"""Google Earth Engine extraction: GEDI L2A shots with co-located predictors.

Needs an authenticated Earth Engine account and project. Run
``scripts/fetch_gee.py`` once to pull and cache the samples to CSV;
everything downstream reads the cache.

Per region the extraction is:

1. GEDI L2A monthly rasters (25 m, one pixel per shot), screened
   server-side: quality_flag == 1, degrade_flag == 0, sensitivity >= 0.95,
   full-power beams only, RH98 within a plausible canopy range.
2. Sentinel-2 L2A (harmonised), Cloud Score+ masked (cs_cdf >= 0.6),
   June-September median over the GEDI years, scaled to reflectance.
3. SRTM elevation, slope and aspect.
4. LANDFIRE EVT (v1.4.0) for the vegetation-type error analysis.
5. Footprints in MODIS burned area during the GEDI/Sentinel-2 window are
   dropped: height measured before a fire and spectra after it disagree
   for reasons the model should not be blamed for (500 m product, so small
   fires are missed).

The result is sampled at GEDI pixel centres and returned as a DataFrame in
the ``data.REQUIRED_COLUMNS`` contract.

Robustness (learned on the first real runs): every request has a client
deadline and bounded retries, each region is fetched as small tiles with one
non-paginated request per tile, and the subsample is chosen by a
deterministic per-shot hash rather than a server-side random sort.
"""

from __future__ import annotations

import time
import warnings

import numpy as np
import pandas as pd

from . import config


def _require_ee():
    try:
        import ee  # noqa: F401
    except ImportError as exc:  # pragma: no cover - env dependent
        raise ImportError(
            "The 'gee' backend needs the Earth Engine API.\n"
            "    pip install earthengine-api\n"
            "    earthengine authenticate\n"
            "Then pass your Cloud project id: --project your-ee-project."
        ) from exc
    return __import__("ee")


REQUEST_DEADLINE_MS = 180_000   # client-side socket timeout per request
MAX_ATTEMPTS = 4                 # per request, with 15/30/60 s backoff
TILES_PER_SIDE = 4               # ~10 km tiles for a ~40 km AOI
KEEP_FRAC = 0.2                  # hash threshold; trimmed to max_samples locally

_INITIALIZED: set[str] = set()


def _retry(fn, what: str, attempts: int = MAX_ATTEMPTS):
    """Call ``fn``; on any error log it, back off and retry, then raise."""
    for k in range(1, attempts + 1):
        t0 = time.time()
        try:
            return fn()
        except Exception as exc:  # network, deadline, EE server errors
            msg = f"{type(exc).__name__}: {str(exc)[:200]}"
            if k == attempts:
                raise RuntimeError(f"{what}: failed {attempts} times; last error {msg}") from exc
            wait = 15 * 2 ** (k - 1)
            print(f"    {what}: attempt {k} failed after {time.time() - t0:.0f} s ({msg}); "
                  f"retrying in {wait} s", flush=True)
            time.sleep(wait)


def _init(project: str):
    """Initialise Earth Engine once per process, with a request deadline.

    Every ee.Initialize() refreshes the OAuth token, so it is done once.
    Without a deadline the client waits forever on a stalled connection (one
    extraction sat 1 h 50 min on a single idle socket).
    """
    ee = _require_ee()
    if project not in _INITIALIZED:  # pragma: no cover - needs credentials
        _retry(lambda: ee.Initialize(project=project), "ee.Initialize")
        ee.data.setDeadline(REQUEST_DEADLINE_MS)
        _INITIALIZED.add(project)
    return ee


# --------------------------------------------------------------------------- #
# Pure helpers (testable offline)
# --------------------------------------------------------------------------- #
def evt_group(name: str) -> str:
    """Coarse physiognomy group from a LANDFIRE EVT class name.

    Keyword rules, checked in order. "Forest and Woodland" systems count as
    Forest; oak or pine "Woodland" and "Savanna" as Woodland; riparian
    systems get their own group. "Other" collects water, developed land,
    roads, cropland, barren and no-data (code 0).
    """
    n = str(name).lower()
    if any(k in n for k in ("developed", "agricultur", "urban", "quarr", "open water",
                            "snow", "barren", "sparsely vegetated", "recently")):
        return "Other"
    if "riparian" in n:          # e.g. California Montane Riparian Systems: tall, mixed
        return "Riparian"
    if "forest" in n or "plantation" in n:
        return "Forest"
    if "woodland" in n or "savanna" in n:
        return "Woodland"
    if any(k in n for k in ("shrub", "chaparral", "scrub", "sage", "manzanita")):
        return "Shrubland"
    if any(k in n for k in ("grass", "herbaceous", "meadow", "prairie", "steppe", "forb")):
        return "Herbaceous"
    return "Other"


def _find_evt_lookup(props: dict) -> dict[int, str]:
    """Map EVT code -> name from the image's class-table properties.

    The catalog stores the table as two parallel lists (codes and names);
    rather than hard-code their property keys, find a list of strings whose
    key mentions 'name' and a numeric list of the same length.
    """
    names_key = next((k for k, v in props.items()
                      if "name" in k.lower() and isinstance(v, list) and v
                      and all(isinstance(x, str) for x in v)), None)
    if names_key is None:
        return {}
    names = props[names_key]
    codes_key = next((k for k, v in props.items()
                      if k != names_key and isinstance(v, list) and len(v) == len(names)
                      and all(isinstance(x, (int, float)) for x in v)), None)
    if codes_key is None:
        return {}
    return {int(c): str(nm) for c, nm in zip(props[codes_key], names)}


# --------------------------------------------------------------------------- #
# Earth Engine pieces
# --------------------------------------------------------------------------- #
def aoi(ee, region_key: str):
    return ee.Geometry.Rectangle(list(config.REGIONS[region_key].bbox))


def ecoregions_in_aoi(region_key: str, project: str) -> list[str]:  # pragma: no cover
    """EPA Level III ecoregion names that the AOI touches (sanity check)."""
    ee = _init(project)
    fc = ee.FeatureCollection(config.EE_EPA_L3).filterBounds(aoi(ee, region_key))
    return sorted(set(_retry(lambda: fc.aggregate_array("us_l3name").getInfo(),
                             f"{region_key}: EPA ecoregions")))


def _gedi(ee, region):  # pragma: no cover
    lo, hi = config.GEDI_RH98_RANGE

    def screen(im):
        beam = im.select("beam")
        power = beam.eq(config.GEDI_POWER_BEAMS[0])
        for b in config.GEDI_POWER_BEAMS[1:]:
            power = power.Or(beam.eq(b))
        ok = (im.select("quality_flag").eq(1)
              .And(im.select("degrade_flag").eq(0))
              .And(im.select("sensitivity").gte(config.GEDI_MIN_SENSITIVITY))
              .And(im.select("rh98").gte(lo)).And(im.select("rh98").lte(hi))
              .And(power))
        return im.updateMask(ok).select(
            ["rh98", "sensitivity", "quality_flag", "beam", "orbit_number",
             "shot_number_within_beam", "delta_time", "solar_elevation"])

    # Monthly rasters are tiled by UTM zone, each on its own 25 m grid. An AOI
    # that straddles a zone boundary (the Sierra box crosses 120 W) must be
    # sampled zone by zone on the native grid, or shots are dropped or
    # duplicated by nearest-neighbour regridding.
    coll = (ee.ImageCollection(config.EE_GEDI_L2A_MONTHLY)
            .filterBounds(region)
            .filterDate(config.GEDI_START, config.GEDI_END)
            .map(lambda im: im.set("crs", im.select("rh98").projection().crs())))
    out = []
    zones = _retry(lambda: coll.aggregate_array("crs").distinct().getInfo(), "GEDI UTM zones")
    for crs in zones:
        sub = coll.filter(ee.Filter.eq("crs", crs))
        proj = ee.Image(sub.first()).select("rh98").projection()
        # Overlapping shots from different months are rare; keep the most sensitive.
        out.append((sub.map(screen).qualityMosaic("sensitivity"), proj))
    return out


def _s2_composite(ee, region):  # pragma: no cover
    y0, y1 = config.S2_YEARS
    m0, m1 = config.S2_MONTHS
    cs = ee.ImageCollection(config.EE_CLOUD_SCORE_PLUS)
    s2 = (ee.ImageCollection(config.EE_S2_SR)
          .filterBounds(region)
          .filterDate(f"{y0}-01-01", f"{y1 + 1}-01-01")
          .filter(ee.Filter.calendarRange(m0, m1, "month"))
          .linkCollection(cs, ["cs_cdf"])
          .map(lambda im: im.updateMask(im.select("cs_cdf").gte(config.CLOUD_SCORE_THRESHOLD))))
    gee_bands = [b for _, b in config.S2_BANDS]
    keys = [k for k, _ in config.S2_BANDS]
    return s2.select(gee_bands).median().divide(10000).rename(keys)


def _terrain(ee):  # pragma: no cover
    dem = ee.Image(config.EE_SRTM).select("elevation")
    return ee.Terrain.products(dem).select(["elevation", "slope", "aspect"])


def _evt(ee, region):  # pragma: no cover
    return (ee.ImageCollection(config.EE_LANDFIRE_EVT).filterBounds(region)
            .mosaic().select("EVT").rename("evt_code"))


def _unburned(ee):  # pragma: no cover
    burned = (ee.ImageCollection(config.EE_MODIS_BURNED)
              .filterDate(config.GEDI_START, config.GEDI_END)
              .select("BurnDate").max().gt(0).unmask(0))
    return burned.Not()


def _shot_hash(ee, f, seed: int = 0):  # pragma: no cover
    """Pseudo-random number in [0, 1) that depends only on the shot and seed."""
    key = (ee.Number(f.get("orbit_number")).multiply(1e8)
           .add(ee.Number(f.get("beam")).multiply(1e7))
           .add(f.get("shot_number_within_beam")))
    return key.add(seed * 7919).multiply(12.9898).sin().multiply(43758.5453).mod(1).abs()


def evt_lookup(project: str) -> dict[int, str]:  # pragma: no cover
    ee = _init(project)
    img = ee.Image(ee.ImageCollection(config.EE_LANDFIRE_EVT).first())
    return _find_evt_lookup(_retry(lambda: img.toDictionary().getInfo(), "EVT class table"))


def _tiles(ee, region_key: str, n: int):
    lon0, lat0, lon1, lat1 = config.REGIONS[region_key].bbox
    xs, ys = np.linspace(lon0, lon1, n + 1), np.linspace(lat0, lat1, n + 1)
    return [ee.Geometry.Rectangle([float(xs[i]), float(ys[j]), float(xs[i + 1]), float(ys[j + 1])])
            for j in range(n) for i in range(n)]


def fetch_region(region_key: str, project: str | None, max_samples: int = 8000,
                 seed: int = 0, tiles: int = TILES_PER_SIDE,
                 keep_frac: float = KEEP_FRAC) -> pd.DataFrame:
    """Screened GEDI shots with predictors for one region, as a DataFrame.

    The region is fetched as ``tiles`` x ``tiles`` tiles. In each tile, shots
    whose per-shot hash is below ``keep_frac`` are returned in one
    non-paginated request; locally, the ``max_samples`` lowest-hash shots
    are kept. The subsample is therefore deterministic and independent of
    the tiling.
    """
    if not project:
        raise ValueError("an Earth Engine project id is required for the gee backend "
                         "(--project your-ee-project)")
    ee = _init(project)  # pragma: no cover - below needs a live account
    region = aoi(ee, region_key)

    predictors = (_s2_composite(ee, region)
                  .addBands(_terrain(ee))
                  .addBands(_evt(ee, region))
                  .addBands(ee.Image.pixelLonLat()))
    unburned = _unburned(ee)
    zones = _gedi(ee, region)
    n_tiles = tiles * tiles
    rows = []
    for k, tile in enumerate(_tiles(ee, region_key, tiles), 1):
        fc = None
        for gedi, proj in zones:
            part = (gedi.addBands(predictors).updateMask(unburned)
                    .sample(region=tile, projection=proj, dropNulls=True,
                            tileScale=4, geometries=False))
            fc = part if fc is None else fc.merge(part)
        # Deterministic per-shot hash, not randomColumn(): the first
        # extraction (randomColumn + sort + paginated computeFeatures) came
        # back with ~2 % duplicated shots and as many missing.
        fc = (fc.map(lambda f: f.set("rnd", _shot_hash(ee, f, seed)))
              .filter(ee.Filter.lt("rnd", keep_frac)))
        t0 = time.time()
        feats = _retry(lambda: fc.getInfo()["features"], f"{region_key} tile {k}/{n_tiles}")
        rows += [f["properties"] for f in feats]
        print(f"  {region_key} tile {k:2d}/{n_tiles}: {len(feats):5d} shots "
              f"({time.time() - t0:.0f} s)", flush=True)
    df = pd.DataFrame(rows)

    lookup = {}
    try:
        lookup = evt_lookup(project)
    except Exception as exc:  # property layout differs from expectation
        warnings.warn(f"could not read LANDFIRE EVT class names ({exc}); using codes only")

    df = df.rename(columns={"longitude": "lon", "latitude": "lat"})
    df["region"] = region_key
    df["orbit_number"] = df["orbit_number"].astype(int)
    df["beam"] = df["beam"].astype(int)
    df["track_id"] = "orbit" + df["orbit_number"].astype(str)
    df["shot_id"] = (df["track_id"] + "-b" + df["beam"].astype(str) + "-"
                     + df["shot_number_within_beam"].astype(int).astype(str))
    df["evt_code"] = df["evt_code"].astype("Int64")
    df["evt_name"] = df["evt_code"].map(lambda c: lookup.get(int(c), f"EVT {c}")
                                        if pd.notna(c) else "unknown")
    df["evt_group"] = df["evt_name"].map(evt_group)
    df["x_m"] = np.nan
    df["y_m"] = np.nan
    # a shot can only appear once even if tiles or UTM zones overlap
    n_rows = len(df)
    df = df.drop_duplicates("shot_id")
    if len(df) < n_rows:
        print(f"  {region_key}: {n_rows - len(df)} duplicate shots removed at tile seams",
              flush=True)
    df = df.sort_values("rnd").head(max_samples).reset_index(drop=True)
    if len(df) < max_samples:
        warnings.warn(f"{region_key}: only {len(df)} shots below keep_frac={keep_frac}; "
                      f"raise keep_frac to reach {max_samples}")
    return df.drop(columns=["rnd", "geo"], errors="ignore")
