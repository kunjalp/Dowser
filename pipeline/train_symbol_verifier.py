"""Train a small crop verifier from reviewed Train symbols and human false crops.

The base YOLO checkpoint remains unchanged. This optional second stage predicts
whether the centered object is a target well symbol. Its score is not a calibrated
probability and never replaces YOLO confidence. Test imagery is excluded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PATCH = 48


def digest(path):
    """SHA-256 of a source artifact for a reproducible local run."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def patch_tensor(image, box, jitter=None, scale_range=(.9, 1.1)):
    """Return native-box-centered RGB ink, 3x48x48; pad outside image white.

    Native xywh uses pixel edges. The crop includes 1.6x object context; resize
    is local to this classifier, never to detector or geographic coordinates.
    """
    values = [float(box[k]) for k in ['x', 'y', 'w', 'h']]
    x, y, w, h = values
    if not all(math.isfinite(v) for v in values) or min(w, h) <= 0 or min(x, y) < 0:
        raise ValueError('Invalid native box')
    if x+w > image.width+1e-6 or y+h > image.height+1e-6:
        raise ValueError('Box exceeds image')
    cx, cy, side = x+w/2, y+h/2, max(w, h)*1.6
    if jitter is not None:
        cx += jitter.uniform(-.08, .08)*w
        cy += jitter.uniform(-.08, .08)*h
        side *= jitter.uniform(*scale_range)
    size = max(4, math.ceil(side))
    left, top = math.floor(cx-size/2), math.floor(cy-size/2)
    valid = (max(0, left), max(0, top), min(image.width, left+size), min(image.height, top+size))
    crop = Image.new('RGB', (size, size), 'white')
    crop.paste(image.crop(valid), (valid[0]-left, valid[1]-top))
    pixels = np.asarray(crop.resize((PATCH, PATCH), Image.Resampling.BILINEAR), dtype=np.float32)
    return np.ascontiguousarray((1-pixels/255).transpose(2, 0, 1))


def require_train(tile):
    """Reject held-out and buffer sources before opening crop-training images."""
    if tile['split'] != 'train':
        raise ValueError('Verifier training may use frozen Train only')


def make_model():
    """Construct the fixed small RGB classifier; import Torch only in ML env."""
    from torch import nn
    return nn.Sequential(nn.Conv2d(3, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                         nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
                         nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(), nn.Flatten(),
                         nn.Linear(32*12*12, 32), nn.ReLU(), nn.Linear(32, 1))


def choose_cutoff(scores, targets, positive_total=49, minimum_tp=45):
    """Val-only calibration: maximize F1 while preserving the declared recall gate.

    Targets describe existing detector proposals; positive_total also includes
    ground-truth symbols missed by the detector. This is not a Test sweep.
    """
    if len(scores) != len(targets) or minimum_tp > sum(targets) or positive_total < sum(targets):
        raise ValueError('Invalid targets or unattainable recall gate')
    points = []
    for i in range(1000):
        cutoff = i/1000
        tp = sum(t == 1 and s >= cutoff for s, t in zip(scores, targets))
        fp = sum(t == 0 and s >= cutoff for s, t in zip(scores, targets))
        fn = positive_total-tp
        if tp >= minimum_tp:
            points.append({'verifier_cutoff': cutoff, 'tp': tp, 'fp': fp, 'fn': fn,
                           'precision': tp/(tp+fp), 'recall': tp/positive_total,
                           'f1': 2*tp/(2*tp+fp+fn)})
    return max(points, key=lambda m: (m['f1'], m['verifier_cutoff']))


def train(output, epochs=15, runtime_matched_positives=False, select_val_f1=False):
    """Fit with balanced Train batches; select epoch by balanced Val BCE at fixed .5.

    Positives retain human/assistant source counts. Negatives are human-reviewed
    false object crops, not assertions that their entire source tiles are empty.
    Validation is the existing 15-frame set; all scoring remains Val tuning.
    """
    import csv
    import torch
    from torch.nn import functional as F
    if output.exists():
        raise FileExistsError(output)
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    torch.set_num_threads(4)
    manifest_path = ROOT/'data/ml/kern_1024_v2/manifest.jsonl'
    manifest = {r['tileId']: r for r in map(json.loads, manifest_path.read_text().splitlines())}
    audit_path = ROOT/'data/ml/train_mixed_v1/audit.json'
    audit = json.loads(audit_path.read_text())
    review_path = ROOT/'data/ml/rollout_diagnosis_v1/ryann_confirmed_false_reviews.json'
    reviewed = json.loads(review_path.read_text())
    csv_path = ROOT/'pipeline/data/ryann_cursor_translate_v1/detections.csv'
    original = {r['detectionId']: r for r in csv.DictReader(csv_path.open())}
    rng = random.Random(42)
    from pipeline.evaluate_preview import box_iou, evaluate
    preview_path = ROOT/'data/ml/runs/cursor_translate_mps/preview/predictions.json'
    payload = json.loads(preview_path.read_text())
    train_predictions = {r['tileId']: r for r in payload['images'] if r['split'] == 'train'}
    positives, negatives, provenance = [], [], []
    positive_sources = {}
    for row in audit['images']:
        require_train(manifest[row['tileId']])
        with Image.open(ROOT/'data/ml/train_mixed_v1/images/train'/f"{row['tileId']}.png") as im:
            image = im.convert('RGB')
        boxes = row['boxes']
        if runtime_matched_positives:
            boxes, used = [], set()
            for b in sorted(train_predictions[row['tileId']]['predictions'], key=lambda b: -b['confidence']):
                overlap, j = max(((box_iou(b, g), j) for j, g in enumerate(row['boxes']) if j not in used), default=(0, -1))
                if overlap >= .3 and b['confidence'] >= .5:
                    boxes.append(b); used.add(j)
        source = row.get('annotation_source', 'human_reported')
        positive_sources[source] = positive_sources.get(source, 0) + len(boxes)
        for box in boxes:
            for _ in range(4):
                positives.append(patch_tensor(image, box, rng, (.65, 1.35) if runtime_matched_positives else (.9, 1.1)))
        provenance.append({'tileId': row['tileId'], 'positive_boxes': len(boxes), 'source': source})
    neg_ids = []
    for row in reviewed['rows']:
        tile = manifest[row['tileId']]
        if tile['split'] != 'train':
            continue  # Held-out feedback stays in evaluation, never training.
        require_train(tile)
        if row['source'] != 'human_review_csv_forwarded_by_user' or row['verdict'] != 'not_a_target_well_symbol':
            raise ValueError('Require human-reviewed false crop')
        native = original[row['detectionId']]
        box = {k: float(native[k]) for k in ['x', 'y', 'w', 'h']}
        with Image.open(ROOT/'data/ml/kern_1024_v2'/tile['image_path']) as im:
            image = im.convert('RGB')
        for _ in range(16):
            negatives.append(patch_tensor(image, box, rng, (.65, 1.35) if runtime_matched_positives else (.9, 1.1)))
        neg_ids.append(row['detectionId'])
    if len(neg_ids) != 58:
        raise ValueError('Unexpected reviewed Train-negative membership')
    px = torch.from_numpy(np.stack(positives))
    nx = torch.from_numpy(np.stack(negatives))
    validation, targets, records = [], [], []
    for row in payload['images']:
        if row['split'] != 'val':
            continue
        if manifest[row['tileId']]['split'] != 'val' or row.get('annotation_source', 'human_reported') != 'human_reported':
            raise ValueError('Require frozen human Val')
        with Image.open(ROOT/'data/ml/reviewed_validation_v1/images/val'/f"{row['tileId']}.png") as im:
            image = im.convert('RGB')
        record = {**row, 'predictions': []}
        used = set()
        for box in sorted((b for b in row['predictions'] if b['confidence'] >= .71),
                          key=lambda b: -b['confidence']):
            overlap, j = max(((box_iou(box, g), j) for j, g in enumerate(row['ground_truth'])
                              if j not in used), default=(0, -1))
            label = int(overlap >= .5)
            if label:
                used.add(j)
            validation.append(patch_tensor(image, box)); targets.append(label)
            record['predictions'].append({**box, 'verifier_index': len(validation)-1})
        records.append(record)
    vx = torch.from_numpy(np.stack(validation))
    vy = torch.tensor(targets, dtype=torch.float32)
    if (len(validation), sum(targets)) != (50, 46):
        raise ValueError('Base operating point differs from reviewed reference')
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    model = make_model().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.001)
    output.mkdir(parents=True)
    best_loss, best_state, history = float('inf'), None, []
    best_f1, best_epoch, best_cutoff = -1, None, .5
    started = time.perf_counter()
    for epoch in range(epochs):
        model.train()
        for _ in range(math.ceil(len(positives)/4/16)):
            x = torch.cat([px[torch.randint(len(px), (16,))], nx[torch.randint(len(nx), (16,))]]).to(device)
            y = torch.cat([torch.ones(16), torch.zeros(16)]).to(device)
            x = torch.rot90(x, random.randrange(4), dims=(2, 3))
            if random.random() < .5:
                x = torch.flip(x, dims=(3,))
            optimizer.zero_grad(); loss = F.binary_cross_entropy_with_logits(model(x).flatten(), y)
            loss.backward(); optimizer.step()
        model.eval()
        with torch.no_grad():
            logits = model(vx.to(device)).flatten().cpu()
            losses = F.binary_cross_entropy_with_logits(logits, vy, reduction='none')
            val_loss = float((losses[vy == 1].mean()+losses[vy == 0].mean())/2)
            scores = torch.sigmoid(logits).tolist()
        filtered = [{**r, 'predictions': [b for b in r['predictions'] if scores[b['verifier_index']] >= .5]} for r in records]
        metrics = evaluate(filtered, .71)['overall']
        point = choose_cutoff(scores, targets) if select_val_f1 else None
        history.append({'epoch': epoch+1, 'balanced_val_bce': val_loss, 'metrics': metrics,
                        'val_calibrated_point': point})
        improved = point['f1'] > best_f1 if select_val_f1 else val_loss < best_loss
        if improved:
            best_loss = val_loss
            best_epoch = epoch
            if select_val_f1:
                best_f1, best_cutoff = point['f1'], point['verifier_cutoff']
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        print(json.dumps(history[-1]), flush=True)
    torch.save({'state_dict': best_state, 'patch_size': PATCH, 'context_factor': 1.6,
                'verifier_cutoff': best_cutoff, 'base_confidence': .71, 'architecture': 'rgb48_conv16_32_32_linear32_v1'}, output/'verifier.pt')
    selected = history[best_epoch]
    report = {'scope': 'Repeated human-Val tuning only, not Test or candidate-field accuracy',
              'base_checkpoint_sha256': payload['checkpoint_sha256'],
              'manifest_sha256': digest(manifest_path), 'train_audit_sha256': digest(audit_path),
              'negative_reviews_sha256': digest(review_path), 'source_csv_sha256': digest(csv_path),
              'source_code_sha256': digest(__file__), 'test_used': False, 'seed': 42,
              'positive_boxes': len(positives)//4, 'positive_supervision': positive_sources,
              'positive_box_source': 'Train YOLO boxes matched one-to-one to reviewed GT at IoU>=.3/conf>=.5' if runtime_matched_positives else 'Reviewed GT boxes',
              'training_context_scale': [.65, 1.35] if runtime_matched_positives else [.9, 1.1],
              'human_false_train_crops': len(neg_ids), 'negative_detection_ids': neg_ids,
              'train_sources': provenance, 'device': device, 'epochs': epochs,
              'seconds': round(time.perf_counter()-started, 3), 'history': history,
              'selection': 'maximum Val F1 over epoch/cutoff with TP>=45/49, earliest epoch tie; no Test use' if select_val_f1 else 'minimum balanced binary Val BCE; fixed verifier cutoff .5, base .71',
              'selected': selected, 'verifier_sha256': digest(output/'verifier.pt'),
              'promoted': False, 'versions': {'torch': torch.__version__, 'numpy': np.__version__}}
    (output/'run.json').write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--runtime-matched-positives', action='store_true')
    parser.add_argument('--select-val-f1', action='store_true')
    args = parser.parse_args()
    report = train(args.out, runtime_matched_positives=args.runtime_matched_positives,
                   select_val_f1=args.select_val_f1)
    print(json.dumps({'selected': report['selected'], 'seconds': report['seconds']}, indent=2))


if __name__ == '__main__':
    main()
