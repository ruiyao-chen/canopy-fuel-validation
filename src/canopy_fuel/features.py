"""Predictor engineering: spectral indices and terrain derivatives.

Both backends deliver raw surface reflectance bands, elevation, slope and
aspect; the indices are computed here, locally, so the same (tested) code
serves synthetic and real data.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def _nd(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Normalised difference (a - b) / (a + b), NaN where the sum is ~0."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    s = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(s) > 1e-9, (a - b) / s, np.nan)


def ndvi(nir, red):
    return _nd(nir, red)


def ndre(nir, re1):
    """Red-edge NDVI: more sensitive than NDVI at high canopy density."""
    return _nd(nir, re1)


def nbr(nir, swir2):
    """Normalised burn ratio: SWIR-2 responds to canopy water and char."""
    return _nd(nir, swir2)


def ndmi(nir, swir1):
    """Normalised difference moisture index (live-fuel moisture proxy)."""
    return _nd(nir, swir1)


def evi(nir, red, blue):
    nir, red, blue = (np.asarray(v, dtype=float) for v in (nir, red, blue))
    den = nir + 6.0 * red - 7.5 * blue + 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(den) > 1e-9, 2.5 * (nir - red) / den, np.nan)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with indices and aspect components added.

    Requires the band columns in ``config.BAND_KEYS`` plus ``elevation``,
    ``slope`` (deg) and ``aspect`` (deg clockwise from north).
    """
    out = df.copy()
    out["ndvi"] = ndvi(out["nir"], out["red"])
    out["evi"] = evi(out["nir"], out["red"], out["blue"])
    out["ndre"] = ndre(out["nir"], out["re1"])
    out["nbr"] = nbr(out["nir"], out["swir2"])
    out["ndmi"] = ndmi(out["nir"], out["swir1"])
    asp = np.deg2rad(out["aspect"].to_numpy(dtype=float))
    out["northness"] = np.cos(asp)
    out["eastness"] = np.sin(asp)
    return out


def feature_matrix(df: pd.DataFrame, features: list[str] | None = None) -> np.ndarray:
    cols = features or config.FEATURES
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"missing feature columns {missing}; call add_features() first")
    return df[cols].to_numpy(dtype=float)
