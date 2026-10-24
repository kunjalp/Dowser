"""Tests for match_wells.py. Run from the repo root: python -m pytest pipeline/test_match_wells.py -q"""
import os
import sys

import geopandas as gpd
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from match_wells import DEFAULT_WELLS, METERS_CRS, load_documented, match  # noqa: E402

# Two made-up documented wells in Kern (lat/lon).
FAKE_WELLS = gpd.GeoDataFrame(
    {"apiNumber": ["0402900001", "0402900002"], "status": ["Plugged", "Canceled"]},
    geometry=gpd.points_from_xy([-119.40, -119.50], [35.20, 35.30]),
    crs=4326,
).to_crs(METERS_CRS)

# About 0.00055 degrees of latitude is roughly 61 m; 0.0018 is roughly 200 m.
DETECTIONS = pd.DataFrame({
    "detectionId": ["on_well", "near_well", "far_away", "near_canceled"],
    "lat": [35.20, 35.20055, 35.2018, 35.30],
    "lon": [-119.40, -119.40, -119.40, -119.50],
})


def test_point_on_a_documented_well_is_not_a_candidate():
    r = match(DETECTIONS, FAKE_WELLS).set_index("detectionId")
    assert r.loc["on_well", "nearestDocumentedDistM"] < 1
    assert r.loc["on_well", "nearestDocumentedId"] == "0402900001"
    assert not r.loc["on_well", "isCandidate"]


def test_point_60m_away_is_still_matched():
    r = match(DETECTIONS, FAKE_WELLS).set_index("detectionId")
    assert 50 < r.loc["near_well", "nearestDocumentedDistM"] < 70
    assert not r.loc["near_well", "isCandidate"]


def test_point_200m_from_any_record_is_a_candidate():
    r = match(DETECTIONS, FAKE_WELLS).set_index("detectionId")
    assert 180 < r.loc["far_away", "nearestDocumentedDistM"] < 220
    assert r.loc["far_away", "isCandidate"]


def test_canceled_wells_count_as_documented():
    r = match(DETECTIONS, FAKE_WELLS).set_index("detectionId")
    assert r.loc["near_canceled", "nearestDocumentedStatus"] == "Canceled"
    assert not r.loc["near_canceled", "isCandidate"]


def test_real_calgem_well_matches_itself():
    """Smoke test on the real CalGEM file, skipped if it has not been loaded yet."""
    if not os.path.exists(DEFAULT_WELLS):
        return
    wells = load_documented(DEFAULT_WELLS)
    first = wells.to_crs(4326).iloc[0]
    det = pd.DataFrame({"lat": [first.geometry.y], "lon": [first.geometry.x]})
    r = match(det, wells)
    assert r.loc[0, "nearestDocumentedDistM"] < 1
    assert not r.loc[0, "isCandidate"]
