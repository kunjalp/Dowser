"""Turn attributed published points into TRAIN-ONLY boxes for human review.

This does not run a model, create ground truth, or train YOLO. Box sizes are
heuristic, not measurements. Keep the output separate from reviewed annotations.
"""

import argparse
import hashlib
import html
import json
import math
import platform
import shutil
import subprocess
import zipfile
from pathlib import Path

from affine import Affine

from pipeline.geo import transformer
from pipeline.prepare_dataset import ROOT


MAP_ID = "usgs_293661"
MAP_SHA = "23120004b243dd4def565924678d75088b8df9f77d39e843c5029be747e57da1"
POINTS_SHA = "87c2ec22f1b38068be568fb58425c5ed769c11cc16ef640637af50f6863dc6d5"
SOURCE_DOI = "https://doi.org/10.18141/2452768"


def point_boxes(tile, predictions, radius=8):
    """Project published lat/lon centers into one exact-source training tile.

    Return clipped native-pixel xywh proposals with source IDs, never confidence.
    The publisher's second value is nearest-record distance in meters. Refuse
    validation/test/buffer tiles, wrong source identity, and invalid geometry.
    """
    if tile["split"] != "train":
        raise ValueError("Published proposals are restricted to training tiles")
    if tile["source_map_id"] != MAP_ID or tile["source_sha256"] != MAP_SHA:
        raise ValueError("Published points belong only to the pinned Oil Center 1954 raster")
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError("Box radius must be finite and positive")
    op, _ = transformer("EPSG:4326", tile["crs"])
    inverse = ~Affine(*tile["transform"])
    boxes = []
    for key, (latlon, distance) in predictions.items():
        lat, lon = latlon
        if not all(math.isfinite(v) for v in [lat, lon, distance]):
            raise ValueError("Nonfinite published point")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or distance < 0:
            raise ValueError("Invalid published coordinates/distance")
        x, y = inverse * op.transform(lon, lat, errcheck=True)
        if not (0 <= x < tile["widthPx"] and 0 <= y < tile["heightPx"]):
            continue
        left, top = max(0, x-radius), max(0, y-radius)
        right, bottom = min(tile["widthPx"], x+radius), min(tile["heightPx"], y+radius)
        boxes.append({"published_id": key, "x": left, "y": top,
                      "w": right-left, "h": bottom-top,
                      "published_nearest_record_distance_m": distance,
                      "review_status": "unreviewed"})
    return boxes


def select_tiles(candidates, count):
    """Greedily maximize new published IDs in training-only review examples."""
    selected, seen = [], set()
    remaining = list(candidates)
    while remaining and len(selected) < count:
        best = min(remaining, key=lambda item: (
            -len({b["published_id"] for b in item[1]}-seen), item[0]["tileId"]))
        remaining.remove(best)
        if not best[1]:
            continue
        selected.append(best)
        seen.update(b["published_id"] for b in best[1])
    return selected


def prepare(dataset, predictions_path, output, count=4, radius=8):
    """Write a separate preview/import package; never overwrite any existing output."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    if count < 1:
        raise ValueError("Review count must be positive")
    if hashlib.sha256(predictions_path.read_bytes()).hexdigest() != POINTS_SHA:
        raise ValueError("Published predictions checksum mismatch")
    manifest = dataset/"manifest.jsonl"
    tiles = [json.loads(line) for line in manifest.read_text().splitlines()]
    predictions = json.loads(predictions_path.read_text())["detected"]
    eligible = [(t, point_boxes(t, predictions, radius)) for t in tiles
                if t["split"] == "train" and t["source_map_id"] == MAP_ID]
    selected = select_tiles(eligible, count)
    if len(selected) != count:
        raise ValueError("Not enough eligible nonempty training tiles")
    output.mkdir(parents=True)
    (output/"INCOMPLETE").write_text("Do not use this partial proposal package.\n")
    images, labels = output/"images/train", output/"labels/train"
    images.mkdir(parents=True)
    labels.mkdir(parents=True)
    records, panels = [], []
    for tile, boxes in selected:
        name = tile["tileId"]
        source_image = dataset/tile["image_path"]
        shutil.copyfile(source_image, images/(name+".png"))
        width, height = tile["widthPx"], tile["heightPx"]
        rows = [f"0 {(b['x']+b['w']/2)/width:.8f} {(b['y']+b['h']/2)/height:.8f} "
                f"{b['w']/width:.8f} {b['h']/height:.8f}" for b in boxes]
        (labels/(name+".txt")).write_text("\n".join(rows)+"\n")
        rects = "".join(f'<rect x="{b["x"]:.3f}" y="{b["y"]:.3f}" '
                        f'width="{b["w"]:.3f}" height="{b["h"]:.3f}"><title>'
                        f'Published ID {html.escape(b["published_id"])}</title></rect>' for b in boxes)
        panels.append(f'<section><h2>{html.escape(name)} — {len(boxes)} proposals</h2>'
                      f'<svg viewBox="0 0 {width} {height}"><image href="images/train/{name}.png" '
                      f'width="{width}" height="{height}"/><g class="boxes">{rects}</g></svg></section>')
        records.append({"tileId": name, "split": "train", "mapYear": tile["mapYear"],
                        "image_sha256": hashlib.sha256(source_image.read_bytes()).hexdigest(),
                        "boxes": boxes})
    (output/"proposals.json").write_text(json.dumps(records, indent=2))
    (output/"preview.html").write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Dowser — unreviewed proposals</title><style>
body{font:16px system-ui;margin:24px;background:#f4f4f4;color:#222}
header{position:sticky;top:0;background:white;padding:12px;z-index:1;border:2px solid #c54}
svg{width:100%;max-width:1100px;background:white}rect{fill:none;stroke:#ef2525;stroke-width:1.5}
body.hide .boxes{display:none}h2{font-size:16px}</style>
<header><b>UNREVIEWED published proposals — not ground truth or Dowser inference.</b>
<p>Boxes use approximate sizes. Inspect all pixels, remove wrong boxes, add missed symbols,
and correct positions/sizes in your annotation tool. This page is a preview, not an editor.</p>
<label><input type="checkbox" checked onchange="document.body.classList.toggle('hide',!this.checked)">
Show proposed boxes</label> · Use browser zoom for detail.</header>'''+"".join(panels)+"</html>")
    notice = ("UNREVIEWED PROPOSALS — NOT TRAINING GROUND TRUTH.\n"
              f"Published U-Net point outputs: {SOURCE_DOI}\n"
              "Ciulla et al.; source README describes CC BY 4.0. Credit the original work.\n"
              "No external weights were run. Boxes are fixed-size heuristics around published centers.\n"
              "All tiles are Train / Oil Center 1954; other eras are not covered.\n"
              "Review the WHOLE image: delete false proposals, add omissions, adjust boxes.\n"
              "Do not overwrite existing Roboflow annotations; use a separate review project/batch\n"
              "and reconcile original tile IDs before transferring reviewed results.\n"
              "No dataset YAML or training job is created. Class 0 is well_symbol.\n")
    (output/"README.txt").write_text(notice)
    # Roboflow's Darknet import uses this label map for numeric class IDs.
    (output/"darknet.labels").write_text("well_symbol\n")
    with zipfile.ZipFile(output/"roboflow_proposals_train.zip", "w", zipfile.ZIP_STORED) as archive:
        for folder in [images, labels]:
            for path in sorted(folder.iterdir()):
                archive.write(path, path.relative_to(output))
        archive.write(output/"README.txt", "README.txt")
        archive.write(output/"darknet.labels", "darknet.labels")
    summary = {"state": "unreviewed_published_proposals_not_training_data",
               "source_doi": SOURCE_DOI, "source_predictions_sha256": POINTS_SHA,
               "input_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
               "tile_count": len(records), "proposal_boxes": sum(len(r["boxes"]) for r in records),
               "unique_published_ids": len({b["published_id"] for r in records for b in r["boxes"]}),
               "human_reviewed_boxes": 0, "box_radius_px": radius,
               "code_commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
               "code_dirty": bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip()),
               "python_version": platform.python_version(),
               "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output/"summary.json").write_text(json.dumps(summary, indent=2))
    (output/"INCOMPLETE").unlink()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT/"data/ml/kern_1024_v1")
    parser.add_argument("--predictions", type=Path, default=ROOT/"data/research/edx/CA_OilCenter_293661_1954_24000_geo_detected.json")
    parser.add_argument("--output", type=Path, default=ROOT/"data/ml/proposals_pilot_v2")
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--radius", type=float, default=8)
    args = parser.parse_args()
    print(json.dumps(prepare(args.dataset,args.predictions,args.output,args.count,args.radius), indent=2))


if __name__ == "__main__":
    main()
