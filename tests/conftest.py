"""Shared fixtures: small synthetic samples with known truth (offline, seconds)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from canopy_fuel import data, features  # noqa: E402

SMALL = dict(n_passes=3, shot_stride=3)   # ~2.4k screened shots per region


def _prepared(seed: int):
    return features.add_features(data.quality_filter(data.get_samples(seed=seed, **SMALL)))


@pytest.fixture(scope="session")
def raw():
    return data.get_samples(seed=0, **SMALL)


@pytest.fixture(scope="session")
def small():
    return _prepared(0)


@pytest.fixture(scope="session")
def independent():
    """Two fresh landscapes with the same ecology (the 'new area' truth)."""
    return [_prepared(1000 + k) for k in range(2)]
