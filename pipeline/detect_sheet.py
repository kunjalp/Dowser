"""Run a pinned model on existing georeferenced sheet tiles, excluding Test.

Adapted from Ryann's detect_sheet.py (received 2026-10-24). Prepared, collar-
masked 1024 px tiles retain the original sheet offsets and frozen split IDs.
Run in pipeline/.venv; geographic export runs separately in the map environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path

from PIL import Image

from pipeline.preview_detector import native_box
from pipeline.train_detector import ROOT, local_sdk


def digest(path):
    """SHA-256 of a local artifact, used to bind inference to immutable inputs."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exportable_tiles(manifest):
    """Select only frozen Train/Val tiles; never open Test or buffer images."""
    if len({r['tileId'] for r in manifest}) != len(manifest):
        raise ValueError('Duplicate tile IDs')
    if any(r['split'] not in {'train', 'val', 'test', 'buffer'} for r in manifest):
        raise ValueError('Unknown frozen split')
    tiles = [r for r in manifest if r['split'] in {'train', 'val'}]
    if not tiles or any((t['widthPx'], t['heightPx']) != (1024, 1024) for t in tiles):
        raise ValueError('Expected native 1024 px Train/Val tiles')
    return tiles


def predict(config_path, output):
    """Write new native-box predictions using the exact pinned inference settings."""
    config = json.loads(config_path.read_text())
    manifest_path = ROOT / config['manifest']
    weights = ROOT / config['weights']
    if digest(manifest_path) != config['manifest_sha256'] or digest(weights) != config['weights_sha256']:
        raise ValueError('Manifest or checkpoint identity differs from inference pin')
    if config['imgsz'] != 1024 or not 0 < config['confidence'] <= 1:
        raise ValueError('Invalid native size or confidence cutoff')
    manifest = [json.loads(s) for s in manifest_path.read_text().splitlines()]
    records = []
    for tile in exportable_tiles(manifest):
        path = (manifest_path.parent / tile['image_path']).resolve()
        if ROOT not in path.parents:
            raise ValueError('Image must belong to this checkout')
        with Image.open(path) as image:
            if image.size != (1024, 1024):
                raise ValueError('Resized image would invalidate native coordinates')
        records.append({'tileId': tile['tileId'], 'split': tile['split'],
                        'mapYear': tile['mapYear'], 'image_path': str(path.relative_to(ROOT)),
                        'image_sha256': digest(path), 'predictions': []})
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    marker = output.with_suffix('.INCOMPLETE')
    marker.write_text('Inference incomplete; do not export.\n')
    model = local_sdk()(str(weights))
    started = time.perf_counter()
    results = model.predict(source=[str(ROOT / r['image_path']) for r in records],
                            imgsz=config['imgsz'], conf=config['confidence'],
                            iou=config['nms_iou'], max_det=config['max_det'],
                            device=config['device'], batch=2, stream=True,
                            save=False, verbose=False)
    for index, (record, result) in enumerate(zip(records, results, strict=True), 1):
        if Path(result.path).resolve() != ROOT / record['image_path']:
            raise ValueError('Unexpected prediction order')
        record['predictions'] = [native_box(b, float(s), float(c), result.orig_shape)
                                 for b, s, c in zip(result.boxes.xyxy.cpu().tolist(),
                                                    result.boxes.conf.cpu().tolist(),
                                                    result.boxes.cls.cpu().tolist())]
        if index % 20 == 0:
            print(f'Predicted {index}/{len(records)} tiles', flush=True)
    payload = {'schema_version': 1, 'config': config, 'config_sha256': digest(config_path),
               'manifest_sha256': digest(manifest_path), 'checkpoint_sha256': digest(weights),
               'test_used': False, 'excluded_splits': ['test', 'buffer'],
               'scope': 'Train/Val integration export, not an accuracy evaluation or full-region census',
               'seconds': round(time.perf_counter() - started, 3),
               'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'code_sha256': digest(__file__), 'images': records}
    with output.open('x') as stream:
        json.dump(payload, stream, indent=2)
    marker.unlink()
    print(f'Wrote {len(records)} tiles / {sum(len(r["predictions"]) for r in records)} boxes to {output}')
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True, help='Pinned inference JSON; no implicit model selection')
    parser.add_argument('--out', type=Path, required=True, help='Fresh predictions.json, before geographic export')
    args = parser.parse_args()
    predict(args.config, args.out)


if __name__ == '__main__':
    main()
