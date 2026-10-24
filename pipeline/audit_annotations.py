"""Audit a Roboflow YOLO export against the frozen native-image manifest.

Preserve the ZIP, restore original PNGs, and normalize only subpixel export
rounding. No label is semantically approved, split changed, or training run.
"""

import argparse
import hashlib
import html
import io
import importlib.metadata
import json
import math
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


ROUNDING_TOLERANCE_PX = 0.02
LARGE_BOX_PX = 40  # Review heuristic only; large does not mean incorrect.


def parse_labels(text, width=1024, height=1024):
    """Validate normalized class-0 xywh rows; return boxes and logged edge clips.

    Coordinates use pixel edges. Refuse nonfinite/out-of-frame geometry except
    <=0.02 px export rounding. Never tighten semantic object boundaries here.
    """
    boxes, corrections = [], []
    for line_number, row in enumerate(text.splitlines(), 1):
        if not row.strip():
            continue
        values = [float(v) for v in row.split()]
        if len(values) != 5 or not all(math.isfinite(v) for v in values):
            raise ValueError(f"Invalid YOLO row {line_number}")
        class_id, cx, cy, w, h = values
        if class_id != 0 or min(w, h) <= 0:
            raise ValueError(f"Wrong class or nonpositive box on row {line_number}")
        edges = [(cx-w/2)*width, (cy-h/2)*height,
                 (cx+w/2)*width, (cy+h/2)*height]
        left, top, right, bottom = edges
        overflow = max(0, -left, -top, right-width, bottom-height)
        if overflow > ROUNDING_TOLERANCE_PX:
            raise ValueError(f"Box exceeds image on row {line_number}: {overflow:.4f} px")
        clipped = [max(0,left),max(0,top),min(width,right),min(height,bottom)]
        left, top, right, bottom = clipped
        if right <= left or bottom <= top:
            raise ValueError(f"Box outside image on row {line_number}")
        if overflow > 1e-9:
            corrections.append({"row":line_number,"overflow_px":overflow,
                                "before_xyxy_px":edges,"after_xyxy_px":clipped})
        boxes.append({"row":line_number,"x":left,"y":top,"w":right-left,"h":bottom-top})
    return boxes, corrections


def match_tile(filename, manifest, expected_split="train"):
    """Resolve a filename to its declared frozen split; never reassign geography."""
    if expected_split not in {"train","val","test"}:
        raise ValueError("Expected train, val or test")
    match = re.fullmatch(r"(usgs_\d+_x\d+_y\d+)(?:_png\.rf\.[0-9a-f]+)?\.(?:jpg|jpeg|png)",filename)
    if not match or match[1] not in manifest:
        raise ValueError(f"Unknown exported tile: {filename}")
    tile = manifest[match[1]]
    if tile["split"] != expected_split:
        raise ValueError(f"Image is not in frozen {expected_split}: {filename}")
    return tile


def review_figure(output, records):
    """Plot native-pixel neighborhoods and actual annotation rectangles for review."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    flagged = [(r,b) for r in records for b in r["boxes"] if max(b["w"],b["h"]) > LARGE_BOX_PX]
    if not flagged:
        return
    rows = math.ceil(len(flagged)/5)
    fig, axes = plt.subplots(rows,5,figsize=(15,3*rows),layout="constrained",squeeze=False)
    for ax,(record,box) in zip(axes.flat,flagged):
        image = np.asarray(Image.open(output/"images"/record["split"]/(record["tileId"]+".png")))
        # Matplotlib's image origin is a pixel center; our rectangles use edges.
        ax.imshow(image,extent=(0,1024,1024,0))
        ax.add_patch(Rectangle((box["x"],box["y"]),box["w"],box["h"],fill=False,
                               edgecolor="red",linewidth=1.2))
        cx,cy = box["x"]+box["w"]/2,box["y"]+box["h"]/2
        ax.set_xlim(max(0,cx-46),min(1024,cx+46))
        ax.set_ylim(min(1024,cy+46),max(0,cy-46))
        ax.set_title(f'{record["mapYear"]}, row {box["row"]}: {box["w"]:.1f} x {box["h"]:.1f} px',fontsize=9)
        ax.axis("off")
    for ax in axes.flat[len(flagged):]:
        ax.axis("off")
    fig.suptitle("Manual labels: larger boxes to review, not automatic rejection")
    fig.savefig(output/"large_boxes_review.png",dpi=150)
    plt.close(fig)


def audit(archive_path, dataset, output, expected_split="train"):
    """Produce an auditable import/review package; refuse existing output.

    No ZIP extraction is performed: read recognized members and write fixed
    manifest-derived paths. Exported JPEGs must align with source PNGs. A passing
    format audit is not approval of labels or evidence of independent accuracy.
    """
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    if expected_split not in {"train","val","test"}:
        raise ValueError("Expected train, val or test")
    # A project export may contain already reviewed Train plus newly labeled Val.
    # Import the explicitly requested folder, checking each ID against our split.
    source_folders = {"train":["train"],"val":["valid","val"],"test":["test"]}[expected_split]
    manifest_path = dataset/"manifest.jsonl"
    manifest = {t["tileId"]:t for t in map(json.loads,manifest_path.read_text().splitlines())}
    records, seen = [], set()
    with zipfile.ZipFile(archive_path) as z:
        if len(z.namelist()) != len(set(z.namelist())) or z.testzip():
            raise ValueError("Duplicate or damaged ZIP members")
        config = yaml.safe_load(z.read("data.yaml"))
        if config.get("nc") != 1 or config.get("names") not in (["well_symbol"],{0:"well_symbol"}):
            raise ValueError("Expected only class 0: well_symbol")
        images = sorted(n for n in z.namelist() if any(n.startswith(f+"/images/") for f in source_folders)
                        and Path(n).suffix.lower() in [".png",".jpg",".jpeg"])
        labels = {n for n in z.namelist() if any(n.startswith(f+"/labels/") for f in source_folders) and n.endswith(".txt")}
        expected = {n.replace("/images/","/labels/").rsplit(".",1)[0]+".txt" for n in images}
        if not images or labels != expected:
            raise ValueError("Missing images/labels or orphan annotation files")
        for name in images:
            tile = match_tile(Path(name).name,manifest,expected_split)
            if tile["tileId"] in seen:
                raise ValueError("Multiple augmented/duplicate copies of one tile")
            seen.add(tile["tileId"])
            image = Image.open(io.BytesIO(z.read(name))).convert("RGB")
            original_path = dataset/tile["image_path"]
            original = Image.open(original_path).convert("RGB")
            if image.size != (1024,1024) or original.size != image.size:
                raise ValueError("Export must preserve 1024 px native geometry")
            a,b = np.asarray(image,dtype=float),np.asarray(original,dtype=float)
            mae = float(np.abs(a-b).mean())
            # JPEG export recompresses images. An identity alignment should be
            # better than shifted alternatives; reject unexpected image changes.
            shifted = {}
            for dy,dx in [(-2,0),(-1,0),(1,0),(2,0),(0,-2),(0,-1),(0,1),(0,2)]:
                shifted[f"{dx},{dy}"] = float(np.abs(a[2:-2,2:-2]-b[2+dy:1022+dy,2+dx:1022+dx]).mean())
            if mae > 10 or min(shifted.values()) < mae:
                raise ValueError("Export does not align with original tile")
            label_path = name.replace("/images/","/labels/").rsplit(".",1)[0]+".txt"
            boxes, corrections = parse_labels(z.read(label_path).decode())
            records.append({"tileId":tile["tileId"],"mapYear":tile["mapYear"],"split":expected_split,
                            "export_image":name,"source_image":tile["image_path"],
                            "original_png_sha256":hashlib.sha256(original_path.read_bytes()).hexdigest(),
                            "export_mae":mae,"shifted_mae":shifted,"boxes":boxes,
                            "rounding_corrections":corrections,
                            "semantic_review":"pending; annotator reports complete"})
    output.mkdir(parents=True)
    (output/"INCOMPLETE").write_text("Audit/import not complete.\n")
    for folder in ["images/"+expected_split,"labels/"+expected_split]:
        (output/folder).mkdir(parents=True)
    panels = []
    for record in records:
        tile_id = record["tileId"]
        shutil.copyfile(dataset/record["source_image"],output/"images"/expected_split/(tile_id+".png"))
        rows = [f'0 {(b["x"]+b["w"]/2)/1024:.12f} {(b["y"]+b["h"]/2)/1024:.12f} '
                f'{b["w"]/1024:.12f} {b["h"]/1024:.12f}' for b in record["boxes"]]
        (output/"labels"/expected_split/(tile_id+".txt")).write_text("\n".join(rows)+("\n" if rows else ""))
        rects = "".join(f'<rect x="{b["x"]}" y="{b["y"]}" width="{b["w"]}" height="{b["h"]}">'
                        f'<title>YOLO row {b["row"]}</title></rect>' for b in record["boxes"])
        panels.append(f'<h2>{html.escape(tile_id)} — {len(rows)} boxes</h2>'
                      f'<svg viewBox="0 0 1024 1024"><image href="images/{expected_split}/{tile_id}.png" '
                      f'width="1024" height="1024"/><g class="boxes">{rects}</g></svg>')
    (output/"review.html").write_text('''<!doctype html><meta charset="utf-8"><title>Dowser manual-label audit</title>
<style>body{font:16px system-ui;margin:24px}header{position:sticky;top:0;background:white;padding:12px;z-index:1}
svg{display:block;max-width:1024px;width:100%}rect{fill:none;stroke:red;stroke-width:1}
body.hide .boxes{display:none}</style><header><b>Human-drawn labels — semantic quality review pending.</b>
<p>Preview only. Correct labels in the original annotation project.</p>
<label><input type="checkbox" checked onchange="document.body.classList.toggle('hide',!this.checked)">
Show boxes (hover for original YOLO row number)</label></header>'''+"".join(panels))
    summary = {"state":"structurally_valid_semantic_review_required",
               "split":expected_split,
               "archive_sha256":hashlib.sha256(archive_path.read_bytes()).hexdigest(),
               "manifest_sha256":hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
               "image_count":len(records),"box_count":sum(len(r["boxes"]) for r in records),
               "boxes_by_year":{str(y):sum(len(r["boxes"]) for r in records if r["mapYear"]==y)
                                for y in sorted({r["mapYear"] for r in records})},
               "rounding_correction_count":sum(len(r["rounding_corrections"]) for r in records),
               "large_box_review_count":sum(max(b["w"],b["h"])>LARGE_BOX_PX for r in records for b in r["boxes"]),
               "code_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
               "code_dirty":bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip()),
               "versions":{p:importlib.metadata.version(p) for p in ["numpy","Pillow","PyYAML","matplotlib"]},
               "script_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "validation_labels":sum(len(r["boxes"]) for r in records) if expected_split=="val" else 0,
               "test_labels":sum(len(r["boxes"]) for r in records) if expected_split=="test" else 0,
               "empty_label_images":sum(not r["boxes"] for r in records),
               "limits":["No full semantic/completeness approval", "Only the explicitly requested split is imported",
                         "Box instances are not a count of distinct physical wells",
                         "No active training YAML: this is a single-split import"]}
    (output/"audit.json").write_text(json.dumps({"summary":summary,"images":records},indent=2))
    (output/"dataset.template.yaml").write_text(
        "# REVIEW REQUIRED; independent validation/test labels are absent.\n"
        "# This is not an active training configuration.\n"
        f"path: {output.resolve()}\n"+
        "".join(f"{s}: "+(f"images/{s}" if s==expected_split else "null")+"\n" for s in ["train","val","test"])+
        "names:\n  0: well_symbol\n")
    review_figure(output,records)
    (output/"INCOMPLETE").unlink()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--dataset",type=Path,default=ROOT/"data/ml/kern_1024_v1")
    parser.add_argument("--output",type=Path,default=ROOT/"data/ml/reviewed_v1")
    parser.add_argument("--split",choices=["train","val","test"],default="train")
    args = parser.parse_args()
    print(json.dumps(audit(args.archive,args.dataset,args.output,args.split),indent=2))


if __name__ == "__main__":
    main()
