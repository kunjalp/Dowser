#!/usr/bin/env python3
"""
Second data lane: wells the STATE already knows about, listed as Idle in CalGEM, that sit
within 250 m of a home or school. These are real records, not map detections, and the app
keeps them apart from the undocumented candidates everywhere.

  select    CalGEM wells with status Idle and a good location, inside the OSM study box
            (the area enrich.py's layers cover; see fetch_osm.py DEFAULT_BBOX)
  enrich    the same enrich() as enrich.py: distToHomeM, distToSchoolM, distToWaterM, buildingsNear250m
  keep      only wells within 250 m of a home or a school
  score     score.py's score_parts() and weighted_score(), with undocumented = 0 (it is in the
            records) and confidence = 1.0 (it is a known well, not a guessed symbol)

Records use the normal candidate format with id "idle-<API number>" and source "calgem_idle",
plus wellStatus, operator and apiNumber. No evidence images.

Run from the repo root, after load_calgem.py and fetch_osm.py:
  python pipeline/idle_wells.py --dry-run     # only writes pipeline/data/idle_candidates.json
  python pipeline/idle_wells.py               # loads into YOUR dev deployment
  python pipeline/idle_wells.py --prod        # loads into the SHARED deployment the team sees
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from enrich import OSM_DIR, PROXIMITY_RADIUS_M, enrich, read_layer  # noqa: E402
from load_candidates import BATCH_SIZE, PART_KEYS, _num, _str, send  # noqa: E402
from score import score_parts, weighted_score  # noqa: E402

# Same box as fetch_osm.py DEFAULT_BBOX (not imported: that module needs osmnx).
# The OSM layers stop at its edges, so distances outside it would be wrong.
STUDY_BOX = (-119.95, 35.00, -118.85, 35.75)
SOURCE = "calgem_idle"
QUAD_DEG = 0.125  # USGS 7.5-minute quadrangles sit on a regular 1/8-degree grid
FALLBACK_QUAD = "Kern County"  # same default as load_candidates.py


def select_idle(wells: pd.DataFrame, box=STUDY_BOX) -> pd.DataFrame:
    """Idle wells with a usable location inside the box."""
    w = wells[(wells["status"] == "Idle") & (wells["locationQuality"] == "good")]
    w = w[w["lon"].between(box[0], box[2]) & w["lat"].between(box[1], box[3])]
    return w.reset_index(drop=True)


def near_people(df: pd.DataFrame, radius_m: float = PROXIMITY_RADIUS_M) -> pd.DataFrame:
    """Rows within radius_m of a home or a school (a missing distance counts as far)."""
    keep = (df["distToHomeM"] <= radius_m) | (df["distToSchoolM"] <= radius_m)
    return df[keep.fillna(False)].reset_index(drop=True)


def quad_cell(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / QUAD_DEG), math.floor(lon / QUAD_DEG)


def quad_names(detections: pd.DataFrame) -> dict[tuple[int, int], str]:
    """Quad name per 7.5-minute grid cell, learned from the detections we already have
    (each tile carries its sheet name). Most common name wins at sheet edges."""
    votes: dict[tuple[int, int], Counter] = {}
    for lat, lon, name in detections[["lat", "lon", "quadName"]].itertuples(index=False):
        if isinstance(name, str) and name:
            votes.setdefault(quad_cell(lat, lon), Counter())[name] += 1
    return {cell: c.most_common(1)[0][0] for cell, c in votes.items()}


def idle_parts(row: pd.Series) -> dict:
    parts = score_parts(row)
    parts["undocumented"] = 0.0
    parts["confidence"] = 1.0
    return parts


def to_idle_candidate(row: pd.Series, names: dict[tuple[int, int], str] | None = None) -> dict:
    """One enriched CalGEM row -> one candidate record in the agreed format."""
    api = str(row["apiNumber"])
    parts = idle_parts(row)
    lat, lon = float(row["lat"]), float(row["lon"])
    doc = {
        "id": f"idle-{api}",
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "score": round(weighted_score(parts), 4),
        "scoreParts": {k: round(parts[k], 4) for k in PART_KEYS},
        "editionsSeen": [],
        "status": "candidate",
        "evidenceImages": [],
        "quadName": (names or {}).get(quad_cell(lat, lon), FALLBACK_QUAD),
        "source": SOURCE,
        "wellStatus": _str(row.get("status")) or "Idle",
        "apiNumber": api,
    }
    if _str(row.get("operator")):
        doc["operator"] = _str(row.get("operator"))
    for k in ("distToHomeM", "distToSchoolM", "distToWaterM", "buildingsNear250m"):
        v = _num(row.get(k))
        if v is not None:
            doc[k] = int(v) if k == "buildingsNear250m" else round(v, 1)
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calgem", default=os.path.join("pipeline", "data", "calgem", "calgem_wells.jsonl"))
    ap.add_argument("--detections", default=os.path.join("pipeline", "data", "detections.csv"),
                    help="used only to name quads from location")
    ap.add_argument("--json-out", default=os.path.join("pipeline", "data", "idle_candidates.json"))
    ap.add_argument("--prod", action="store_true", help="load into the shared production deployment")
    ap.add_argument("--dry-run", action="store_true", help="write the JSON file only, send nothing")
    args = ap.parse_args()

    with open(args.calgem) as fh:
        wells = pd.DataFrame(json.loads(line) for line in fh)  # apiNumber stays a string
    idle = select_idle(wells)
    print(f"Idle wells in the study box: {len(idle)}", flush=True)

    homes = read_layer(os.path.join(OSM_DIR, "homes.gpkg"))
    schools = read_layer(os.path.join(OSM_DIR, "schools.gpkg"))
    water = read_layer(os.path.join(OSM_DIR, "water.gpkg"))
    buildings = read_layer(os.path.join(OSM_DIR, "buildings_overture.parquet"))
    near = near_people(enrich(idle, homes, schools, water, buildings.geometry.centroid))
    n_school = int((near["distToSchoolM"] <= PROXIMITY_RADIUS_M).sum())
    print(f"Within {PROXIMITY_RADIUS_M} m of a home or school: {len(near)}  "
          f"(within {PROXIMITY_RADIUS_M} m of a school: {n_school})")

    names = quad_names(pd.read_csv(args.detections)) if os.path.exists(args.detections) else {}
    candidates = sorted((to_idle_candidate(r, names) for _, r in near.iterrows()),
                        key=lambda c: c["score"], reverse=True)
    ids = [c["id"] for c in candidates]
    if len(ids) != len(set(ids)):
        sys.exit("Duplicate idle ids; check that API numbers are unique.")
    named = sum(c["quadName"] != FALLBACK_QUAD for c in candidates)
    print(f"Quad named from location: {named} of {len(candidates)} (rest: {FALLBACK_QUAD!r})")
    with open(args.json_out, "w") as fh:
        json.dump(candidates, fh, indent=1)
    print(f"Prepared {len(candidates)} idle wells -> {args.json_out}")
    if args.dry_run:
        return

    target = "PROD (shared)" if args.prod else "your dev deployment"
    for i in range(0, len(candidates), BATCH_SIZE):
        out = send(candidates[i:i + BATCH_SIZE], args.prod)
        print(f"  batch {i // BATCH_SIZE + 1}: {out}")
    print(f"Loaded {len(candidates)} idle wells into {target}.")


if __name__ == "__main__":
    main()
