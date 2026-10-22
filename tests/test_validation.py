"""Validation design: metrics, spatial blocking, variogram, and the claims the
README makes about evaluation schemes, checked against synthetic truth."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from canopy_fuel import config, data, experiments as E, spatial, validation as V


def test_metrics_known_values():
    m = V.metrics([0, 1, 2, 3], [1, 2, 3, 4])
    assert m["n"] == 4
    assert m["bias"] == pytest.approx(1.0)        # predicted - reference
    assert m["rmse"] == pytest.approx(1.0)
    assert m["mae"] == pytest.approx(1.0)
    assert m["r2"] == pytest.approx(1 - 4 / 5)
    assert V.metrics([1, np.nan], [np.nan, 2])["n"] == 0


def test_height_class_edges():
    hc = V.height_class([0.0, 1.99, 2.0, 14.9, 15.0, 30.0, 80.0])
    labels = [c[0] for c in config.HEIGHT_CLASSES]
    assert list(hc) == [labels[0], labels[0], labels[1], labels[2], labels[3], labels[4], labels[4]]


def test_spatial_folds_keep_blocks_whole_and_balanced(small):
    blocks = spatial.assign_blocks(small, 4.0)
    folds = V.spatial_folds(small, 4.0, n_folds=5, seed=1)
    per_block = pd.DataFrame({"b": blocks, "f": folds}).groupby("b")["f"].nunique()
    assert (per_block == 1).all()
    sizes = folds.value_counts()
    assert len(sizes) == 5
    assert sizes.max() < 1.6 * sizes.min()


def test_blocks_are_unique_per_region(small):
    blocks = spatial.assign_blocks(small, 4.0)
    regions_per_block = pd.DataFrame({"b": blocks, "r": small["region"]}).groupby("b")["r"].nunique()
    assert (regions_per_block == 1).all()


def test_buffer_mask():
    train = np.array([[0.0, 0.0], [500.0, 0.0], [2000.0, 0.0]])
    test = np.array([[0.0, 100.0]])
    # distances to the test point: 100 m, 510 m, 2002 m
    assert spatial.buffer_mask(train, test, 1000.0).tolist() == [False, False, True]
    assert spatial.buffer_mask(train, test, 0.0).all()


def test_variogram_recovers_known_correlation_range():
    """A Gaussian-kernel field with sd s has correlation exp(-h^2 / 4 s^2):
    95 % of the sill is reached at h = 2 s sqrt(ln 20) ~ 3.46 s."""
    rng = np.random.default_rng(0)
    n, cell, s = 400, 50.0, 1000.0
    field = data._grf(n, cell, s, rng)
    idx = rng.integers(0, n, size=(3000, 2))
    x, y = idx[:, 1] * cell, idx[:, 0] * cell
    c, g, _ = spatial.empirical_variogram(x, y, field[idx[:, 0], idx[:, 1]],
                                          max_dist_m=8000, n_bins=32)
    assert spatial.practical_range(c, g) == pytest.approx(3.46 * s, rel=0.3)
    # white noise: no structure, range collapses to the first lag
    c, g, _ = spatial.empirical_variogram(x, y, rng.standard_normal(3000), max_dist_m=8000, n_bins=32)
    assert spatial.practical_range(c, g) < 1000


def test_block_size_is_at_least_the_floor(small):
    block_km, vg = V.choose_block_km(small)
    assert block_km >= config.MIN_BLOCK_KM
    assert set(vg) == set(small["region"])


@pytest.fixture(scope="module")
def schemes(small, independent):
    cv, _ = E.cv_schemes(small, ["linear", "xgb"], block_km=4.0, fast=True)
    tr, _ = E.transfer(small, ["xgb"], fast=True)
    ia = E.independent_area(small, independent, ["xgb"], fast=True)
    g = cv[cv.reference == "GEDI RH98"].pivot_table(index=["region", "model"],
                                                    columns="scheme", values="rmse")
    g["independent"] = ia.groupby(["region", "model"])["rmse"].mean()
    g["transfer"] = tr.set_index(["test_region", "model"])["rmse"]
    return g, cv


def test_random_cv_is_optimistic_and_spatial_cv_is_closer_to_new_area_error(schemes):
    """The core validation claim, checked where the answer is known: error on
    fresh landscapes is the target; random k-fold underestimates it, spatial
    blocks (+ buffer) get closer."""
    g, _ = schemes
    for region in config.DEFAULT_REGIONS:
        r = g.loc[(region, "xgb")]
        assert r["random"] < r["spatial"] <= r["spatial+buffer"] + 0.05
        assert r["random"] < r["independent"]
        assert abs(r["independent"] - r["spatial+buffer"]) < abs(r["independent"] - r["random"])


def test_cross_region_transfer_is_worst(schemes):
    g, _ = schemes
    for region in config.DEFAULT_REGIONS:
        r = g.loc[(region, "xgb")]
        assert r["transfer"] > r["independent"]
        assert r["transfer"] > 1.2 * r["spatial"]


def test_xgboost_beats_linear_baseline_under_spatial_cv(schemes):
    g, _ = schemes
    for region in config.DEFAULT_REGIONS:
        assert g.loc[(region, "xgb"), "spatial"] < g.loc[(region, "linear"), "spatial"]


def test_model_inherits_reference_floor_bias_in_low_vegetation(small):
    """GEDI RH98 does not go to zero over grass (pulse width). A model trained
    on GEDI reproduces that: unbiased vs GEDI, biased high vs the truth."""
    folds = V.spatial_folds(small, 4.0)
    pred = V.cv_predict(small, folds, "xgb", fast=True)
    low = small["h_true"].to_numpy() < 1.0
    assert abs(np.mean(pred - small["rh98"].to_numpy())) < 0.3
    assert np.mean(pred[low] - small["h_true"].to_numpy()[low]) > 1.0


def test_metrics_by_class_cover_all_rows(small):
    d = small.assign(pred=small["rh98"] + 1.0)
    t = E.by_height_class(d, "pred", extra_by=["region"])
    assert t["n"].sum() == len(small)
    assert np.allclose(t["bias"], 1.0)
    evt = V.metrics_table(d, "rh98", "pred", by=["region", "evt_group"])
    assert evt["n"].sum() == len(small)
