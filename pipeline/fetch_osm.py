#!/usr/bin/env python3
"""
Download OpenStreetMap layers for the study area (Step 4).

Run from the repo root:
  python pipeline/fetch_osm.py
Writes pipeline/data/osm/{homes,schools,water,buildings}.gpkg (gitignored).
Re-running skips layers that already downloaded.
"""
import argparse
import os
import time

import osmnx as ox

# (left, bottom, right, top) in lon/lat: western Kern oil fields plus Oildale/Famoso.
DEFAULT_BBOX = (-119.95, 35.00, -118.85, 35.75)

LAYERS = {
    # "homes" = residential buildings plus residential land use (not every shed in an oil field)
    "homes": {
        "building": ["house", "residential", "apartments", "detached",
                     "semidetached_house", "terrace", "bungalow", "dormitory", "farm"],
        "landuse": "residential",
    },
    "schools": {"amenity": ["school", "kindergarten", "college"]},
    "water": {"waterway": ["river", "stream", "canal"], "natural": "water"},
    # every building, stored as a center point, for "buildings within 250 m"
    "buildings": {"building": True},
}

KEEP = ("building", "landuse", "amenity", "name", "waterway", "natural")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX,
                    metavar=("LEFT", "BOTTOM", "RIGHT", "TOP"))
    ap.add_argument("--out", default=os.path.join("pipeline", "data", "osm"))
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = os.path.join(args.out, "cache")
    ox.settings.requests_timeout = 300

    for name, tags in LAYERS.items():
        path = os.path.join(args.out, f"{name}.gpkg")
        if os.path.exists(path):
            print(f"{name}: already downloaded, skipping ({path})")
            continue
        start = time.time()
        print(f"Downloading {name}... (buildings can take 5-15 minutes)", flush=True)
        if name == "buildings":
            ox.settings.max_query_area_size = 10_000 * 10_000  # ask in 10 km x 10 km pieces
        gdf = ox.features_from_bbox(tuple(args.bbox), tags)
        cols = [c for c in KEEP if c in gdf.columns]
        gdf = gdf[cols + ["geometry"]].reset_index()
        if name == "buildings":
            # store each building as its center point (computed in meters, saved as lat/lon)
            gdf["geometry"] = gdf.to_crs(3310).centroid.to_crs(4326).values
        gdf.to_file(path, driver="GPKG")
        print(f"  {name}: {len(gdf):,} features in {time.time() - start:.0f}s -> {path}")

    print("Done.")


if __name__ == "__main__":
    main()