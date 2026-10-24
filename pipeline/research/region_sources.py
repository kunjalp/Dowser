#!/usr/bin/env python3
"""Reproduce region-selection source probes; cache responses outside Git.

Reads public USGS/CalGEM APIs and writes only under data/research/. This is
research tooling, not a detector, dataset builder, or backend ingestion client.
Bounding boxes always use WGS84 (west, south, east, north).
"""

import argparse
import concurrent.futures
import csv
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CACHE = Path(__file__).resolve().parents[2] / "data" / "research"
FORCE_REFRESH = False
TNM = "https://tnmaccess.nationalmap.gov/api/v1/products"
WELLS = "https://gis.conservation.ca.gov/server/rest/services/WellSTAR/Wells/MapServer/0"
REGIONS = {
    "kern_river": [-119.125, 35.375, -118.875, 35.5],
    "taft": [-119.5, 35.0, -119.25, 35.25],
    "mckittrick": [-119.75, 35.25, -119.5, 35.5],
    "la_west": [-118.5, 33.875, -118.25, 34.125],
    "signal_hill": [-118.25, 33.75, -118.125, 33.875],
}


def fetch_json(label, endpoint, params):
    """Cache a public JSON response with query URL, UTC time, and checksum."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (label + ".json")
    url = endpoint + "?" + urllib.parse.urlencode(params)
    if path.exists() and not FORCE_REFRESH:
        cached = json.loads(path.read_text())
        if cached["url"] == url:
            return cached["response"]
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Dowser-region-research/1.0"})
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("error"):
                raise ValueError(data["error"])
            path.write_text(json.dumps({
                "url": url,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "response_sha256": hashlib.sha256(raw).hexdigest(),
                "response": data,
            }, indent=2))
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1)


def catalog(name):
    """Summarize symbol-era 1:24k catalog editions with positive-area overlap."""
    bbox = REGIONS[name]
    data = fetch_json("usgs_" + name, TNM, {
        "datasets": "Historical Topographic Maps",
        "bbox": ",".join(map(str, bbox)), "max": 1000,
    })
    if len(data["items"]) < data["total"]:
        raise ValueError("Catalog pagination required; do not report incomplete results")
    maps = []
    for item in data["items"]:
        match = re.search(r"1:(\d+)-scale Quadrangle for (.+), CA (\d{4})$", item["title"])
        if not match or int(match[1]) != 24000 or not 1947 <= int(match[3]) <= 1992:
            continue
        bounds = item["boundingBox"]
        # Catalog spatial intersection includes touching neighbors; discard them.
        if not (bounds["minX"] < bbox[2] and bounds["maxX"] > bbox[0]
                and bounds["minY"] < bbox[3] and bounds["maxY"] > bbox[1]):
            continue
        maps.append(item)
    groups = {}
    for item in maps:
        match = re.search(r"Quadrangle for (.+), CA (\d{4})$", item["title"])
        groups.setdefault(match[1], set()).add(int(match[2]))
    return {"region": name, "total_catalog_items": data["total"],
            "eligible_editions": len(maps),
            "quadrangle_years": {k: sorted(v) for k, v in groups.items()}}


def wells(name):
    """Count mapped reference records of all statuses, not undocumented wells."""
    data = fetch_json("calgem_count_" + name, WELLS + "/query", {
        "f": "json", "where": "1=1", "geometry": ",".join(map(str, REGIONS[name])),
        "geometryType": "esriGeometryEnvelope", "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "returnCountOnly": "true",
    })
    return {"region": name, "bbox": REGIONS[name], "documented_record_count": data["count"]}


def edx():
    """Retrieve publisher metadata and small artifacts; never execute their code."""
    data = fetch_json("edx_package", "https://edx.netl.doe.gov/api/3/action/package_show", {
        "id": "u-net-based-usgs-quadrangles-oil-and-gas-well-symbols-identification",
    })
    if not data.get("success"):
        raise ValueError("EDX did not return the dataset")
    allowed = {"readme.pdf", "requirements.txt", "predict.ipynb",
               "CA_OilCenter_293661_1954_24000_geo.xml",
               "CA_OilCenter_293661_1954_24000_geo_detected.json",
               "CA_OilCenter_293661_1954_24000_geo_UOWs.csv"}
    target_dir = CACHE / "edx"
    target_dir.mkdir(exist_ok=True)
    resources = []
    for resource in data["result"]["resources"]:
        name = resource["name"]
        record = {k: resource.get(k) for k in ["name", "url", "size", "format"]}
        if name in allowed:
            if resource.get("size", 0) > 200000:
                raise ValueError("Unexpected resource size")
            target = target_dir / name
            if not target.exists() or FORCE_REFRESH:
                with urllib.request.urlopen(resource["url"], timeout=45) as response:
                    raw = response.read(200001)
                if len(raw) > 200000:
                    raise ValueError("Unexpected resource body size")
                target.write_bytes(raw)
            record["local_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        resources.append(record)
    return {"dataset_doi": "10.18141/2452768", "resources": resources}


def published_candidates():
    """Recheck attributed published candidates; this is not new model inference."""
    from pyproj import Geod

    edx()
    path = CACHE / "edx" / "CA_OilCenter_293661_1954_24000_geo_UOWs.csv"
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    geod = Geod(ellps="WGS84")
    result = []
    for row in rows:
        lat, lon = map(float, row["Well Coords"].split(","))
        data = fetch_json("edx_candidate_near_" + row["Well Id"], WELLS + "/query", {
            "f": "json", "where": "1=1", "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint", "inSR": 4326,
            "distance": 1000, "units": "esriSRUnit_Meter", "outSR": 4326,
            "outFields": "API,WellStatus,Latitude,Longitude,GISSource,FieldName",
            "returnGeometry": "true", "resultRecordCount": 5000,
        })
        if data.get("exceededTransferLimit"):
            raise ValueError("Candidate-neighborhood query requires pagination")
        distances = []
        for feature in data.get("features", []):
            geom = feature.get("geometry")
            if geom:
                _, _, meters = geod.inv(lon, lat, geom["x"], geom["y"])
                distances.append((meters, feature["attributes"]["API"],
                                  feature["attributes"]["WellStatus"]))
        nearest = min(distances) if distances else None
        result.append({"published_id": row["Well Id"], "lat": lat, "lon": lon,
                       "published_distance_m": int(row["Distance to closest documented (m)"]),
                       "nearest_current": nearest,
                       "current_records_within_100m": sum(d[0] <= 100 for d in distances)})
    detections = json.loads((CACHE / "edx" /
        "CA_OilCenter_293661_1954_24000_geo_detected.json").read_text())
    return {"provenance": "Published Ciulla et al. outputs, not Dowser detections or ground truth",
            "published_detections": len(detections["detected"]), "candidates": result}


def main():
    global FORCE_REFRESH
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["catalog", "wells", "edx", "published"])
    parser.add_argument("--region", choices=list(REGIONS), action="append")
    parser.add_argument("--refresh", action="store_true", help="refetch rather than reuse dated research cache")
    args = parser.parse_args()
    FORCE_REFRESH = args.refresh
    if args.mode in {"edx", "published"}:
        print(json.dumps(edx() if args.mode == "edx" else published_candidates(), indent=2))
        return
    task = catalog if args.mode == "catalog" else wells
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for result in pool.map(task, args.region or REGIONS):
            print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
