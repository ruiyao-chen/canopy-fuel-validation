"""Validation design: how the canopy-height model is evaluated.

Three evaluation schemes, from most to least optimistic:

1. **Random k-fold.** Shots are assigned to folds at random. Neighbouring
   shots on the same GEDI track land on both sides of the split, so the
   score partly measures interpolation. Reported only to show the gap.
2. **Spatial block k-fold.** The region is tiled into square blocks at
   least as large as the residual autocorrelation range (from the
   variogram) and whole blocks are assigned to folds, with an optional
   buffer that drops training shots near any test shot. Estimates the error
   in an unsampled area of the *same* ecoregion.
3. **Cross-region transfer.** Train on one ecoregion, test on the other.
   Estimates the error when the model is deployed somewhere it has never
   seen, which is the real product question.

Metrics are reported overall and by fuel-relevant height class.
Sign convention: ``bias = mean(predicted - reference)``.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config, spatial
from .features import feature_matrix
from .models import make_model


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def metrics(obs, pred) -> dict:
    obs = np.asarray(obs, dtype=float)
    pred = np.asarray(pred, dtype=float)
    ok = np.isfinite(obs) & np.isfinite(pred)
    obs, pred = obs[ok], pred[ok]
    n = len(obs)
    if n == 0:
        return dict(n=0, rmse=np.nan, bias=np.nan, mae=np.nan, r2=np.nan)
    err = pred - obs
    sst = np.sum((obs - obs.mean()) ** 2)
    return dict(
        n=n,
        rmse=float(np.sqrt(np.mean(err ** 2))),
        bias=float(np.mean(err)),
        mae=float(np.mean(np.abs(err))),
        r2=float(1.0 - np.sum(err ** 2) / sst) if n > 1 and sst > 0 else np.nan,
    )


def height_class(h) -> pd.Categorical:
    labels = [c[0] for c in config.HEIGHT_CLASSES]
    edges = [c[1] for c in config.HEIGHT_CLASSES] + [config.HEIGHT_CLASSES[-1][2]]
    return pd.cut(np.asarray(h, dtype=float), bins=edges, labels=labels, right=False)


def metrics_table(df: pd.DataFrame, obs_col: str, pred_col: str,
                  by: list[str] | None = None) -> pd.DataFrame:
    """Metrics for the whole table, or per group of ``by`` columns."""
    if not by:
        return pd.DataFrame([metrics(df[obs_col], df[pred_col])])
    rows = []
    for key, g in df.groupby(by, observed=True, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(by, key)), **metrics(g[obs_col], g[pred_col])})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Fold assignment
# --------------------------------------------------------------------------- #
def random_folds(df: pd.DataFrame, n_folds: int = config.N_FOLDS, seed: int = 0) -> pd.Series:
    rng = np.random.default_rng(seed)
    f = rng.permutation(np.arange(len(df)) % n_folds)
    return pd.Series(f, index=df.index, name="fold")


def spatial_folds(df: pd.DataFrame, block_km: float, n_folds: int = config.N_FOLDS,
                  seed: int = 0) -> pd.Series:
    return spatial.block_folds(spatial.assign_blocks(df, block_km), n_folds, seed)


def choose_block_km(df: pd.DataFrame, features: list[str] | None = None,
                    max_dist_km: float = 15.0, seed: int = 0) -> tuple[float, dict]:
    """Block size from the practical range of linear-model residuals.

    Leakage comes from what the predictors do *not* explain, so the
    variogram is computed on residuals of a ridge fit, per region; the
    largest range is used, rounded up to 0.5 km and floored at
    ``config.MIN_BLOCK_KM``.
    """
    out = {}
    for key, g in df.groupby("region"):
        m = make_model("linear").fit(feature_matrix(g, features), g[config.TARGET])
        resid = g[config.TARGET].to_numpy() - m.predict(feature_matrix(g, features))
        c, gam, cnt = spatial.empirical_variogram(
            g["x_m"], g["y_m"], resid, max_dist_m=max_dist_km * 1000, seed=seed)
        out[key] = dict(lag_m=c, gamma=gam, pairs=cnt,
                        range_m=spatial.practical_range(c, gam))
    rng_km = max(v["range_m"] for v in out.values()) / 1000.0
    block = max(config.MIN_BLOCK_KM, math.ceil(rng_km * 2) / 2)
    return block, out


# --------------------------------------------------------------------------- #
# Prediction under each scheme
# --------------------------------------------------------------------------- #
def cv_predict(df: pd.DataFrame, folds: pd.Series, model_name: str,
               features: list[str] | None = None, buffer_m: float = 0.0,
               seed: int = 0, fast: bool = False) -> np.ndarray:
    """Out-of-fold predictions; each fold's model never sees its test shots.

    With ``buffer_m > 0`` training shots within that distance of any test
    shot are also withheld (spatial buffer / "dead zone").
    """
    X = feature_matrix(df, features)
    y = df[config.TARGET].to_numpy(dtype=float)
    xy = df[["x_m", "y_m"]].to_numpy()
    reg = df["region"].to_numpy()
    f = folds.to_numpy()
    pred = np.full(len(df), np.nan)
    for k in np.unique(f):
        te = f == k
        tr = ~te
        if buffer_m > 0:
            # buffer only within the same region (regions are far apart)
            keep = np.ones(tr.sum(), dtype=bool)
            tr_idx = np.nonzero(tr)[0]
            for r in np.unique(reg[te]):
                sel = reg[tr_idx] == r
                keep[sel] &= spatial.buffer_mask(xy[tr_idx[sel]], xy[te & (reg == r)], buffer_m)
            tr = np.zeros(len(df), dtype=bool)
            tr[tr_idx[keep]] = True
        model = make_model(model_name, seed=seed, fast=fast).fit(X[tr], y[tr])
        pred[te] = model.predict(X[te])
    return pred


def transfer_predict(train: pd.DataFrame, test: pd.DataFrame, model_name: str,
                     features: list[str] | None = None, seed: int = 0,
                     fast: bool = False) -> np.ndarray:
    """Fit on all of ``train`` (one region), predict ``test`` (another)."""
    model = make_model(model_name, seed=seed, fast=fast)
    model.fit(feature_matrix(train, features), train[config.TARGET])
    return model.predict(feature_matrix(test, features))
