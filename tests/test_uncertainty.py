"""Prediction intervals: conformal mechanics on textbook cases, then the
coverage behaviour the README reports, on synthetic GEDI data."""

from __future__ import annotations

import numpy as np
import pytest

from canopy_fuel import experiments as E, spatial, uncertainty as U
from canopy_fuel.features import feature_matrix


def test_conformal_quantile_rank():
    s = np.arange(1, 20)                       # n = 19
    assert U.conformal_quantile(s, 0.1) == 18  # ceil(20 * 0.9) = 18th smallest
    assert U.conformal_quantile(np.arange(5), 0.1) == np.inf


def test_split_conformal_covers_on_exchangeable_data():
    """Average coverage must lie in [1-alpha, 1-alpha + 1/(n+1)]."""
    rng = np.random.default_rng(0)
    alpha, n_cal, cov = 0.1, 99, []
    for _ in range(400):
        x = rng.uniform(0, 10, n_cal + 200)
        y = 2 * x + rng.standard_normal(len(x))
        pred = 2 * x + 0.3                     # slightly biased point model
        lo, hi = U.abs_residual_intervals(pred[:n_cal], y[:n_cal], pred[n_cal:], alpha)
        cov.append(U.coverage(y[n_cal:], lo, hi))
    assert 0.9 - 0.006 <= np.mean(cov) <= 0.91 + 0.006


def test_cqr_repairs_miscalibrated_quantiles():
    rng = np.random.default_rng(1)
    x = rng.uniform(0, 10, 4000)
    y = x + rng.standard_normal(4000) * (0.2 + 0.3 * x)     # heteroscedastic
    lo, hi = x - 0.5 * (0.2 + 0.3 * x), x + 0.5 * (0.2 + 0.3 * x)   # far too narrow
    assert U.coverage(y, lo, hi) < 0.5
    cal, te = slice(0, 2000), slice(2000, None)
    lo2, hi2, _ = U.cqr_intervals(lo[cal], hi[cal], y[cal], lo[te], hi[te], 0.1)
    assert U.coverage(y[te], lo2, hi2) == pytest.approx(0.9, abs=0.02)


def test_mondrian_gives_per_group_coverage():
    rng = np.random.default_rng(2)
    n = 6000
    grp = rng.integers(0, 2, n)
    y = rng.standard_normal(n) * np.where(grp == 1, 3.0, 0.5)
    lo, hi = np.full(n, -0.5), np.full(n, 0.5)
    cal, te = slice(0, 3000), slice(3000, None)
    lo_m, hi_m, _ = U.cqr_intervals(lo[cal], hi[cal], y[cal], lo[te], hi[te], 0.1)
    g = grp[te]
    marg = [U.coverage(y[te][g == k], lo_m[g == k], hi_m[g == k]) for k in (0, 1)]
    assert marg[0] > 0.97 and marg[1] < 0.85          # pooled: over / under
    lo_g, hi_g, _ = U.cqr_intervals(lo[cal], hi[cal], y[cal], lo[te], hi[te], 0.1,
                                    groups_cal=grp[cal], groups_test=g)
    for k in (0, 1):
        assert U.coverage(y[te][g == k], lo_g[g == k], hi_g[g == k]) == pytest.approx(0.9, abs=0.03)


def test_quantile_model_returns_ordered_quantiles(small):
    X, y = feature_matrix(small), small["rh98"].to_numpy()
    lo, med, hi = U.QuantileXGB(0.1, fast=True).fit(X[:1500], y[:1500]).predict(X[1500:])
    assert (lo <= med).all() and (med <= hi).all()


def test_block_split_is_disjoint_by_block_and_keeps_regions(small):
    split = U.block_split(small, 4.0, seed=3)
    blocks = spatial.assign_blocks(small, 4.0)
    assert (blocks.groupby(blocks).apply(lambda b: split.loc[b.index].nunique()) == 1).all()
    for _, idx in small.groupby("region").groups.items():
        assert set(split.loc[idx]) == {"train", "cal", "test"}
    frac = split.value_counts(normalize=True)
    assert frac["train"] == pytest.approx(0.6, abs=0.12)


def test_cqr_coverage_near_nominal_within_ecoregions(small):
    rep = E.repeated_intervals(E.intervals_within, range(3), {"overall": None},
                               df=small, block_km=4.0, fast=True)["overall"]
    agg = E.aggregate_repeats(rep).set_index("method")
    assert agg.loc["cqr", "coverage"] == pytest.approx(0.9, abs=0.05)
    assert agg.loc["raw", "coverage"] < agg.loc["cqr", "coverage"]


def test_transfer_breaks_coverage_and_local_calibration_restores_it(small):
    """Calibrated on the coast and applied to the Sierra, CQR under-covers
    (exchangeability fails); recalibrating on 20 % of Sierra blocks fixes
    coverage, at the price of much wider intervals."""
    rep = E.repeated_intervals(E.intervals_transfer, range(3), {"overall": None},
                               prefixes=("", "local:"), df=small,
                               train_region="coastal_chaparral", test_region="sierra_conifer",
                               block_km=4.0, fast=True)["overall"]
    agg = E.aggregate_repeats(rep).set_index(["calibration", "method"])
    assert agg.loc[("source", "cqr"), "coverage"] < 0.85
    assert agg.loc[("local", "cqr"), "coverage"] > 0.85
    assert agg.loc[("local", "cqr"), "mean_width"] > agg.loc[("source", "cqr"), "mean_width"]


def test_coverage_table_groups():
    import pandas as pd
    d = pd.DataFrame({"y": [1, 2, 3, 4], "lo": [0, 0, 0, 5], "hi": [2, 2, 2, 6], "g": ["a", "a", "b", "b"]})
    t = U.coverage_table(d, "y", "lo", "hi", by=["g"]).set_index("g")
    assert t.loc["a", "coverage"] == 1.0
    assert t.loc["b", "coverage"] == 0.0
    assert t.loc["a", "mean_width"] == 2.0
