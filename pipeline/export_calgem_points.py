#!/usr/bin/env python3
"""Export the CalGEM wells as one compact file for the Command Map's "Documented wells" layer.

Reads data/calgem/calgem_wells.jsonl (from load_calgem.py) and writes
app/public/calgem/wells.json: a single GeoJSON MultiPoint, coordinates rounded to 5 decimals.
Only wells with usable coordinates are included. Commit the output; Vercel serves it gzipped.

    python pipeline/export_calgem_points.py
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def export(src: Path, dst: Path, include_uncertain: bool) -> tuple[int, int]:
    pts: list[list[float]] = []
    skipped = 0
    with src.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            lat, lon = row.get("lat"), row.get("lon")
            ok = isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and math.isfinite(lat) and math.isfinite(lon)
            if not ok or (row.get("locationQuality") == "uncertain" and not include_uncertain):
                skipped += 1
                continue
            pts.append([round(lon, 5), round(lat, 5)])
    dst.parent.mkdir(parents=True, exist_ok=True)
    geo = {"type": "Feature", "properties": {"source": "CalGEM WellSTAR"}, "geometry": {"type": "MultiPoint", "coordinates": pts}}
    dst.write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    return len(pts), skipped


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=Path("data/calgem/calgem_wells.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("app/public/calgem/wells.json"))
    ap.add_argument("--include-uncertain", action="store_true", help="also draw wells whose CalGEM location is flagged uncertain")
    a = ap.parse_args()
    n, skipped = export(a.src, a.out, a.include_uncertain)
    print(f"Wrote {a.out}: {n} wells ({a.out.stat().st_size/1e6:.1f} MB), skipped {skipped} without a usable location")
