"""Apply an experimental crop verifier to the unchanged pinned YOLO CSV.

Outputs are separate accepted/rejected CSVs with both scores. Original rows,
model weights, final-Test protocol and production candidate statuses are untouched.
This command currently admits the frozen Train/Val handoff only, not final Test.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.train_symbol_verifier import ROOT, digest, make_model, patch_tensor


def apply(verifier_run, detections, cutoff, output):
    """Filter native boxes at an explicit Val-calibrated cutoff; keep YOLO scores."""
    import torch
    if not 0 < cutoff < 1:
        raise ValueError('Verifier cutoff must be explicit and inside (0,1)')
    run = json.loads((verifier_run/'run.json').read_text())
    if run['test_used'] or digest(detections) != run['source_csv_sha256']:
        raise ValueError('This experiment is restricted to the pinned Train/Val source CSV')
    if digest(verifier_run/'verifier.pt') != run['verifier_sha256']:
        raise ValueError('Verifier checkpoint identity mismatch')
    if output.exists():
        raise FileExistsError(output)
    torch.set_num_threads(4)
    model = make_model()
    checkpoint = torch.load(verifier_run/'verifier.pt', map_location='cpu', weights_only=True)
    model.load_state_dict(checkpoint['state_dict']); model.eval()
    manifest_path = ROOT/'data/ml/kern_1024_v2/manifest.jsonl'
    manifest = {r['tileId']: r for r in map(json.loads, manifest_path.read_text().splitlines())}
    if digest(manifest_path) != run['manifest_sha256']:
        raise ValueError('Frozen manifest changed')
    with detections.open() as f:
        reader = csv.DictReader(f); fields = list(reader.fieldnames); rows = list(reader)
    for r in rows:
        if manifest[r['tileId']]['split'] not in {'train', 'val'} or r['source'] != 'model':
            raise ValueError('Test/buffer and non-model rows are excluded')
    image_cache, scores = {}, []
    for start in range(0, len(rows), 128):
        patches = []
        for row in rows[start:start+128]:
            tile = manifest[row['tileId']]
            if row['tileId'] not in image_cache:
                with Image.open(ROOT/'data/ml/kern_1024_v2'/tile['image_path']) as im:
                    image_cache[row['tileId']] = im.convert('RGB')
            patches.append(patch_tensor(image_cache[row['tileId']],
                                        {k: float(row[k]) for k in ['x', 'y', 'w', 'h']}))
        with torch.no_grad():
            scores.extend(torch.sigmoid(model(torch.from_numpy(np.stack(patches)))).flatten().tolist())
    output.mkdir(parents=True)
    accepted, rejected = [], []
    for row, score in zip(rows, scores):
        annotated = {**row, 'verifier_score': score, 'verifier_cutoff': cutoff}
        (accepted if score >= cutoff else rejected).append(annotated)
    for name, values in [('accepted.csv', accepted), ('rejected.csv', rejected)]:
        with (output/name).open('x', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields+['verifier_score', 'verifier_cutoff'])
            writer.writeheader(); writer.writerows(values)
    receipt = {'scope': 'Experimental second-stage filtering, not independent accuracy or well verification',
               'source_csv_sha256': digest(detections), 'verifier_sha256': run['verifier_sha256'],
               'base_checkpoint_sha256': run['base_checkpoint_sha256'], 'verifier_cutoff': cutoff,
               'base_confidence': .71, 'input_rows': len(rows), 'accepted': len(accepted),
               'rejected': len(rejected), 'test_used': False, 'device': 'cpu',
               'source_code_sha256': digest(__file__), 'yolo_confidence_replaced': False,
               'manual_or_production_statuses_changed': False}
    (output/'receipt.json').write_text(json.dumps(receipt, indent=2))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verifier-run', type=Path, required=True)
    parser.add_argument('--detections', type=Path, required=True)
    parser.add_argument('--cutoff', type=float, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply(args.verifier_run, args.detections, args.cutoff, args.out), indent=2))


if __name__ == '__main__':
    main()
