#!/usr/bin/env python3
"""
Step 3: merge duplicate detections into one row per physical well symbol.

The same well shows up several times: on overlapping tiles of one sheet, and on several
editions (years) of the same map. Detections within DEDUP_DISTANCE_M of each other
(chained: A near B near C) become one well. For each merged well we keep:
  lat, lon         confidence-weighted average position
  confidence       highest detection confidence
  editionsSeen     sorted list of distinct map years, e.g. [1947, 1962]
  detectionIds     every detection merged into it (the first one becomes detectionId)
  evidence         best crop per year as JSON [{"year": 1947, "url": "..."}]
  quadName, source carried over (most common value)

Run from the repo root, first step after Emir's detections:
  python pipeline/dedup.py --detections path/to/detections.csv
Writes pipeline/data/deduped.csv, which match_wells.py reads next.

Expected detection columns (other names in brackets are accepted too):
  lat, lon, confidence [conf, score], year [mapYear, edition],
  optional: detectionId [id], crop [cropPath, cropUrl, crop_url], tileId [tile],
            quadName [quad, sheet], source ("model" or "ground_truth")
"""
from __future__ import annotations

import argparse
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd

DEDUP_DISTANCE_M = 20  # config value from the Master Plan
METERS_CRS = 3310

ALIASES = {
    "confidence": ["confidence", "conf", "score"],
    "year": ["year", "mapYear", "map_year", "edition"],
    "detectionId": ["detectionId", "detection_id", "id"],
    "crop": ["crop", "cropPath", "cropUrl", "crop_url", "crop_path"],
    "tileId": ["tileId", "tile_id", "tile"],
    "quadName": ["quadName", "quad", "sheet", "quad_name"],
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    lower = {c.lower(): c for c in df.columns}
    for target, names in ALIASES.items():
        if target in df.columns:
            continue
        for n in names:
            if n.lower() in lower:
                df[target] = df[lower[n.lower()]]
                break
    if "lat" not in df.columns or "lon" not in df.columns:
        raise SystemExit("Detections need 'lat' and 'lon' columns.")
    if "confidence" not in df.columns:
        df["confidence"] = 1.0  # hand-labeled ground truth (agreed with Kunjal)
    if "detectionId" not in df.columns:
        df["detectionId"] = [f"det-{i:05d}" for i in range(len(df))]
    if "source" not in df.columns:
        df["source"] = "model"
    df["detectionId"] = df["detectionId"].astype(str)
    return df


def cluster_labels(points: gpd.GeoSeries, distance_m: float) -> np.ndarray:
    """Group points whose chains of neighbors are within distance_m (union-find)."""
    n = len(points)
    parent = np.arange(n)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    left, right = points.sindex.query(points.buffer(distance_m), predicate="intersects")
    for a, b in zip(left, right):
        if a != b:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
    return np.array([find(i) for i in range(n)])


def most_common(values: pd.Series):
    v = values.dropna()
    return v.mode().iloc[0] if len(v) else None


def dedup(detections: pd.DataFrame, distance_m: float = DEDUP_DISTANCE_M) -> pd.DataFrame:
    df = normalize_columns(detections).reset_index(drop=True)
    pts = gpd.GeoSeries(gpd.points_from_xy(df["lon"], df["lat"]), crs=4326).to_crs(METERS_CRS)
    df["_x"], df["_y"] = pts.x, pts.y
    df["_cluster"] = cluster_labels(pts, distance_m)

    rows = []
    for _, g in df.groupby("_cluster", sort=False):
        g = g.sort_values("confidence", ascending=False)
        w = g["confidence"].clip(lower=0.01)
        x, y = np.average(g["_x"], weights=w), np.average(g["_y"], weights=w)
        years = sorted({int(v) for v in g["year"].dropna()}) if "year" in g else []
        evidence = []
        if "crop" in g and "year" in g:
            for yr in years:
                best = g[(g["year"] == yr) & g["crop"].notna()]
                if len(best):
                    evidence.append({"year": yr, "url": str(best.iloc[0]["crop"])})
        rows.append({
            "_x": x, "_y": y,
            "detectionId": g.iloc[0]["detectionId"],
            "detectionIds": ";".join(g["detectionId"]),
            "confidence": round(float(g["confidence"].max()), 4),
            "editionsSeen": json.dumps(years),
            "evidence": json.dumps(evidence),
            "quadName": most_common(g["quadName"]) if "quadName" in g else None,
            "source": most_common(g["source"]),
            "nDetections": len(g),
        })

    out = pd.DataFrame(rows)
    ll = gpd.GeoSeries(gpd.points_from_xy(out["_x"], out["_y"]), crs=METERS_CRS).to_crs(4326)
    out.insert(0, "lat", ll.y.round(6))
    out.insert(1, "lon", ll.x.round(6))
    return out.drop(columns=["_x", "_y"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detections", required=True)
    ap.add_argument("--distance", type=float, default=DEDUP_DISTANCE_M)
    ap.add_argument("--out", default=os.path.join("pipeline", "data", "deduped.csv"))
    args = ap.parse_args()

    if args.detections.lower().endswith((".geojson", ".json", ".gpkg")):
        g = gpd.read_file(args.detections).to_crs(4326)
        raw = pd.DataFrame(g.drop(columns="geometry"))
        raw["lat"], raw["lon"] = g.geometry.y, g.geometry.x
    else:
        raw = pd.read_csv(args.detections, dtype={"detectionId": str, "id": str})

    result = dedup(raw, args.distance)
    result.to_csv(args.out, index=False)
    multi = int((result["editionsSeen"].map(lambda s: len(json.loads(s))) > 1).sum())
    print(f"Detections in: {len(raw)}   Unique wells out: {len(result)}   "
          f"Seen on 2+ editions: {multi}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
