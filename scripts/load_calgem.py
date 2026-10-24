#!/usr/bin/env python3
"""
FR-4.1: load CalGEM's WellSTAR well records for one region into local files.

Outputs (in --out, default ./data/calgem):
  calgem_wells.jsonl    one documentedWells row per line, ready for:
                          npx convex import --table documentedWells --replace data/calgem/calgem_wells.jsonl
  calgem_wells.geojson  wells with usable coordinates (local geospatial format)
  bad_rows.log          every row that was flagged or dropped, with the reason

Prints the row count and bounding box when done (FR-4.1 acceptance criterion).

Sources (pick one):
  default   ArcGIS REST query on CalGEM's WellSTAR Wells layer, filtered to the region bbox
  --csv     a CSV you downloaded from data.ca.gov ("WellSTAR: Oil and Gas Wells")

Run with --inspect first: it prints the source's real field names, because the
column mapping below is a best guess and has not been checked against live data.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from typing import Any, Iterable, Iterator

LAYER_URL = "https://gis.conservation.ca.gov/server/rest/services/WellSTAR/Wells/MapServer/0"

# (minLon, minLat, maxLon, maxLat), WGS84. Approximate; PRD 8.8 says decide at check-in.
REGIONS = {
    "kern": (-120.19, 34.79, -117.63, 35.80),
    "la_basin": (-118.67, 33.65, -117.65, 34.35),
}

# Sanity box for California; anything outside is a bad coordinate (0,0, swapped, etc).
CA_BOX = (-124.6, 32.4, -114.0, 42.1)

# Candidate source column names, lowercase, first match wins.
FIELD_CANDIDATES = {
    "api": ["api", "apinumber", "api_number", "apino"],
    "lat": ["latitude", "lat", "y"],
    "lon": ["longitude", "lon", "lng", "x"],
    "status": ["wellstatus", "well_status", "status", "statuscode"],
    "type": ["welltype", "well_type", "type", "wellsymbol"],
    "operator": ["operatorname", "operator", "opername", "operator_name"],
}

MIN_DECIMALS = 4  # roughly 10 m; fewer decimals means a rounded/centroid location


def pick(row: dict[str, Any], key: str) -> Any:
    lowered = {k.lower(): v for k, v in row.items()}
    for name in FIELD_CANDIDATES[key]:
        if name in lowered and lowered[name] not in (None, ""):
            return lowered[name]
    return None


def to_float(x: Any) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def decimals(x: Any) -> int:
    s = str(x)
    if "e" in s.lower():
        return 99
    return len(s.split(".", 1)[1]) if "." in s else 0


def normalize(row: dict[str, Any], geom: dict[str, Any] | None, api_pad: int):
    """Return (doc, reason). reason is None for a clean row, else why it was flagged.
    doc is None only when the row has no usable API number."""
    api_raw = pick(row, "api")
    if api_raw is None:
        return None, "missing api"
    api = "".join(ch for ch in str(api_raw).split(".")[0] if ch.isdigit())
    if not api:
        return None, f"unparseable api {api_raw!r}"
    api = api.zfill(api_pad)

    lat_raw, lon_raw = pick(row, "lat"), pick(row, "lon")
    if (lat_raw is None or lon_raw is None) and geom:
        lon_raw, lat_raw = geom.get("x"), geom.get("y")
    lat, lon = to_float(lat_raw), to_float(lon_raw)

    doc: dict[str, Any] = {
        "apiNumber": api,
        "status": str(pick(row, "status") or "Unknown"),
        "locationQuality": "good",
    }
    if (t := pick(row, "type")) is not None:
        doc["wellType"] = str(t)
    if (o := pick(row, "operator")) is not None:
        doc["operator"] = str(o)

    reason = None
    if lat is None or lon is None:
        reason = "missing coordinates"
    elif lat == 0 or lon == 0:
        reason = "zero coordinate"
    elif not (CA_BOX[0] <= lon <= CA_BOX[2] and CA_BOX[1] <= lat <= CA_BOX[3]):
        reason = f"outside California ({lat}, {lon})"
    elif decimals(lat_raw) < MIN_DECIMALS or decimals(lon_raw) < MIN_DECIMALS:
        reason = f"low-precision coordinates ({lat_raw}, {lon_raw})"

    if reason:
        doc["locationQuality"] = "uncertain"  # FR-4.5: kept, flagged, excluded from matching
    else:
        doc["lat"], doc["lon"] = lat, lon
    return doc, reason


def in_bbox(doc: dict[str, Any], bbox: tuple[float, float, float, float]) -> bool:
    return (
        bbox[0] <= doc["lon"] <= bbox[2] and bbox[1] <= doc["lat"] <= bbox[3]
    )


# ---------- sources ----------

def fetch_arcgis(layer_url: str, bbox, page_size: int | None = None) -> Iterator[tuple[dict, dict | None]]:
    import requests

    meta = requests.get(layer_url, params={"f": "json"}, timeout=60).json()
    if "error" in meta:
        sys.exit(f"ArcGIS error reading layer metadata: {meta['error']}")
    page = page_size or int(meta.get("maxRecordCount", 1000))
    params = {
        "where": "1=1",
        "geometry": ",".join(str(v) for v in bbox),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": 4326,
        "orderByFields": "OBJECTID",
        "f": "json",
    }
    offset = 0
    while True:
        r = requests.get(
            layer_url + "/query",
            params={**params, "resultOffset": offset, "resultRecordCount": page},
            timeout=120,
        ).json()
        if "error" in r:
            sys.exit(f"ArcGIS query error: {r['error']}")
        feats = r.get("features", [])
        for f in feats:
            yield f.get("attributes", {}), f.get("geometry")
        if not feats or not r.get("exceededTransferLimit"):
            return
        offset += len(feats)
        time.sleep(0.2)


def read_csv(path: str) -> Iterator[tuple[dict, None]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            yield row, None


def inspect(source: Iterable[tuple[dict, Any]]) -> None:
    for i, (row, geom) in enumerate(source):
        if i == 0:
            print("Fields found:")
            for k, v in row.items():
                print(f"  {k!r:28} e.g. {v!r}")
            print("geometry:", geom)
            print("\nMapping guess:")
            for key in FIELD_CANDIDATES:
                print(f"  {key:9} <- {pick(row, key)!r}")
        if i >= 2:
            break


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--region", choices=sorted(REGIONS), default="kern")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("MINLON", "MINLAT", "MAXLON", "MAXLAT"),
                    help="override the region bounding box")
    ap.add_argument("--csv", help="read a downloaded CSV instead of querying ArcGIS")
    ap.add_argument("--layer-url", default=LAYER_URL)
    ap.add_argument("--out", default=os.path.join("data", "calgem"))
    ap.add_argument("--api-pad", type=int, default=8,
                    help="zero-pad API numbers to this many digits (CalGEM's field is numeric; 8 is an assumption)")
    ap.add_argument("--inspect", action="store_true", help="print source field names and exit")
    args = ap.parse_args()

    bbox = tuple(args.bbox) if args.bbox else REGIONS[args.region]
    source = read_csv(args.csv) if args.csv else fetch_arcgis(args.layer_url, bbox)

    if args.inspect:
        inspect(source)
        return

    os.makedirs(args.out, exist_ok=True)
    seen: set[str] = set()
    good = uncertain = dropped = outside = dupes = 0
    min_lon = min_lat = math.inf
    max_lon = max_lat = -math.inf

    with open(os.path.join(args.out, "calgem_wells.jsonl"), "w") as jl, \
         open(os.path.join(args.out, "bad_rows.log"), "w") as bad:
        features = []
        for row, geom in source:
            doc, reason = normalize(row, geom, args.api_pad)
            if doc is None:
                dropped += 1
                bad.write(f"DROPPED\t{reason}\t{json.dumps(row, default=str)[:300]}\n")
                continue
            if doc["apiNumber"] in seen:
                dupes += 1
                bad.write(f"DUPLICATE\t{doc['apiNumber']}\n")
                continue
            if doc["locationQuality"] == "good" and args.csv and not in_bbox(doc, bbox):
                outside += 1  # CSV is statewide; ArcGIS is already filtered server-side
                continue
            seen.add(doc["apiNumber"])
            if reason:
                bad.write(f"UNCERTAIN\t{doc['apiNumber']}\t{reason}\n")
            jl.write(json.dumps(doc) + "\n")
            if doc["locationQuality"] == "good":
                good += 1
                min_lon, max_lon = min(min_lon, doc["lon"]), max(max_lon, doc["lon"])
                min_lat, max_lat = min(min_lat, doc["lat"]), max(max_lat, doc["lat"])
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [doc["lon"], doc["lat"]]},
                    "properties": {k: v for k, v in doc.items() if k not in ("lat", "lon")},
                })
            else:
                uncertain += 1

    with open(os.path.join(args.out, "calgem_wells.geojson"), "w") as gj:
        json.dump({"type": "FeatureCollection", "features": features}, gj)

    print(f"Region bbox (query): {bbox}")
    print(f"Rows written: {good + uncertain}  (good: {good}, uncertain location: {uncertain})")
    print(f"Dropped (no API): {dropped}   Duplicates: {dupes}   Outside region (CSV only): {outside}")
    if good:
        print(f"Bounding box of good wells: lon {min_lon:.4f}..{max_lon:.4f}, lat {min_lat:.4f}..{max_lat:.4f}")
    print(f"Details: {os.path.join(args.out, 'bad_rows.log')}")
    if good + uncertain == 0:
        sys.exit("No rows loaded. Run with --inspect and check the field mapping / region.")


if __name__ == "__main__":
    main()
