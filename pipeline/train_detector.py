"""Preflight and run local YOLO training with frozen, reviewed Train/Val inputs.

No dataset download, random split, empty-label invention, or cloud deployment.
--check-only validates readiness without importing Torch or starting training.
"""

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
from pathlib import Path

import yaml
from PIL import Image

from pipeline.audit_annotations import parse_labels

ROOT = Path(__file__).resolve().parents[1]


def read_import(folder, expected_split, manifest):
    """Validate one audited import, image hashes, label geometry, and frozen IDs."""
    report_path = folder/"audit.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing reviewed {expected_split} import: {report_path}")
    report = json.loads(report_path.read_text())
    records = report["images"]
    if not records or (folder/"INCOMPLETE").exists():
        raise ValueError("Annotation import is empty or incomplete")
    seen, boxes = set(), 0
    for record in records:
        tile_id = record["tileId"]
        if tile_id in seen or tile_id not in manifest:
            raise ValueError("Duplicate or unknown tile ID")
        seen.add(tile_id)
        if manifest[tile_id]["split"] != expected_split or record["split"] != expected_split:
            raise ValueError(f"Frozen split violation: {tile_id}")
        image_path = folder/"images"/expected_split/(tile_id+".png")
        label_path = folder/"labels"/expected_split/(tile_id+".txt")
        if hashlib.sha256(image_path.read_bytes()).hexdigest() != record["original_png_sha256"]:
            raise ValueError(f"Changed image: {tile_id}")
        with Image.open(image_path) as im:
            if im.size != (1024,1024):
                raise ValueError("Training requires native 1024 px images")
        parsed, _ = parse_labels(label_path.read_text())
        if len(parsed) != len(record["boxes"]) or any(
            abs(a[k]-b[k]) > 1e-6 for a,b in zip(parsed,record["boxes"]) for k in ["x","y","w","h"]):
            raise ValueError(f"Labels differ from audited import: {tile_id}")
        boxes += len(parsed)
    image_names = {p.name for p in (folder/"images"/expected_split).iterdir()
                   if p.is_file() and p.suffix.lower() in {".png",".jpg",".jpeg",".webp",".bmp"}}
    label_names = {p.name for p in (folder/"labels"/expected_split).glob("*.txt")}
    if image_names != {k+".png" for k in seen} or label_names != {k+".txt" for k in seen}:
        raise ValueError("Unexpected unaudited images or labels in the import directory")
    return {"ids":seen,"images":len(seen),"boxes":boxes,
            "audit_sha256":hashlib.sha256(report_path.read_bytes()).hexdigest()}


def check_inputs(config, root=ROOT):
    """Refuse missing Validation, test leakage, changed labels, or wrong weights."""
    manifest_path = root/config["manifest"]
    manifest = {t["tileId"]:t for t in map(json.loads,manifest_path.read_text().splitlines())}
    train = read_import(root/config["train_import"],"train",manifest)
    val = read_import(root/config["validation_import"],"val",manifest)
    if train["boxes"] < config["minimum_training_boxes"]:
        raise ValueError("Not enough training symbols")
    if not val["boxes"] and not config.get("allow_negative_only_validation",False):
        raise ValueError("Positive validation examples required for this run")
    if config["require_all_validation_tiles"] and val["ids"] != {k for k,v in manifest.items() if v["split"]=="val"}:
        raise ValueError("Validation must include all frozen validation tiles")
    if train["ids"] & val["ids"]:
        raise ValueError("Train/Validation IDs overlap")
    for a in train["ids"]:
        for b in val["ids"]:
            ax,ay,ar,ab = manifest[a]["split_bounds_m"]
            bx,by,br,bb = manifest[b]["split_bounds_m"]
            if min(ar,br)>max(ax,bx) and min(ab,bb)>max(ay,by):
                raise ValueError("Train/Validation footprints overlap")
    weights = root/config["weights"]
    if hashlib.sha256(weights.read_bytes()).hexdigest() != config["weights_sha256"]:
        raise ValueError("Pretrained weights checksum mismatch")
    return {"state":"ready_for_training","train_images":train["images"],"train_boxes":train["boxes"],
            "validation_images":val["images"],"validation_boxes":val["boxes"],
            "train_audit_sha256":train["audit_sha256"],"validation_audit_sha256":val["audit_sha256"],
            "manifest_sha256":hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "validation_has_positives":bool(val["boxes"]),
            "validation_scope":"normal validation" if val["boxes"] else "negative-only diagnostics; recall/mAP undefined",
            "test_used":False}


def local_sdk():
    """Load YOLO using task-local settings and disabled external training loggers."""
    os.environ["YOLO_CONFIG_DIR"] = str(ROOT/"data/ml/ultralytics_settings")
    os.environ["YOLO_OFFLINE"] = "true"
    os.environ["YOLO_AUTOINSTALL"] = "false"
    from ultralytics import YOLO, settings
    settings.update({k:False for k in ["sync","clearml","comet","dvc","mlflow","raytune","tensorboard","wandb"]})
    return YOLO


def run(config, name):
    """Train only after preflight; record inputs and status in a new local run."""
    ready = check_inputs(config)
    actual_versions = {p:importlib.metadata.version(p) for p in config["versions"]}
    if actual_versions != config["versions"]:
        raise ValueError(f"Training environment differs from pinned config: {actual_versions}")
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
        raise ValueError("Run name must contain only letters, digits, underscore or hyphen")
    output = ROOT/"data/ml/runs"/name
    output.mkdir(parents=True,exist_ok=False)
    data = {"train":str((ROOT/config["train_import"]/"images/train").resolve()),
            "val":str((ROOT/config["validation_import"]/"images/val").resolve()),"names":{0:"well_symbol"}}
    dataset_path = output/"data.yaml"
    dataset_path.write_text(yaml.safe_dump(data))
    record = {"state":"starting","inputs":ready,"config":config,"versions":actual_versions,
              "code_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
              "code_dirty":bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip())}
    record_path = output/"run.json"
    record_path.write_text(json.dumps(record,indent=2))
    try:
        YOLO = local_sdk()
        model = YOLO(str(ROOT/config["weights"]))
        model.train(data=str(dataset_path),project=str(output),name="training",exist_ok=False,**config["training"])
        record["state"] = "completed"
        record["save_dir"] = str(model.trainer.save_dir)
        record["metrics"] = dict(model.trainer.metrics)
        record["metric_scope"] = "validation, not independent final test"
        if not ready["validation_has_positives"]:
            record["raw_framework_metrics"] = record.pop("metrics")
            record["metrics"] = None
            record["metric_scope"] = "negative-only diagnostic run; reported framework zeros are not measured recall/mAP"
    except BaseException as exc:
        record["state"] = "failed_or_interrupted"
        record["error"] = str(exc)
        raise
    finally:
        record_path.write_text(json.dumps(record,indent=2,default=str))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,default=ROOT/"pipeline/config/train_smoke.json")
    parser.add_argument("--check-only",action="store_true")
    parser.add_argument("--name",default="kern_yolo11n_smoke_v1")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    try:
        result = check_inputs(config) if args.check_only else run(config,args.name)
    except (FileNotFoundError,ValueError) as exc:
        parser.exit(2,f"Not ready: {exc}\n")
    print(json.dumps(result,indent=2,default=str))


if __name__ == "__main__":
    main()
