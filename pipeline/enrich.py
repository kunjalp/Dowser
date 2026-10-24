#!/usr/bin/env python3
"""
Step 7: enrich candidates with distances to people and water.

For each candidate (a row with lat/lon), adds:
  distToHomeM        meters to the nearest home or residential area (OSM homes layer)
  distToSchoolM      meters to the nearest school (OSM schools layer)
  distToWaterM       meters to the nearest river, stream, canal or water body (OSM water layer)
  buildingsNear250m  number of buildings within 250 m (Overture buildings layer)

Run from the repo root, after match_wells.py:
  python pipeline/enrich.py
Reads pipeline/data/matched.csv (only rows with isCandidate = True) and the layers in
pipeline/data/osm/, writes pipeline/data/enriched.csv.
"""
from __future__ import annotations

import argparse
import os

import geopandas as gpd
import pandas as pd

PROXIMITY_RADIUS_M = 250  # config value from the Master Plan
METERS_CRS = 3310         # California Albers
OSM_DIR = os.path.join("pipeline", "data", "osm")


def read_layer(path: str) -> gpd.GeoDataFrame:
    """Read a .gpkg or GeoParquet layer and project it to meters."""
    if path.endswith(".parquet"):
        try:
            g = gpd.read_parquet(path, columns=["geometry"])
        except Exception:
            # Fallback for parquet files without GeoParquet metadata: geometry stored as WKB.
            import pyarrow.parquet as pq
            import shapely
            table = pq.read_table(path, columns=["geometry"])
            g = gpd.GeoDataFrame(geometry=shapely.from_wkb(table.column("geometry").to_pylist()), crs=4326)
    else:
        g = gpd.read_file(path)[["geometry"]]
    if g.crs is None:
        g = g.set_crs(4326)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    return g.to_crs(METERS_CRS)


def nearest_distance(points: gpd.GeoDataFrame, layer: gpd.GeoDataFrame) -> pd.Series:
    """Meters from each point to the nearest feature (0 if the point is inside a polygon)."""
    pts = points[["geometry"]].copy()
    pts["_row"] = range(len(pts))
    j = gpd.sjoin_nearest(pts, layer, how="left", distance_col="_dist")
    d = j.groupby("_row")["_dist"].min()
    return d.reindex(range(len(pts))).round(0).to_numpy()


def count_within(points: gpd.GeoDataFrame, centers: gpd.GeoSeries, radius_m: float) -> list[int]:
    """How many building center points lie within radius_m of each point."""
    tree = centers.sindex
    hits = tree.query(points.geometry.buffer(radius_m), predicate="intersects")
    counts = pd.Series(hits[0]).value_counts()
    return [int(counts.get(i, 0)) for i in range(len(points))]


def enrich(df: pd.DataFrame, homes, schools, water, building_centers,
           radius_m: float = PROXIMITY_RADIUS_M) -> pd.DataFrame:
    out = df.reset_index(drop=True).copy()
    pts = gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(out["lon"], out["lat"]), crs=4326).to_crs(METERS_CRS)
    out["distToHomeM"] = nearest_distance(pts, homes)
    out["distToSchoolM"] = nearest_distance(pts, schools)
    out["distToWaterM"] = nearest_distance(pts, water)
    out["buildingsNear250m"] = count_within(pts, building_centers, radius_m)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=os.path.join("pipeline", "data", "matched.csv"))
    ap.add_argument("--out", default=os.path.join("pipeline", "data", "enriched.csv"))
    ap.add_argument("--all", action="store_true", help="enrich every row, not only candidates")
    ap.add_argument("--radius", type=float, default=PROXIMITY_RADIUS_M)
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype={"nearestDocumentedId": str, "detectionId": str})
    if not args.all and "isCandidate" in df.columns:
        df = df[df["isCandidate"].astype(str).str.lower() == "true"]
    print(f"Enriching {len(df)} rows...", flush=True)

    homes = read_layer(os.path.join(OSM_DIR, "homes.gpkg"))
    schools = read_layer(os.path.join(OSM_DIR, "schools.gpkg"))
    water = read_layer(os.path.join(OSM_DIR, "water.gpkg"))
    buildings = read_layer(os.path.join(OSM_DIR, "buildings_overture.parquet"))
    centers = buildings.geometry.centroid
    print(f"Layers: {len(homes):,} homes, {len(schools):,} schools, {len(water):,} water, "
          f"{len(buildings):,} buildings", flush=True)

    result = enrich(df, homes, schools, water, centers, args.radius)
    result.to_csv(args.out, index=False)
    near = int(((result["distToHomeM"] <= args.radius) | (result["distToSchoolM"] <= args.radius)).sum())
    print(f"Done. {len(result)} rows; {near} within {args.radius:.0f} m of a home or school.")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
