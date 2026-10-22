"""Per-sample prediction intervals and the checks that they mean what they say.

Two interval methods, plus calibration:

* **Quantile XGBoost** fits the alpha/2, 0.5 and 1-alpha/2 conditional
  quantiles in one model. Intervals adapt to local difficulty (wide in tall
  forest, narrow in grass) but have no coverage guarantee.
* **Conformalised quantile regression (CQR)** (Romano et al., 2019) widens
  or narrows those quantiles by one constant learned on a held-out
  calibration set, which gives finite-sample marginal coverage >= 1-alpha
  *when calibration and test data are exchangeable*.
* **Mondrian CQR** learns that constant separately per group (region, or
  predicted height class), giving coverage per group rather than only on
  average.

The guarantee is the point to test, not to assume: across ecoregions the
exchangeability assumption fails, and ``coverage_table`` shows by how much.
Calibration and test sets are split by spatial block, never by shot, so that
calibration residuals are as independent of training as the test residuals.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config, spatial


# --------------------------------------------------------------------------- #
# Quantile model
# --------------------------------------------------------------------------- #
class QuantileXGB:
    """XGBoost with a multi-quantile pinball loss: lower, median, upper."""

    def __init__(self, alpha: float = config.ALPHA, seed: int = 0, fast: bool = False):
        self.alpha = alpha
        self.quantiles = np.array([alpha / 2, 0.5, 1 - alpha / 2])
        self.seed = seed
        self.fast = fast
        self.model = None

    def fit(self, X, y):
        from xgboost import XGBRegressor
        self.model = XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=self.quantiles,
            n_estimators=150 if self.fast else 500, learning_rate=0.1 if self.fast else 0.05,
            max_depth=6, min_child_weight=5, subsample=0.8, colsample_bytree=0.8,
            tree_method="hist", n_jobs=4, random_state=self.seed,
        )
        self.model.fit(X, y)
        return self

    def predict(self, X) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        q = np.sort(self.model.predict(X), axis=1)   # repair any quantile crossing
        return q[:, 0], q[:, 1], q[:, 2]


# --------------------------------------------------------------------------- #
# Conformal calibration
# --------------------------------------------------------------------------- #
def conformal_quantile(scores, alpha: float) -> float:
    """The ceil((n+1)(1-alpha))-th smallest score (inf if n is too small)."""
    s = np.sort(np.asarray(scores, dtype=float))
    n = len(s)
    k = math.ceil((n + 1) * (1 - alpha))
    return float("inf") if k > n else float(s[k - 1])


def abs_residual_intervals(pred_cal, y_cal, pred_test, alpha: float = config.ALPHA):
    """Split-conformal with |residual| scores: a constant-width band."""
    q = conformal_quantile(np.abs(np.asarray(y_cal) - np.asarray(pred_cal)), alpha)
    pred_test = np.asarray(pred_test, dtype=float)
    return pred_test - q, pred_test + q


def cqr_scores(lo, hi, y) -> np.ndarray:
    """Signed distance outside [lo, hi]; negative when inside."""
    lo, hi, y = (np.asarray(a, dtype=float) for a in (lo, hi, y))
    return np.maximum(lo - y, y - hi)


def cqr_intervals(lo_cal, hi_cal, y_cal, lo_test, hi_test,
                  alpha: float = config.ALPHA,
                  groups_cal=None, groups_test=None, min_group_n: int = 50):
    """CQR; with ``groups_*`` given, Mondrian CQR (one correction per group).

    Groups with fewer than ``min_group_n`` calibration samples fall back to
    the pooled correction rather than an unstable (or infinite) one.
    Returns (lo, hi, q) where q is the per-test-sample correction applied.
    """
    scores = cqr_scores(lo_cal, hi_cal, y_cal)
    q_all = conformal_quantile(scores, alpha)
    lo_test = np.asarray(lo_test, dtype=float)
    hi_test = np.asarray(hi_test, dtype=float)
    q = np.full(len(lo_test), q_all)
    if groups_cal is not None:
        gc = np.asarray(groups_cal)
        gt = np.asarray(groups_test)
        for g in np.unique(gt):
            sel = gc == g
            if sel.sum() >= min_group_n:
                q[gt == g] = conformal_quantile(scores[sel], alpha)
    return lo_test - q, hi_test + q, q


# --------------------------------------------------------------------------- #
# Diagnostics
# --------------------------------------------------------------------------- #
def coverage(y, lo, hi) -> float:
    y, lo, hi = (np.asarray(a, dtype=float) for a in (y, lo, hi))
    return float(np.mean((y >= lo) & (y <= hi)))


def coverage_table(df: pd.DataFrame, y_col: str, lo_col: str, hi_col: str,
                   by: list[str] | None = None) -> pd.DataFrame:
    """Empirical coverage and interval width, overall or per group."""
    def row(g):
        w = g[hi_col] - g[lo_col]
        return dict(n=len(g), coverage=coverage(g[y_col], g[lo_col], g[hi_col]),
                    mean_width=float(w.mean()), median_width=float(w.median()))
    if not by:
        return pd.DataFrame([row(df)])
    out = []
    for key, g in df.groupby(by, observed=True, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        out.append({**dict(zip(by, key)), **row(g)})
    return pd.DataFrame(out)


def block_split(df: pd.DataFrame, block_km: float,
                fractions: tuple[float, float, float] = (0.6, 0.2, 0.2),
                seed: int = 0) -> pd.Series:
    """Assign whole spatial blocks to 'train' / 'cal' / 'test', per region.

    Splitting per region keeps every region represented in each part.
    """
    blocks = spatial.assign_blocks(df, block_km)
    rng = np.random.default_rng(seed)
    part = pd.Series(index=df.index, dtype=object, name="split")
    names = ["train", "cal", "test"]
    for _, idx in df.groupby("region").groups.items():
        b = blocks.loc[idx]
        counts = b.value_counts()
        order = rng.permutation(counts.index.to_numpy())
        cum = np.cumsum(counts.loc[order].to_numpy()) / counts.sum()
        edges = np.cumsum(fractions)[:-1]
        label = np.array(names)[np.searchsorted(edges, cum, side="left").clip(0, 2)]
        part.loc[idx] = b.map(dict(zip(order, label))).to_numpy()
    return part
