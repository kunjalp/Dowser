#!/usr/bin/env python3
"""
Step 6: match detected well symbols to documented CalGEM wells.

For each detection: find the nearest documented well and its distance in meters.
If no documented well is within CROSS_CHECK_RADIUS_M, the detection is a candidate.
Every CalGEM well with a good location counts as documented, including "Canceled"
(the cautious choice: any record nearby means we do not call it undocumented).

Run from the repo root:
  python pipeline/match_wells.py --detections path/to/detections.csv
Detections file: CSV or GeoJSON with at least `lat` and `lon` columns (other columns are kept).
Writes pipeline/data/matched.csv by default.
"""
from __future__ import annotations

import argparse
import os

import geopandas as gpd
import pandas as pd

CROSS_CHECK_RADIUS_M = 100  # config value from the Master Plan
METERS_CRS = 3310           # California Albers
DEFAULT_WELLS = os.path.join("pipeline", "data", "calgem", "calgem_wells.geojson")


def load_documented(path: str = DEFAULT_WELLS) -> gpd.GeoDataFrame:
    """Documented wells with good locations, projected to meters."""
    wells = gpd.read_file(path)
    keep = [c for c in ("apiNumber", "status") if c in wells.columns]
    return wells[keep + ["geometry"]].to_crs(METERS_CRS)


def to_points(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Turn a table with lat/lon columns into points in meters."""
    pts = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    return pts.to_crs(METERS_CRS)


def match(detections: pd.DataFrame, wells: gpd.GeoDataFrame,
          radius_m: float = CROSS_CHECK_RADIUS_M) -> pd.DataFrame:
    """Add nearestDocumentedId, nearestDocumentedDistM and isCandidate to each detection."""
    pts = to_points(detections).reset_index(drop=True)
    pts["_row"] = range(len(pts))
    joined = gpd.sjoin_nearest(pts, wells, how="left", distance_col="_dist")
    joined = joined.sort_values("_dist").drop_duplicates("_row").sort_values("_row")  # ties: keep one
    out = detections.reset_index(drop=True).copy()
    out["nearestDocumentedId"] = joined["apiNumber"].values
    out["nearestDocumentedDistM"] = joined["_dist"].round(1).values
    out["nearestDocumentedStatus"] = joined["status"].values if "status" in joined else None
    out["isCandidate"] = out["nearestDocumentedDistM"] > radius_m
    return out


def read_detections(path: str) -> pd.DataFrame:
    if path.lower().endswith((".geojson", ".json", ".gpkg")):
        g = gpd.read_file(path).to_crs(4326)
        df = pd.DataFrame(g.drop(columns="geometry"))
        if "lat" not in df or "lon" not in df:
            df["lat"], df["lon"] = g.geometry.y, g.geometry.x
        return df
    return pd.read_csv(path, dtype={"detectionId": str})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detections", required=True)
    ap.add_argument("--wells", default=DEFAULT_WELLS)
    ap.add_argument("--radius", type=float, default=CROSS_CHECK_RADIUS_M)
    ap.add_argument("--out", default=os.path.join("pipeline", "data", "matched.csv"))
    args = ap.parse_args()

    result = match(read_detections(args.detections), load_documented(args.wells), args.radius)
    result.to_csv(args.out, index=False)
    n = len(result)
    c = int(result["isCandidate"].sum())
    print(f"Detections: {n}   Candidates (no record within {args.radius:.0f} m): {c}   "
          f"Matched to a record: {n - c}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
