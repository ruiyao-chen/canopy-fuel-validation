"""Data access.

Every backend returns one ``pandas.DataFrame`` with one row per GEDI shot and
the columns in ``REQUIRED_COLUMNS``, so the modelling and validation code never
needs to know where the samples came from:

    get_samples(regions, backend=...)  -> DataFrame
    quality_filter(df)                 -> DataFrame (GEDI shot screening)
    save_samples / load_samples        -> CSV cache of an extraction

``backend="synthetic"`` simulates GEDI tracks over a synthetic landscape whose
true canopy height is known, with a documented GEDI-like error model on top.
The whole pipeline, and the tests, run offline from it, and every metric
computed against GEDI can also be computed against the truth.

``backend="gee"`` pulls real GEDI L2A, Sentinel-2, SRTM and LANDFIRE EVT from
Google Earth Engine (see ``gee.py``; needs ``earthengine-api`` and a project).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .spatial import EARTH_RADIUS_M, lonlat_to_xy


# --------------------------------------------------------------------------- #
# Output contract
# --------------------------------------------------------------------------- #
REQUIRED_COLUMNS = [
    "region", "shot_id", "track_id", "beam", "lon", "lat", "x_m", "y_m",
    "rh98", "quality_flag", "sensitivity",
    *config.BAND_KEYS, "elevation", "slope", "aspect",
    "evt_group", "evt_name",
]
# Synthetic only: ``h_true`` (noise-free canopy height at the footprint).


def check_contract(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"sample table is missing columns: {missing}")


def quality_filter(
    df: pd.DataFrame,
    min_sensitivity: float = config.GEDI_MIN_SENSITIVITY,
    power_beams_only: bool = True,
) -> pd.DataFrame:
    """GEDI shot screening, identical for both backends.

    Keeps shots with quality_flag == 1, sensitivity >= ``min_sensitivity``,
    RH98 inside ``config.GEDI_RH98_RANGE`` and (optionally) full-power beams,
    and drops rows with any missing predictor. The GEE backend applies the
    same screen server-side; applying it again here is harmless.
    """
    lo, hi = config.GEDI_RH98_RANGE
    m = (
        (df["quality_flag"] == 1)
        & (df["sensitivity"] >= min_sensitivity)
        & df["rh98"].between(lo, hi)
    )
    if power_beams_only:
        m &= df["beam"].isin(config.GEDI_POWER_BEAMS)
    preds = [*config.BAND_KEYS, "elevation", "slope", "aspect"]
    m &= df[preds].notna().all(axis=1)
    return df.loc[m].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Synthetic backend
# --------------------------------------------------------------------------- #
# Surface-reflectance endmembers, summer, in config.BAND_KEYS order
# (blue, green, red, re1, re2, re3, nir, swir1, swir2). Rounded,
# literature-typical shapes; not fitted to any library spectrum.
_SPECTRA = {
    "conifer":     [0.020, 0.040, 0.025, 0.075, 0.160, 0.200, 0.220, 0.105, 0.045],
    "oak":         [0.030, 0.065, 0.040, 0.110, 0.240, 0.290, 0.310, 0.165, 0.080],
    "chaparral":   [0.030, 0.055, 0.045, 0.095, 0.170, 0.200, 0.220, 0.160, 0.085],
    "dry_grass":   [0.070, 0.100, 0.130, 0.160, 0.195, 0.215, 0.230, 0.320, 0.240],
    "soil_sierra": [0.100, 0.140, 0.175, 0.200, 0.220, 0.230, 0.240, 0.300, 0.250],
    "soil_coast":  [0.085, 0.120, 0.160, 0.190, 0.210, 0.220, 0.230, 0.310, 0.270],
}
_SPECTRA = {k: np.asarray(v) for k, v in _SPECTRA.items()}

# GEDI-like observation model applied to the true canopy height h:
#   rh98 = sqrt(h^2 + floor^2) + slope_coef * D * tan(slope) + e
#   e ~ N(0, sd0^2 + (sd_rel * h)^2 + (slope_coef * D * tan(slope))^2)
# * floor: pulse width keeps RH98 above zero over bare ground and low shrubs.
# * slope term: on slopes the ground return spreads across the footprint
#   (diameter D), inflating RH98 and its scatter.
# Values are order-of-magnitude choices for a test bed, not a calibrated GEDI
# error model.
GEDI_ERROR = dict(floor_m=2.0, sd0_m=0.8, sd_rel=0.06, slope_coef=0.12)
# Shot-level contamination. Most is flagged (and removed by quality_filter);
# a small fraction passes QC, as in real data.
_P_BAD_FLAGGED = 0.05
_P_BAD_UNFLAGGED = 0.005

# GEDI beam numbers: coverage beams 0-3, full-power beams 5, 6, 8, 11.
_BEAMS = [0, 1, 2, 3, 5, 6, 8, 11]

_SUN_ZENITH_DEG = 28.0      # mid-summer, ~10:30 local overpass
_SUN_AZIMUTH_DEG = 140.0


def _grf(n: int, cell_m: float, scale_m: float, rng: np.random.Generator) -> np.ndarray:
    """Zero-mean, unit-variance Gaussian random field (Gaussian kernel, sd = scale_m)."""
    k = np.fft.fftfreq(n, d=cell_m)
    kx, ky = np.meshgrid(k, k)
    filt = np.exp(-2.0 * (np.pi * scale_m) ** 2 * (kx ** 2 + ky ** 2))
    f = np.fft.ifft2(np.fft.fft2(rng.standard_normal((n, n))) * filt).real
    return (f - f.mean()) / f.std()


def _smooth(a: np.ndarray, cell_m: float, scale_m: float) -> np.ndarray:
    n = a.shape[0]
    k = np.fft.fftfreq(n, d=cell_m)
    kx, ky = np.meshgrid(k, k)
    filt = np.exp(-2.0 * (np.pi * scale_m) ** 2 * (kx ** 2 + ky ** 2))
    return np.fft.ifft2(np.fft.fft2(a) * filt).real


def _unit(a: np.ndarray) -> np.ndarray:
    return (a - a.min()) / (a.max() - a.min())


def _sigmoid(a):
    return 1.0 / (1.0 + np.exp(-a))


def _landscape(region_key: str, rng: np.random.Generator, domain_m: float, cell_m: float) -> dict:
    """Gridded terrain and latent vegetation fields for one region.

    Grid rows run south -> north, columns west -> east, centred on (0, 0).
    """
    n = int(round(domain_m / cell_m))
    c = (np.arange(n) + 0.5) * cell_m - domain_m / 2
    X, _ = np.meshgrid(c, c)
    xf = (X + domain_m / 2) / domain_m              # 0 (west) .. 1 (east)

    if region_key == "sierra_conifer":
        # West-slope gradient (foothills -> crest) plus ridges and valleys.
        elev = (600 + 1800 * (0.65 * xf + 0.35 * _unit(_grf(n, cell_m, 8000, rng)))
                + 380 * _grf(n, cell_m, 1200, rng))
        elev = np.clip(elev, 300, 3000)
    elif region_key == "coastal_chaparral":
        # Coast range: a central ridge, steep dissected slopes.
        ridge = np.sin(np.pi * xf)
        elev = (30 + 1000 * _unit(_grf(n, cell_m, 5000, rng) + 1.5 * ridge)
                + 330 * _grf(n, cell_m, 800, rng))
        elev = np.clip(elev, 5, None)
    else:
        raise ValueError(f"no synthetic landscape for region {region_key!r}")

    gy, gx = np.gradient(elev, cell_m)
    return dict(
        elev=elev,
        slope=np.degrees(np.arctan(np.hypot(gx, gy))),
        # downslope azimuth, clockwise from north; carried as unit components
        # so interpolation does not wrap through 0/360
        asp_n=-gy / np.maximum(np.hypot(gx, gy), 1e-9),
        asp_e=-gx / np.maximum(np.hypot(gx, gy), 1e-9),
        tpi=elev - _smooth(elev, cell_m, 1000),     # <0 in valleys and canyons
        cover=_grf(n, cell_m, 3000, rng),           # stand-scale density
        fine=_grf(n, cell_m, 600, rng),             # patch-scale density
        age=_unit(_grf(n, cell_m, 2000, rng)),      # time since disturbance
        moist=_grf(n, cell_m, 2500, rng),           # soil/fog moisture
        # Height drivers and spectral confounders that optics cannot separate:
        site=_grf(n, cell_m, 1500, rng),            # site productivity (no spectral trace)
        mix=_grf(n, cell_m, 2000, rng),             # hardwood share in conifer stands
        soilb=_grf(n, cell_m, 1000, rng),           # background brightness
    )


def _sample_grid(grid: np.ndarray, x: np.ndarray, y: np.ndarray, domain_m: float, cell_m: float):
    from scipy.ndimage import map_coordinates
    r = (y + domain_m / 2) / cell_m - 0.5
    c = (x + domain_m / 2) / cell_m - 0.5
    return map_coordinates(grid, [r, c], order=1, mode="nearest")


def _gedi_tracks(rng, domain_m: float, n_passes: int, shot_stride: int):
    """Footprint centres for ``n_passes`` GEDI passes (8 beams, 600 m apart).

    Passes cross at +/-35-50 deg from north (ISS orbit at California latitudes);
    shots are 60 m apart along track, thinned by ``shot_stride``.
    """
    half = domain_m / 2
    xs, ys, beams, passes = [], [], [], []
    for p in range(n_passes):
        h = np.deg2rad(rng.choice([-1, 1]) * rng.uniform(35, 50))
        u = np.array([np.sin(h), np.cos(h)])          # along-track (east, north)
        nrm = np.array([np.cos(h), -np.sin(h)])       # across-track
        cx, cy = rng.uniform(-0.8 * half, 0.8 * half, 2)
        step = 60.0 * shot_stride
        s = np.arange(-1.5 * domain_m, 1.5 * domain_m, step) + rng.uniform(0, step)
        for b, beam in enumerate(_BEAMS):
            off = (b - 3.5) * 600.0
            x = cx + off * nrm[0] + s * u[0]
            y = cy + off * nrm[1] + s * u[1]
            keep = (np.abs(x) < half) & (np.abs(y) < half)
            xs.append(x[keep]); ys.append(y[keep])
            beams.append(np.full(keep.sum(), beam)); passes.append(np.full(keep.sum(), p))
    return (np.concatenate(xs), np.concatenate(ys),
            np.concatenate(beams), np.concatenate(passes))


def _vegetation(region_key: str, s: dict, rng) -> dict:
    """Vegetation type, stand height, cover fraction and spectrum per footprint."""
    n = len(s["elev"])
    north_w = s["asp_n"] * np.sin(np.deg2rad(s["slope"]))   # north-facing AND steep
    age = s["age"]
    site_f = 0.7 + 0.6 * _sigmoid(1.5 * s["site"])          # 0.7-1.3 x potential height
    vtype = np.empty(n, dtype=object)

    if region_key == "sierra_conifer":
        e = s["elev"]
        lat = (1.1 * s["cover"] + 0.7 * s["fine"] + 1.2 * north_w + 0.3
               - 2.0 * np.clip((e - 2400) / 400, 0, 1)        # sparse near treeline
               - 0.8 * np.clip((1000 - e) / 400, 0, 1))       # dry foothills
        C = _sigmoid(lat)
        vtype[:] = "herb"
        vtype[C > 0.25] = "shrub"
        vtype[(C > 0.45) & (e >= 1100)] = "conifer"
        vtype[(C > 0.45) & (e < 1100)] = "oak_pine"
        hmax = (18 + 30 * np.exp(-((e - 1800) / 650) ** 2)) * site_f
        H = np.select(
            [vtype == "conifer", vtype == "oak_pine", vtype == "shrub"],
            [hmax * (0.35 + 0.65 * age ** 0.8) * (0.55 + 0.45 * C),
             (6 + 10 * age) * (0.6 + 0.4 * C) * site_f,
             0.8 + 2.7 * age],
            0.2 + 0.5 * age)
        fc = np.select(
            [vtype == "conifer", vtype == "oak_pine", vtype == "shrub"],
            [0.45 + 0.5 * C, 0.3 + 0.5 * C, 0.5 + 0.4 * age], 0.5)
        soil = _SPECTRA["soil_sierra"]
        names = {"conifer": ("Forest", "Synthetic Sierra mixed conifer forest"),
                 "oak_pine": ("Woodland", "Synthetic oak-pine woodland"),
                 "shrub": ("Shrubland", "Synthetic montane chaparral"),
                 "herb": ("Herbaceous", "Synthetic annual grassland / meadow")}
        veg = {"conifer": _SPECTRA["conifer"],
               "oak_pine": 0.5 * (_SPECTRA["oak"] + _SPECTRA["conifer"]),
               "shrub": _SPECTRA["chaparral"], "herb": _SPECTRA["dry_grass"]}
        # hardwood share varies within conifer stands (black oak, maple)
        hw = 0.35 * _sigmoid(1.5 * s["mix"])
    else:  # coastal_chaparral
        moist = 1.6 * north_w + 1.0 * s["moist"] - 0.012 * s["tpi"] + 0.2 * s["fine"]
        vtype[:] = "chaparral"
        vtype[(moist < -1.8) | ((s["slope"] < 10) & (moist < -0.8))] = "herb"
        vtype[(moist > 1.0) & (s["slope"] < 32)] = "oak"
        vtype[(moist > 3.0) & (s["tpi"] < -40)] = "conifer"
        H = np.select(
            [vtype == "conifer", vtype == "oak", vtype == "chaparral"],
            [(22 + 25 * age) * site_f,
             (6 + 10 * age) * (0.75 + 0.25 * _sigmoid(moist - 2.0)) * site_f,
             1.0 + 3.0 * age ** 0.8],
            0.2 + 0.5 * age)
        fc = np.select(
            [vtype == "conifer", vtype == "oak", vtype == "chaparral"],
            [0.8 + 0.15 * age, 0.35 + 0.4 * _sigmoid(moist - 2.0), 0.65 + 0.3 * age], 0.5)
        soil = _SPECTRA["soil_coast"]
        names = {"conifer": ("Forest", "Synthetic canyon conifer (redwood / Douglas-fir)"),
                 "oak": ("Woodland", "Synthetic coast live oak woodland"),
                 "chaparral": ("Shrubland", "Synthetic chamise-ceanothus chaparral"),
                 "herb": ("Herbaceous", "Synthetic annual grassland")}
        veg = {"conifer": _SPECTRA["conifer"], "oak": _SPECTRA["oak"],
               "chaparral": _SPECTRA["chaparral"], "herb": _SPECTRA["dry_grass"]}
        # canyon conifers mix with bay laurel / tanoak
        hw = 0.35 * _sigmoid(1.5 * s["mix"])

    veg_spec = np.stack([veg[t] for t in vtype])
    is_con = vtype == "conifer"
    veg_spec[is_con] = ((1 - hw[is_con])[:, None] * _SPECTRA["conifer"]
                        + hw[is_con][:, None] * _SPECTRA["oak"])
    soil = soil[None, :] * (1.0 + 0.15 * np.clip(s["soilb"], -2, 2))[:, None]
    return dict(vtype=vtype, H=H, fc=np.clip(fc, 0.05, 0.98), veg_spec=veg_spec, soil=soil,
                evt_group=np.array([names[t][0] for t in vtype]),
                evt_name=np.array([names[t][1] for t in vtype]))


def _reflectance(H, fc, veg_spec, soil, slope_deg, aspect_deg, rng) -> np.ndarray:
    """Linear canopy/soil mixture with height-dependent shadowing and terrain illumination.

    Taller, denser canopies cast more shadow, darkening every band (strongest
    in SWIR, where sunlit canopy is already dark): the main optical handle on
    height, and one that saturates. No topographic correction is applied, as
    in a standard L2A composite.
    """
    shadow = 0.5 * fc * (1.0 - np.exp(-H / 8.0))       # ~saturated above ~20 m
    tz, ta = np.deg2rad(_SUN_ZENITH_DEG), np.deg2rad(_SUN_AZIMUTH_DEG)
    s, a = np.deg2rad(slope_deg), np.deg2rad(aspect_deg)
    cos_i = np.cos(tz) * np.cos(s) + np.sin(tz) * np.sin(s) * np.cos(ta - a)
    illum = np.clip(cos_i / np.cos(tz), 0.35, 1.4)

    n, nb = veg_spec.shape
    veg = veg_spec * (1.0 + 0.08 * rng.standard_normal((n, 1)))     # within-type variability
    mix = (fc * (1 - shadow))[:, None] * veg + ((1 - fc) * (1 - 0.6 * shadow))[:, None] * soil
    refl = illum[:, None] * mix * (1.0 + 0.04 * rng.standard_normal((n, 1)))  # composite residual
    refl += 0.004 * rng.standard_normal((n, nb))                      # sensor / atmos noise
    return np.clip(refl, 0.001, 1.0)


def _gedi_observe(h_true, slope_deg, vtype, beam, rng, err=GEDI_ERROR) -> dict:
    n = len(h_true)
    slope_term = config.GEDI_FOOTPRINT_M * np.tan(np.deg2rad(slope_deg))
    sd = np.sqrt(err["sd0_m"] ** 2 + (err["sd_rel"] * h_true) ** 2
                 + (err["slope_coef"] * slope_term) ** 2)
    rh98 = (np.sqrt(h_true ** 2 + err["floor_m"] ** 2)
            + err["slope_coef"] * slope_term + sd * rng.standard_normal(n))

    # Sensitivity: coverage beams penetrate less, and dense canopy is harder.
    coverage = np.isin(beam, [0, 1, 2, 3])
    sens = np.clip(rng.normal(0.975, 0.012, n) - 0.025 * coverage
                   - 0.01 * np.isin(vtype, ["conifer"]), 0.80, 0.999)
    # Low-sensitivity shots in forest miss the ground -> RH98 too low.
    low = (sens < config.GEDI_MIN_SENSITIVITY) & (h_true > 5)
    rh98[low] *= rng.uniform(0.55, 0.9, low.sum())

    quality = np.ones(n, dtype=int)
    bad = rng.random(n) < _P_BAD_FLAGGED
    quality[bad] = 0
    rh98[bad] = rng.uniform(-5, 80, bad.sum())                       # clouds, noise
    sneaky = (~bad) & (rng.random(n) < _P_BAD_UNFLAGGED)
    rh98[sneaky] += rng.uniform(5, 25, sneaky.sum())                 # passes QC
    return dict(rh98=rh98, sensitivity=sens, quality_flag=quality)


def synthetic_region(
    region_key: str,
    seed: int = 0,
    n_passes: int = 6,
    shot_stride: int = 2,
    domain_km: float = 40.0,
    cell_m: float = 80.0,
) -> pd.DataFrame:
    """Simulate GEDI shots + Sentinel-2/SRTM predictors over one synthetic region.

    ``seed`` selects the landscape realisation and all noise draws: two seeds
    give two independent landscapes with the same ecology (used to measure
    the true out-of-area error that cross-validation is trying to estimate).
    """
    region = config.REGIONS[region_key]
    rng = np.random.default_rng([seed, sum(map(ord, region_key))])
    domain_m = domain_km * 1000.0
    grids = _landscape(region_key, rng, domain_m, cell_m)

    x, y, beam, pas = _gedi_tracks(rng, domain_m, n_passes, shot_stride)
    s = {k: _sample_grid(v, x, y, domain_m, cell_m) for k, v in grids.items()}
    aspect = (np.degrees(np.arctan2(s["asp_e"], s["asp_n"])) + 360.0) % 360.0

    v = _vegetation(region_key, s, rng)
    # Stand height -> footprint height: within-stand variability that no
    # 10-20 m optical pixel can see (irreducible for the model).
    h_true = v["H"] * np.exp(0.15 * rng.standard_normal(len(x)) - 0.5 * 0.15 ** 2)
    refl = _reflectance(v["H"], v["fc"], v["veg_spec"], v["soil"], s["slope"], aspect, rng)
    obs = _gedi_observe(h_true, s["slope"], v["vtype"], beam, rng)

    lon0, lat0 = region.center
    lat = lat0 + np.rad2deg(y / EARTH_RADIUS_M)
    lon = lon0 + np.rad2deg(x / (EARTH_RADIUS_M * np.cos(np.deg2rad(lat0))))

    df = pd.DataFrame({
        "region": region_key,
        "shot_id": [f"SYN/{region_key}/{seed}/{i:06d}" for i in range(len(x))],
        "track_id": [f"SYN/{region_key}/{seed}/pass{p:02d}" for p in pas],
        "beam": beam, "lon": lon, "lat": lat, "x_m": x, "y_m": y,
        "rh98": obs["rh98"], "quality_flag": obs["quality_flag"],
        "sensitivity": obs["sensitivity"],
        **{k: refl[:, i] for i, k in enumerate(config.BAND_KEYS)},
        "elevation": s["elev"], "slope": s["slope"], "aspect": aspect,
        "evt_group": v["evt_group"], "evt_name": v["evt_name"],
        "h_true": h_true,
    })
    return df


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #
def save_samples(df: pd.DataFrame, path: str | Path) -> Path:
    check_contract(df)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path


def load_samples(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    check_contract(df)
    return _ensure_xy(df)


def _ensure_xy(df: pd.DataFrame) -> pd.DataFrame:
    """Fill x_m / y_m from lon / lat (per-region local projection) where missing."""
    df = df.copy()
    for key, idx in df.groupby("region").groups.items():
        sub = df.loc[idx]
        if sub[["x_m", "y_m"]].notna().all().all():
            continue
        lon0, lat0 = config.REGIONS[key].center if key in config.REGIONS else (
            sub["lon"].mean(), sub["lat"].mean())
        x, y = lonlat_to_xy(sub["lon"], sub["lat"], lon0, lat0)
        df.loc[idx, "x_m"] = x
        df.loc[idx, "y_m"] = y
    return df


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def get_samples(
    regions: list[str] | None = None,
    backend: str = "synthetic",
    seed: int = config.SEED,
    project: str | None = None,
    max_samples: int = 8000,
    **synthetic_kw,
) -> pd.DataFrame:
    """Raw (unfiltered) GEDI shots with predictors for each region."""
    regions = regions or config.DEFAULT_REGIONS
    if backend == "synthetic":
        frames = [synthetic_region(r, seed=seed, **synthetic_kw) for r in regions]
    elif backend == "gee":
        from . import gee
        frames = [gee.fetch_region(r, project=project, max_samples=max_samples, seed=seed)
                  for r in regions]
    else:
        raise ValueError(f"unknown backend {backend!r}")
    df = _ensure_xy(pd.concat(frames, ignore_index=True))
    check_contract(df)
    return df
