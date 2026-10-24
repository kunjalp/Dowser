"""Tests for dedup.py. Run from the repo root: python -m pytest pipeline/test_dedup.py -q"""
import json
import os
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, os.path.dirname(__file__))
from dedup import METERS_CRS, dedup  # noqa: E402

ORIGIN = gpd.GeoSeries([Point(-119.40, 35.20)], crs=4326).to_crs(METERS_CRS).iloc[0]


def at(dx_m, dy_m):
    """lat/lon of a point dx_m east and dy_m north of ORIGIN."""
    p = gpd.GeoSeries([Point(ORIGIN.x + dx_m, ORIGIN.y + dy_m)], crs=METERS_CRS).to_crs(4326).iloc[0]
    return p.y, p.x


def table(rows):
    out = []
    for i, (dx, dy, year, conf) in enumerate(rows):
        lat, lon = at(dx, dy)
        out.append({"detectionId": f"d{i}", "lat": lat, "lon": lon, "year": year,
                    "confidence": conf, "crop": f"/evidence/d{i}.png", "quadName": "Taft"})
    return pd.DataFrame(out)


def test_10m_apart_merges_and_lists_both_years():
    r = dedup(table([(0, 0, 1947, 0.9), (10, 0, 1962, 0.7)]))
    assert len(r) == 1
    assert json.loads(r.loc[0, "editionsSeen"]) == [1947, 1962]
    assert r.loc[0, "confidence"] == 0.9
    assert r.loc[0, "detectionId"] == "d0"  # highest confidence first
    assert {e["year"] for e in json.loads(r.loc[0, "evidence"])} == {1947, 1962}


def test_50m_apart_stays_separate():
    r = dedup(table([(0, 0, 1947, 0.9), (50, 0, 1947, 0.8)]))
    assert len(r) == 2


def test_same_year_overlapping_tiles_counts_one_edition():
    r = dedup(table([(0, 0, 1962, 0.8), (3, 2, 1962, 0.6)]))
    assert len(r) == 1
    assert json.loads(r.loc[0, "editionsSeen"]) == [1962]
    assert r.loc[0, "nDetections"] == 2


def test_chain_of_neighbors_merges():
    # 0 -> 15 m -> 30 m: each pair within 20 m, ends 30 m apart, still one well
    r = dedup(table([(0, 0, 1947, 0.9), (15, 0, 1962, 0.9), (30, 0, 1978, 0.9)]))
    assert len(r) == 1
    assert json.loads(r.loc[0, "editionsSeen"]) == [1947, 1962, 1978]


def test_accepts_other_column_names_and_missing_confidence():
    df = table([(0, 0, 1947, 0.9)]).rename(columns={"year": "mapYear"}).drop(columns="confidence")
    r = dedup(df)
    assert r.loc[0, "confidence"] == 1.0
    assert json.loads(r.loc[0, "editionsSeen"]) == [1947]
