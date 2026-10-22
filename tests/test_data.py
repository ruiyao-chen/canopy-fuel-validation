"""Data contract, synthetic simulator, GEDI screening, features, cache."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from canopy_fuel import config, data, features, spatial


def test_synthetic_is_reproducible_and_seed_dependent():
    a = data.synthetic_region("coastal_chaparral", seed=3, n_passes=2, shot_stride=6)
    b = data.synthetic_region("coastal_chaparral", seed=3, n_passes=2, shot_stride=6)
    c = data.synthetic_region("coastal_chaparral", seed=4, n_passes=2, shot_stride=6)
    pd.testing.assert_frame_equal(a, b)
    assert len(a) != len(c) or not np.allclose(a["rh98"], c["rh98"])


def test_contract_and_physical_ranges(small):
    data.check_contract(small)
    bands = small[config.BAND_KEYS].to_numpy()
    assert (bands > 0).all() and (bands <= 1).all()
    assert small["slope"].between(0, 70).all()
    assert small["aspect"].between(0, 360).all()
    med = small.groupby("evt_group")["h_true"].median()
    assert med["Herbaceous"] < 1.5
    assert med["Shrubland"] < 5
    assert med["Forest"] > 15
    # Sierra is the tall-forest region, the coast the shrub region
    by_region = small.groupby("region")["h_true"].median()
    assert by_region["sierra_conifer"] > by_region["coastal_chaparral"]


def test_quality_filter_removes_flagged_low_sensitivity_and_coverage_beams(raw):
    q = data.quality_filter(raw)
    assert (q["quality_flag"] == 1).all()
    assert (q["sensitivity"] >= config.GEDI_MIN_SENSITIVITY).all()
    assert q["beam"].isin(config.GEDI_POWER_BEAMS).all()
    # screening must remove the gross errors injected into flagged shots
    err_raw = (raw["rh98"] - raw["h_true"]).abs()
    err_q = (q["rh98"] - q["h_true"]).abs()
    assert err_raw.quantile(0.99) > 3 * err_q.quantile(0.99)


def test_gedi_error_model_matches_its_specification(small):
    """Recover the documented GEDI error model from the simulated shots."""
    e = data.GEDI_ERROR
    h, s = small["h_true"].to_numpy(), small["slope"].to_numpy()
    slope_term = config.GEDI_FOOTPRINT_M * np.tan(np.deg2rad(s))
    expected = np.sqrt(h ** 2 + e["floor_m"] ** 2) + e["slope_coef"] * slope_term
    sd = np.sqrt(e["sd0_m"] ** 2 + (e["sd_rel"] * h) ** 2 + (e["slope_coef"] * slope_term) ** 2)
    z = (small["rh98"].to_numpy() - expected) / sd
    # robust stats: ~0.5 % of shots carry unflagged outliers by design
    assert abs(np.median(z)) < 0.1
    mad_sd = 1.4826 * np.median(np.abs(z - np.median(z)))
    assert mad_sd == pytest.approx(1.0, abs=0.1)


def test_indices_and_aspect_components():
    df = pd.DataFrame({
        "blue": [0.05], "green": [0.08], "red": [0.10], "re1": [0.20], "re2": [0.3],
        "re3": [0.35], "nir": [0.50], "swir1": [0.25], "swir2": [0.10],
        "elevation": [1000.0], "slope": [10.0], "aspect": [90.0],
    })
    f = features.add_features(df).iloc[0]
    assert f["ndvi"] == pytest.approx(0.4 / 0.6)
    assert f["nbr"] == pytest.approx(0.4 / 0.6)
    assert f["ndmi"] == pytest.approx(0.25 / 0.75)
    assert f["ndre"] == pytest.approx(0.3 / 0.7)
    assert f["evi"] == pytest.approx(2.5 * 0.4 / (0.5 + 0.6 - 0.375 + 1.0))
    assert f["northness"] == pytest.approx(0.0, abs=1e-12)
    assert f["eastness"] == pytest.approx(1.0)
    assert np.isnan(features.ndvi(0.0, 0.0))


def test_local_projection_scale():
    x, y = spatial.lonlat_to_xy([-120.0, -120.0], [38.0, 39.0], -120.0, 38.0)
    assert y[1] - y[0] == pytest.approx(111_195, rel=1e-3)
    x, _ = spatial.lonlat_to_xy(-119.0, 38.0, -120.0, 38.0)
    assert x == pytest.approx(111_195 * np.cos(np.deg2rad(38.0)), rel=1e-3)


def test_cache_roundtrip_and_xy_backfill(tmp_path, raw):
    sub = raw.iloc[:200].copy()
    p = data.save_samples(sub, tmp_path / "s.csv")
    back = data.load_samples(p)
    pd.testing.assert_frame_equal(back.reset_index(drop=True), sub.reset_index(drop=True),
                                  check_dtype=False)
    # a real-data cache has lon/lat but no local coordinates yet
    sub2 = sub.assign(x_m=np.nan, y_m=np.nan)
    back2 = data.load_samples(data.save_samples(sub2, tmp_path / "s2.csv"))
    assert np.allclose(back2["x_m"], sub["x_m"], atol=5.0)   # metres
    assert np.allclose(back2["y_m"], sub["y_m"], atol=5.0)


def test_contract_violation_is_reported(raw):
    with pytest.raises(ValueError, match="rh98"):
        data.check_contract(raw.drop(columns=["rh98"]))
