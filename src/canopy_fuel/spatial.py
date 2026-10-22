"""Spatial helpers for validation design.

GEDI shots come in tracks (8 beams, 60 m along-track spacing), so neighbouring
samples share the same stand, slope and illumination. A random train/test split
puts near-duplicates on both sides and makes the model look better than it is.
The tools here make that leakage measurable and remove it:

* a local metric projection (no pyproj dependency; adequate within ~100 km),
* square spatial blocks assigned whole to CV folds,
* an optional buffer that drops training samples close to any test sample,
* an empirical variogram whose practical range sets the block size.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

EARTH_RADIUS_M = 6_371_000.0


def lonlat_to_xy(lon, lat, lon0: float, lat0: float) -> tuple[np.ndarray, np.ndarray]:
    """Equirectangular projection about (lon0, lat0), in metres."""
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)
    x = np.deg2rad(lon - lon0) * EARTH_RADIUS_M * np.cos(np.deg2rad(lat0))
    y = np.deg2rad(lat - lat0) * EARTH_RADIUS_M
    return x, y


def assign_blocks(df: pd.DataFrame, block_km: float) -> pd.Series:
    """Label each sample with a square block id, unique across regions."""
    size = block_km * 1000.0
    i = np.floor(df["x_m"].to_numpy() / size).astype(int)
    j = np.floor(df["y_m"].to_numpy() / size).astype(int)
    return pd.Series(
        df["region"].astype(str).to_numpy() + ":" + i.astype(str) + ":" + j.astype(str),
        index=df.index, name="block",
    )


def block_folds(blocks: pd.Series, n_folds: int, seed: int = 0) -> pd.Series:
    """Assign whole blocks to folds, balancing sample counts.

    Blocks are shuffled, then placed largest-first into the fold with the
    fewest samples so far, so folds are similar in size without any block
    being split.
    """
    rng = np.random.default_rng(seed)
    counts = blocks.value_counts()
    order = rng.permutation(counts.index.to_numpy())
    order = sorted(order, key=lambda b: -counts[b])   # stable: ties keep shuffle
    load = np.zeros(n_folds, dtype=int)
    fold_of: dict[str, int] = {}
    for b in order:
        k = int(np.argmin(load))
        fold_of[b] = k
        load[k] += counts[b]
    return blocks.map(fold_of).astype(int).rename("fold")


def buffer_mask(train_xy: np.ndarray, test_xy: np.ndarray, buffer_m: float) -> np.ndarray:
    """True for training samples farther than ``buffer_m`` from every test sample."""
    if buffer_m <= 0 or len(test_xy) == 0:
        return np.ones(len(train_xy), dtype=bool)
    d, _ = cKDTree(test_xy).query(train_xy, k=1)
    return d > buffer_m


def empirical_variogram(
    x: np.ndarray,
    y: np.ndarray,
    v: np.ndarray,
    max_dist_m: float = 15_000.0,
    n_bins: int = 30,
    max_points: int = 3000,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classical (Matheron) semivariogram of ``v``.

    Returns (bin centres [m], semivariance, pair counts). Subsamples to
    ``max_points`` so the pairwise computation stays small.
    """
    x, y, v = (np.asarray(a, dtype=float) for a in (x, y, v))
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(v)
    x, y, v = x[ok], y[ok], v[ok]
    if len(v) > max_points:
        idx = np.random.default_rng(seed).choice(len(v), max_points, replace=False)
        x, y, v = x[idx], y[idx], v[idx]

    tree = cKDTree(np.column_stack([x, y]))
    pairs = tree.query_pairs(max_dist_m, output_type="ndarray")
    if len(pairs) == 0:
        raise ValueError("no sample pairs within max_dist_m")
    i, j = pairs[:, 0], pairs[:, 1]
    h = np.hypot(x[i] - x[j], y[i] - y[j])
    sq = 0.5 * (v[i] - v[j]) ** 2

    edges = np.linspace(0.0, max_dist_m, n_bins + 1)
    which = np.clip(np.digitize(h, edges) - 1, 0, n_bins - 1)
    counts = np.bincount(which, minlength=n_bins)
    sums = np.bincount(which, weights=sq, minlength=n_bins)
    with np.errstate(invalid="ignore", divide="ignore"):
        gamma = np.where(counts > 0, sums / counts, np.nan)
    centres = 0.5 * (edges[:-1] + edges[1:])
    return centres, gamma, counts


def practical_range(centres: np.ndarray, gamma: np.ndarray, frac: float = 0.95,
                    min_structure: float = 0.10) -> float:
    """Distance at which the variogram first reaches ``frac`` of its structured rise.

    The nugget is taken from the first populated bin and the sill from the
    mean of the last third of bins; the range is the first lag where the
    (3-bin smoothed) variogram reaches nugget + frac * (sill - nugget).
    If the rise is under ``min_structure`` of the sill the variogram is
    treated as flat (no spatial structure) and the first lag is returned;
    otherwise sampling noise on a flat variogram produces a spurious range.
    """
    ok = np.isfinite(gamma)
    c, g = centres[ok], gamma[ok]
    if len(g) < 3:
        return float(c[0]) if len(c) else 0.0
    nugget = g[0]
    sill = float(np.mean(g[-max(len(g) // 3, 1):]))
    if sill - nugget < min_structure * sill:
        return float(c[0])
    gs = np.convolve(np.pad(g, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    target = nugget + frac * (sill - nugget)
    hit = np.nonzero(gs >= target)[0]
    return float(c[hit[0]]) if len(hit) else float(c[-1])
