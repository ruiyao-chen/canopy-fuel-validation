"""Configuration: study regions, data sources, features, and evaluation strata.

Two contrasting fire-prone California ecoregions are used so that the model can
be trained in one and tested in the other:

* Sierra Nevada west-slope mixed conifer: tall (20-50 m), closed-canopy forest
  grading into oak-pine woodland and montane chaparral.
* Central Coast chaparral / oak (Santa Lucia Range): dense evergreen shrub
  (1-4 m), oak woodland, annual grassland, and conifers confined to moist
  canyons.

The two are deliberately different in the way that matters for transfer:
dense chaparral is spectrally "green" like a forest but only a few metres
tall, so a model that learns "green = tall" in the Sierra will over-predict
shrub height on the coast.
"""

from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# Study regions
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Region:
    key: str
    name: str
    bbox: tuple[float, float, float, float]   # (lon_min, lat_min, lon_max, lat_max)
    epa_l3: str                                # intended EPA Level III ecoregion
    note: str = ""

    @property
    def center(self) -> tuple[float, float]:
        lon0, lat0, lon1, lat1 = self.bbox
        return (0.5 * (lon0 + lon1), 0.5 * (lat0 + lat1))


# AOIs are ~40 x 40 km boxes inside each ecoregion. They are starting points:
# check them on a map before the first real run (the GEE fetch prints the EPA
# Level III ecoregion names each AOI intersects).
REGIONS: dict[str, Region] = {
    "sierra_conifer": Region(
        "sierra_conifer", "Sierra Nevada mixed conifer",
        (-120.40, 38.05, -119.95, 38.40), "Sierra Nevada (EPA L3 5)",
        "Stanislaus NF west slope; ~600-2700 m; mixed conifer, oak-pine, chaparral.",
    ),
    "coastal_chaparral": Region(
        "coastal_chaparral", "Central Coast chaparral / oak",
        (-121.45, 35.55, -120.95, 35.95), "Central California coastal chaparral/oak (EPA L3 6)",
        "Southern Santa Lucia Range; chaparral, oak woodland, grassland, canyon conifers.",
    ),
}

DEFAULT_REGIONS = ["sierra_conifer", "coastal_chaparral"]


# --------------------------------------------------------------------------- #
# Earth Engine sources (verified against the GEE data catalog, Oct 2026)
# --------------------------------------------------------------------------- #
EE_GEDI_L2A_MONTHLY = "LARSE/GEDI/GEDI02_A_002_MONTHLY"     # 25 m rasterised L2A shots
EE_S2_SR = "COPERNICUS/S2_SR_HARMONIZED"
EE_CLOUD_SCORE_PLUS = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
EE_SRTM = "USGS/SRTMGL1_003"
EE_LANDFIRE_EVT = "LANDFIRE/Vegetation/EVT/v1_4_0"          # 2016-era EVT, 30 m
EE_MODIS_BURNED = "MODIS/061/MCD64A1"                        # 500 m monthly burned area
EE_EPA_L3 = "EPA/Ecoregions/2013/L3"

# GEDI acquisition window: mission start to the March 2023 storage period.
GEDI_START = "2019-04-18"
GEDI_END = "2023-03-16"
# Leaf-on Sentinel-2 composite: median of June-September over these years.
S2_YEARS = (2020, 2022)
S2_MONTHS = (6, 9)
CLOUD_SCORE_THRESHOLD = 0.60          # cs_cdf >= threshold is "clear"

# GEDI shot screening (L2A user guide recommendations).
GEDI_POWER_BEAMS = (5, 6, 8, 11)      # BEAM0101, BEAM0110, BEAM1000, BEAM1011
GEDI_MIN_SENSITIVITY = 0.95
GEDI_RH98_RANGE = (0.0, 90.0)         # metres; outside this is not canopy

GEDI_FOOTPRINT_M = 25.0


# --------------------------------------------------------------------------- #
# Features
# --------------------------------------------------------------------------- #
# Sentinel-2 L2A bands used, as (internal key, GEE band).
S2_BANDS: list[tuple[str, str]] = [
    ("blue", "B2"), ("green", "B3"), ("red", "B4"),
    ("re1", "B5"), ("re2", "B6"), ("re3", "B7"),
    ("nir", "B8"), ("swir1", "B11"), ("swir2", "B12"),
]
BAND_KEYS = [k for k, _ in S2_BANDS]
INDEX_KEYS = ["ndvi", "evi", "ndre", "nbr", "ndmi"]
TERRAIN_KEYS = ["elevation", "slope", "northness", "eastness"]

# Coordinates are deliberately NOT features: the goal is a model that
# transfers to new places, not one that interpolates between GEDI tracks.
FEATURES = BAND_KEYS + INDEX_KEYS + TERRAIN_KEYS

TARGET = "rh98"


# --------------------------------------------------------------------------- #
# Evaluation strata
# --------------------------------------------------------------------------- #
# Height classes chosen for fuel relevance (surface / shrub / ladder / canopy),
# not for statistical convenience. Upper edges are exclusive.
HEIGHT_CLASSES: list[tuple[str, float, float]] = [
    ("<2 m grass/low shrub", 0.0, 2.0),
    ("2-5 m shrub", 2.0, 5.0),
    ("5-15 m woodland", 5.0, 15.0),
    ("15-30 m forest", 15.0, 30.0),
    (">=30 m tall forest", 30.0, float("inf")),
]

# Coarse physiognomy groups used for the vegetation-type error analysis.
# Real data: derived from LANDFIRE EVT class names. Synthetic: assigned directly.
EVT_GROUPS = ["Forest", "Woodland", "Riparian", "Shrubland", "Herbaceous", "Other"]


# --------------------------------------------------------------------------- #
# Validation defaults
# --------------------------------------------------------------------------- #
N_FOLDS = 5
MIN_BLOCK_KM = 2.0          # floor for the variogram-derived block size
ALPHA = 0.10                # 90 % prediction intervals
SEED = 0
