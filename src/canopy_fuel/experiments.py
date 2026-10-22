"""The evaluation experiments, as functions returning tidy DataFrames.

``scripts/run_validation.py`` calls these in order and writes the tables
and figures; the tests call them on small synthetic samples.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config, uncertainty as U, validation as V
from .features import feature_matrix

SCHEMES = ["random", "spatial", "spatial+buffer"]


# --------------------------------------------------------------------------- #
# Point accuracy
# --------------------------------------------------------------------------- #
def cv_schemes(df: pd.DataFrame, models: list[str], block_km: float,
               buffer_m: float = 1000.0, n_folds: int = config.N_FOLDS,
               seed: int = 0, fast: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Within-region CV under each scheme, per region and model.

    Returns (metrics, oof) where ``oof`` holds out-of-fold predictions in
    columns ``pred:<model>:<scheme>`` aligned with ``df``.
    """
    oof = df.copy()
    rows = []
    for region, g in df.groupby("region"):
        folds = {
            "random": V.random_folds(g, n_folds, seed),
            "spatial": V.spatial_folds(g, block_km, n_folds, seed),
        }
        for m in models:
            for scheme in SCHEMES:
                f = folds["random" if scheme == "random" else "spatial"]
                buf = buffer_m if scheme == "spatial+buffer" else 0.0
                p = V.cv_predict(g, f, m, buffer_m=buf, seed=seed, fast=fast)
                oof.loc[g.index, f"pred:{m}:{scheme}"] = p
                rows.append(dict(region=region, model=m, scheme=scheme,
                                 reference="GEDI RH98", **V.metrics(g[config.TARGET], p)))
                if "h_true" in g:
                    rows.append(dict(region=region, model=m, scheme=scheme,
                                     reference="true height", **V.metrics(g["h_true"], p)))
    return pd.DataFrame(rows), oof


def transfer(df: pd.DataFrame, models: list[str], seed: int = 0,
             fast: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on each region, test on every other region."""
    regions = sorted(df["region"].unique())
    preds = df.copy()
    rows = []
    for a in regions:
        for b in regions:
            if a == b:
                continue
            test = df[df.region == b]
            for m in models:
                p = V.transfer_predict(df[df.region == a], test, m, seed=seed, fast=fast)
                preds.loc[test.index, f"pred:{m}:transfer"] = p
                rows.append(dict(train_region=a, test_region=b, model=m,
                                 **V.metrics(test[config.TARGET], p)))
    return pd.DataFrame(rows), preds


def independent_area(df: pd.DataFrame, independent: list[pd.DataFrame], models: list[str],
                     seed: int = 0, fast: bool = False) -> pd.DataFrame:
    """Synthetic only: error on fresh landscapes of the same ecology.

    This is the quantity CV is trying to estimate (error in a new,
    unsampled area of the same ecoregion). It can only be measured where
    landscapes can be re-drawn, which is the reason for the simulator.
    """
    rows = []
    for region, g in df.groupby("region"):
        for m in models:
            for k, ind in enumerate(independent):
                t = ind[ind.region == region]
                p = V.transfer_predict(g, t, m, seed=seed, fast=fast)
                rows.append(dict(region=region, model=m, realisation=k,
                                 **V.metrics(t[config.TARGET], p)))
    return pd.DataFrame(rows)


FEATURE_SETS = {
    "all features": config.FEATURES,
    "without elevation": [f for f in config.FEATURES if f != "elevation"],
    "spectral only": config.BAND_KEYS + config.INDEX_KEYS,
}


def feature_ablation(df: pd.DataFrame, block_km: float, model: str = "xgb",
                     feature_sets: dict[str, list[str]] | None = None,
                     seed: int = 0, fast: bool = False) -> pd.DataFrame:
    """In-region spatial-CV RMSE vs cross-region RMSE for each feature set.

    Absolute elevation is a strong *local* predictor of height but encodes
    region-specific ecology (low = dry foothills in the Sierra, moist
    redwood canyons on the coast), so in-region CV can favour exactly the
    feature that transfers worst.
    """
    feature_sets = feature_sets or FEATURE_SETS
    regions = sorted(df["region"].unique())
    rows = []
    for name, feats in feature_sets.items():
        for b in regions:
            test = df[df.region == b]
            p_in = V.cv_predict(test, V.spatial_folds(test, block_km, seed=seed), model,
                                features=feats, seed=seed, fast=fast)
            for a in regions:
                if a == b:
                    continue
                p = V.transfer_predict(df[df.region == a], test, model, features=feats,
                                       seed=seed, fast=fast)
                tall = test[config.TARGET].to_numpy() >= 15
                rows.append(dict(
                    features=name, train_region=a, test_region=b,
                    rmse_within=V.metrics(test[config.TARGET], p_in)["rmse"],
                    rmse_transfer=V.metrics(test[config.TARGET], p)["rmse"],
                    bias_transfer=V.metrics(test[config.TARGET], p)["bias"],
                    bias_transfer_tall=float(np.mean(p[tall] - test[config.TARGET].to_numpy()[tall])),
                ))
    return pd.DataFrame(rows)


def by_height_class(df: pd.DataFrame, pred_col: str, ref_col: str = config.TARGET,
                    extra_by: list[str] | None = None) -> pd.DataFrame:
    """Metrics per fuel-relevant height class, binned on the reference height."""
    d = df.assign(height_class=V.height_class(df[ref_col]))
    return V.metrics_table(d, ref_col, pred_col, by=(extra_by or []) + ["height_class"])


# --------------------------------------------------------------------------- #
# Prediction intervals
# --------------------------------------------------------------------------- #
def _interval_columns(out: pd.DataFrame, qm: U.QuantileXGB, X_test, cal: pd.DataFrame,
                      X_cal, alpha: float, prefix: str = "") -> pd.DataFrame:
    lo_c, _, hi_c = qm.predict(X_cal)
    lo_t, med_t, hi_t = qm.predict(X_test)
    out[f"{prefix}median"] = med_t
    out[f"{prefix}lo:raw"], out[f"{prefix}hi:raw"] = lo_t, hi_t
    lo, hi, _ = U.cqr_intervals(lo_c, hi_c, cal[config.TARGET], lo_t, hi_t, alpha)
    out[f"{prefix}lo:cqr"], out[f"{prefix}hi:cqr"] = lo, hi
    # Mondrian by *predicted* height class: usable at deployment, unlike
    # binning on the (unknown) reference.
    gc = V.height_class(np.clip(qm.predict(X_cal)[1], 0, None)).astype(str)
    gt = V.height_class(np.clip(med_t, 0, None)).astype(str)
    lo, hi, _ = U.cqr_intervals(lo_c, hi_c, cal[config.TARGET], lo_t, hi_t, alpha,
                                groups_cal=gc, groups_test=gt)
    out[f"{prefix}lo:mondrian"], out[f"{prefix}hi:mondrian"] = lo, hi
    if cal["region"].nunique() > 1:
        lo, hi, _ = U.cqr_intervals(lo_c, hi_c, cal[config.TARGET], lo_t, hi_t, alpha,
                                    groups_cal=cal["region"], groups_test=out["region"])
        out[f"{prefix}lo:mondrian_region"], out[f"{prefix}hi:mondrian_region"] = lo, hi
    return out


def intervals_within(df: pd.DataFrame, block_km: float, alpha: float = config.ALPHA,
                     seed: int = 0, fast: bool = False) -> pd.DataFrame:
    """Pooled model; train / calibration / test split by spatial block in each region."""
    split = U.block_split(df, block_km, seed=seed)
    tr, cal, te = (df[split == s] for s in ("train", "cal", "test"))
    qm = U.QuantileXGB(alpha, seed=seed, fast=fast).fit(feature_matrix(tr), tr[config.TARGET])
    out = te.copy()
    return _interval_columns(out, qm, feature_matrix(te), cal, feature_matrix(cal), alpha)


def intervals_transfer(df: pd.DataFrame, train_region: str, test_region: str,
                       block_km: float, alpha: float = config.ALPHA,
                       local_frac: float = 0.2, seed: int = 0,
                       fast: bool = False) -> pd.DataFrame:
    """Calibrate in one region, test in another; then recalibrate locally.

    The source region is split (by block) into train and calibration; the
    target region is split into a small local calibration set
    (``local_frac`` of its blocks, standing in for a targeted field or
    airborne-LiDAR campaign) and a test set. Every interval variant is scored
    on the same target test shots.
    """
    src = df[df.region == train_region]
    tgt = df[df.region == test_region]
    s_split = U.block_split(src, block_km, fractions=(0.75, 0.25, 0.0), seed=seed)
    t_split = U.block_split(tgt, block_km, fractions=(local_frac, 1 - local_frac, 0.0), seed=seed)
    tr, cal_src = src[s_split == "train"], src[s_split == "cal"]
    # target blocks: first share -> local calibration, the rest -> test
    cal_loc, te = tgt[t_split == "train"], tgt[t_split == "cal"]

    qm = U.QuantileXGB(alpha, seed=seed, fast=fast).fit(feature_matrix(tr), tr[config.TARGET])
    out = te.copy()
    X_te = feature_matrix(te)
    _interval_columns(out, qm, X_te, cal_src, feature_matrix(cal_src), alpha)   # source-calibrated
    _interval_columns(out, qm, X_te, cal_loc, feature_matrix(cal_loc), alpha, prefix="local:")
    out["train_region"] = train_region
    return out


INTERVAL_METHODS = {
    "raw": "Quantile XGBoost (uncalibrated)",
    "cqr": "CQR",
    "mondrian": "Mondrian CQR by predicted height class",
    "mondrian_region": "Mondrian CQR by region",
}


def interval_summary(out: pd.DataFrame, by: list[str] | None = None,
                     prefixes: tuple[str, ...] = ("",)) -> pd.DataFrame:
    """Coverage / width for every method (and calibration source) present."""
    rows = []
    for pre in prefixes:
        for meth in INTERVAL_METHODS:
            lo, hi = f"{pre}lo:{meth}", f"{pre}hi:{meth}"
            if lo not in out:
                continue
            t = U.coverage_table(out, config.TARGET, lo, hi, by=by)
            t.insert(0, "method", meth)
            t.insert(0, "calibration", "local" if pre == "local:" else "source")
            rows.append(t)
    return pd.concat(rows, ignore_index=True)


def repeated_intervals(fn, seeds, groupings: dict[str, list[str] | None],
                       prefixes: tuple[str, ...] = ("",), **kw) -> dict[str, pd.DataFrame]:
    """Run an interval experiment over several random block splits.

    One split is one draw: with spatially correlated errors, coverage on a
    single calibration/test split can sit a few points off nominal by chance.
    Each split is summarised under every grouping in ``groupings`` (name ->
    ``by`` columns). Two derived columns are available to group on:
    ``height_class`` (binned on the GEDI reference) and ``pred_height_class``
    (binned on the predicted median, the only one known at deployment).
    Returns name -> per-repeat rows (column ``repeat``); aggregate with
    ``aggregate_repeats``.
    """
    rows: dict[str, list] = {name: [] for name in groupings}
    for k, seed in enumerate(seeds):
        out = fn(seed=seed, **kw)
        out = out.assign(height_class=V.height_class(out[config.TARGET]),
                         pred_height_class=V.height_class(np.clip(out["median"], 0, None)))
        for name, by in groupings.items():
            rows[name].append(interval_summary(out, by=by, prefixes=prefixes).assign(repeat=k))
    return {name: pd.concat(r, ignore_index=True) for name, r in rows.items()}


def aggregate_repeats(rep: pd.DataFrame) -> pd.DataFrame:
    keys = [c for c in rep.columns
            if c not in ("n", "coverage", "mean_width", "median_width", "repeat")]
    return (rep.groupby(keys, observed=True, sort=False)
               .agg(n=("n", "mean"), coverage=("coverage", "mean"),
                    coverage_sd=("coverage", "std"), coverage_min=("coverage", "min"),
                    mean_width=("mean_width", "mean"), median_width=("median_width", "mean"))
               .reset_index())
