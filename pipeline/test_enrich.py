"""Tests for enrich.py. Run from the repo root: python -m pytest pipeline/test_enrich.py -q"""
import os
import sys

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point, box

sys.path.insert(0, os.path.dirname(__file__))
from enrich import METERS_CRS, enrich, read_layer  # noqa: E402

# Work in meters around a point in Kern, then convert to lat/lon for the candidate table.
ORIGIN = gpd.GeoSeries([Point(-119.40, 35.20)], crs=4326).to_crs(METERS_CRS).iloc[0]
X0, Y0 = ORIGIN.x, ORIGIN.y


def meters(geoms):
    return gpd.GeoDataFrame(geometry=geoms, crs=METERS_CRS)


HOMES = meters([box(X0 + 300, Y0 - 10, X0 + 320, Y0 + 10)])          # 300 m east
SCHOOLS = meters([Point(X0, Y0 + 1000)])                              # 1 km north
WATER = meters([LineString([(X0 - 500, Y0 - 2000), (X0 - 500, Y0 + 2000)])])  # 500 m west
CENTERS = meters([Point(X0 + 100, Y0), Point(X0, Y0 + 200), Point(X0 + 260, Y0),
                  Point(X0 + 1000, Y0)]).geometry                     # 2 within 250 m

CANDIDATES = pd.DataFrame({"detectionId": ["a"], "lat": [35.20], "lon": [-119.40]})


def test_distances_and_counts():
    r = enrich(CANDIDATES, HOMES, SCHOOLS, WATER, CENTERS).iloc[0]
    assert abs(r["distToHomeM"] - 300) <= 2
    assert abs(r["distToSchoolM"] - 1000) <= 2
    assert abs(r["distToWaterM"] - 500) <= 2
    assert r["buildingsNear250m"] == 2


def test_inside_residential_area_is_zero():
    big_area = meters([box(X0 - 50, Y0 - 50, X0 + 50, Y0 + 50)])
    r = enrich(CANDIDATES, big_area, SCHOOLS, WATER, CENTERS).iloc[0]
    assert r["distToHomeM"] == 0


def test_reads_geoparquet(tmp_path):
    path = tmp_path / "b.parquet"
    meters([box(X0, Y0, X0 + 10, Y0 + 10)]).to_crs(4326).to_parquet(path)
    layer = read_layer(str(path))
    assert len(layer) == 1 and layer.crs.to_epsg() == METERS_CRS
