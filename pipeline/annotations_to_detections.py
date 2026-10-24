#!/usr/bin/env python3
"""
Turn Emir's hand-labeled well symbols into a detections CSV for the existing pipeline.

Why: the model finds many false symbols (text, tanks, signs). The labeled boxes are real
well symbols a person drew on the USGS tiles, so they make a trustworthy candidate set.
Every row is marked source=ground_truth with confidence 1.0, which the app shows as
"hand-labeled" (it is NOT a model score). Nothing here is invented: every row is a box
from the label files, converted from tile pixels to lat/lon with Emir's pipeline/geo.py.

Inputs (all on Emir's laptop, under data/ml/, which git ignores):
  --manifest  data/ml/kern_1024_v2/manifest.jsonl   (tileId, mapYear, sheetName, transform, crs, size)
  --labels    a folder of YOLO .txt files named <tileId>.txt (searched recursively).
              Repeat the flag for more folders. Add ":assistant" to a folder if its labels
              were drawn by the assistant and not a person, e.g. path:assistant
  --images    (optional) folder of the tile PNGs, searched recursively, to cut evidence crops

Run from the repo root (needs pipeline/geo.py from Emir's branch, plus pyproj, affine, pillow):
  python pipeline/annotations_to_detections.py \\
      --manifest data/ml/kern_1024_v2/manifest.jsonl \\
      --labels data/ml/reviewed_v2/labels \\
      --labels data/ml/reviewed_validation_v1/labels \\
      --images data/ml/kern_1024_v2/images --crops pipeline/data/gt_crops

Then the normal pipeline, unchanged:
  python pipeline/dedup.py --detections pipeline/data/detections_groundtruth.csv
  python pipeline/match_wells.py && python pipeline/enrich.py && python pipeline/score.py
  python pipeline/load_candidates.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

CROP_PX = 160  # square crop around the symbol, in tile pixels
OUT_FIELDS = ["detectionId", "tileId", "quadName", "year", "lat", "lon", "confidence", "source", "labelSource", "crop"]


def parse_yolo(text: str, width: int, height: int):
    """YOLO rows 'class cx cy w h' (normalized) -> top-left pixel boxes. Skips blank lines."""
    boxes = []
    for n, row in enumerate(text.splitlines(), 1):
        if not row.strip():
            continue
        vals = row.split()
        if len(vals) != 5:
            raise ValueError(f"row {n}: expected 5 values, got {len(vals)}")
        cls, cx, cy, w, h = (float(v) for v in vals)
        if cls != 0 or w <= 0 or h <= 0:
            raise ValueError(f"row {n}: wrong class or empty box")
        left = max(0.0, (cx - w / 2) * width)
        top = max(0.0, (cy - h / 2) * height)
        right = min(float(width), (cx + w / 2) * width)
        bottom = min(float(height), (cy + h / 2) * height)
        if right <= left or bottom <= top:
            raise ValueError(f"row {n}: box outside the tile")
        boxes.append({"row": n, "x": left, "y": top, "w": right - left, "h": bottom - top})
    return boxes


def load_manifest(path: str) -> dict:
    tiles = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                t = json.loads(line)
                tiles[t["tileId"]] = t
    return tiles


def find_files(root: str, suffix: str) -> dict:
    return {p.stem: p for p in Path(root).rglob(f"*{suffix}")}


def make_crop(image_path: Path, box: dict, out_path: Path) -> bool:
    from PIL import Image

    with Image.open(image_path) as im:
        cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
        half = CROP_PX / 2
        left = int(max(0, min(im.width - CROP_PX, cx - half)))
        top = int(max(0, min(im.height - CROP_PX, cy - half)))
        im.crop((left, top, left + CROP_PX, top + CROP_PX)).convert("RGB").save(out_path)
    return True


def convert(manifest, label_dirs, images_dir, crops_dir, allow_assistant):
    from pipeline.geo import box_center_to_wgs84

    images = find_files(images_dir, ".png") if images_dir else {}
    rows, skipped = [], []
    for spec in label_dirs:
        path, _, source = spec.partition(":")
        source = source or "human"
        if source == "assistant" and not allow_assistant:
            print(f"skipping {path}: assistant labels need --include-assistant", file=sys.stderr)
            continue
        for tile_id, label_file in sorted(find_files(path, ".txt").items()):
            tile = manifest.get(tile_id)
            if tile is None:
                skipped.append((tile_id, "tile not in manifest"))
                continue
            boxes = parse_yolo(label_file.read_text(), tile["widthPx"], tile["heightPx"])
            for box in boxes:
                try:
                    pos = box_center_to_wgs84(tile, box)
                except ValueError as e:
                    skipped.append((tile_id, str(e)))
                    continue
                det_id = f"gt_{tile_id}_{box['row']:03d}"
                crop = ""
                if crops_dir and tile_id in images:
                    out = Path(crops_dir) / f"{det_id}.png"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    make_crop(images[tile_id], box, out)
                    crop = str(out)
                rows.append({
                    "detectionId": det_id, "tileId": tile_id, "quadName": tile.get("sheetName", ""),
                    "year": tile["mapYear"], "lat": round(pos["lat"], 7), "lon": round(pos["lon"], 7),
                    "confidence": 1.0, "source": "ground_truth", "labelSource": source, "crop": crop,
                })
    return rows, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--labels", action="append", required=True, help="folder of YOLO txt files; add :assistant if not human")
    ap.add_argument("--images")
    ap.add_argument("--crops", default=os.path.join("pipeline", "data", "gt_crops"))
    ap.add_argument("--out", default=os.path.join("pipeline", "data", "detections_groundtruth.csv"))
    ap.add_argument("--include-assistant", action="store_true", help="also use folders marked :assistant")
    args = ap.parse_args()

    manifest = load_manifest(args.manifest)
    rows, skipped = convert(manifest, args.labels, args.images, args.crops if args.images else None, args.include_assistant)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    by_source = {}
    for r in rows:
        by_source[r["labelSource"]] = by_source.get(r["labelSource"], 0) + 1
    print(f"wrote {len(rows)} ground-truth detections to {args.out} {by_source}")
    for tile_id, why in skipped[:10]:
        print(f"  skipped {tile_id}: {why}", file=sys.stderr)
    if skipped:
        print(f"  {len(skipped)} boxes skipped in total", file=sys.stderr)


if __name__ == "__main__":
    main()
