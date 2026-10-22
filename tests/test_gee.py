"""The parts of the Earth Engine backend that can be checked without an account."""

from __future__ import annotations

import pytest

from canopy_fuel import config, gee


@pytest.mark.parametrize("name, group", [
    ("Mediterranean California Dry-Mesic Mixed Conifer Forest and Woodland", "Forest"),
    ("Mediterranean California Mixed Oak Woodland", "Woodland"),
    ("California Mesic Chaparral", "Shrubland"),
    ("California Montane Riparian Systems", "Riparian"),
    ("Western Warm Temperate Fallow/Idle Cropland", "Other"),
    ("Inter-Mountain Basins Big Sagebrush Shrubland", "Shrubland"),
    ("California Central Valley and Southern Coastal Grassland", "Herbaceous"),
    ("Developed-Low Intensity", "Other"),
    ("Open Water", "Other"),
    ("Western Cool Temperate Urban Evergreen Forest", "Other"),
])
def test_evt_group_keywords(name, group):
    assert gee.evt_group(name) == group


def test_evt_lookup_found_without_hardcoded_keys():
    props = {"EVT_class_values": [3001, 3002], "EVT_class_names": ["A Forest", "B Chaparral"],
             "EVT_class_palette": ["000000", "ffffff"], "system:index": "CONUS"}
    assert gee._find_evt_lookup(props) == {3001: "A Forest", 3002: "B Chaparral"}
    assert gee._find_evt_lookup({"foo": 1}) == {}


def test_fetch_requires_project_before_touching_earth_engine():
    with pytest.raises(ValueError, match="project"):
        gee.fetch_region("sierra_conifer", project=None)


def test_region_definitions_are_valid():
    for r in config.REGIONS.values():
        lon0, lat0, lon1, lat1 = r.bbox
        assert lon0 < lon1 and lat0 < lat1
        assert -125 < lon0 < -114 and 32 < lat0 < 42          # California
        assert (lon1 - lon0) < 1.0 and (lat1 - lat0) < 1.0    # ~40-90 km AOIs
