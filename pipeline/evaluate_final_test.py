"""Single-shot final-Test evaluation governed by a frozen protocol JSON.

Master Plan section 6: report precision/recall on held-out tiles, stating maps
and eras. This is deliberately separate from the Train/Val preview tools so Test
is never renamed to Val. Guarantees enforced here:

* the protocol fixes checkpoint SHA, cutoff, NMS, size, max_det and the exact
  30 Test IDs/PNG hashes; any mismatch refuses to run;
* GT comes only from audited human Test imports (``audit_annotations --split
  test``), merged by original tileId; duplicate tiles must agree exactly or the
  run refuses; assistant/model-derived labels are rejected;
* all protocol tiles must be present (``--coverage-only`` reports gaps without
  inference); there is no threshold sweep and no way to pass another cutoff;
* outputs are written once (refuses to overwrite) and record that this Test has
  been consumed for this protocol.

Run inference in pipeline/.venv (Torch/MPS).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline.evaluate_preview import aggregate, match_image
from pipeline.train_detector import ROOT


def digest(path):
    """SHA-256 of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_protocol(path):
    """Validate a frozen protocol and the files it pins; return it."""
    protocol = json.loads(Path(path).read_text())
    if not protocol.get('status', '').startswith('frozen'):
        raise ValueError('Protocol is not frozen')
    evaluation = protocol['evaluation']
    if evaluation.get('allow_confidence_sweep') or evaluation.get('allow_training_on_test'):
        raise ValueError('Protocol must forbid sweeps and training on Test')
    model = protocol['model']
    if digest(ROOT / model['weights']) != model['weights_sha256']:
        raise ValueError('Checkpoint differs from the frozen protocol')
    if digest(ROOT / protocol['manifest']) != protocol['manifest_sha256']:
        raise ValueError('Manifest differs from the frozen protocol')
    if model['imgsz'] != 1024 or not 0 < model['confidence'] <= 1:
        raise ValueError('Protocol must use native 1024 px and a fixed cutoff')
    manifest = {r['tileId']: r for r in map(json.loads, (ROOT / protocol['manifest']).read_text().splitlines())}
    frozen_test = {k for k, v in manifest.items() if v['split'] == 'test'}
    ids = [t['tileId'] for t in protocol['test_tiles']]
    if len(ids) != len(set(ids)) or set(ids) != frozen_test:
        raise ValueError('Protocol Test IDs must equal the frozen manifest Test split exactly')
    for tile in protocol['test_tiles']:
        if digest(ROOT / tile['image_path']) != tile['png_sha256']:
            raise ValueError(f"Test image changed: {tile['tileId']}")
    if protocol.get('verifier'):
        raise ValueError('Two-stage verifier protocols are not implemented by this evaluator')
    return protocol


def merge_imports(protocol, import_dirs):
    """Merge audited human Test imports by tileId; return (gt_by_id, provenance).

    Refuses non-Test imports, assistant labels, changed pixels and conflicting
    duplicates. Coverage gaps are returned, not filled.
    """
    expected = {t['tileId']: t for t in protocol['test_tiles']}
    gt, provenance = {}, {}
    for folder in import_dirs:
        folder = Path(folder)
        if (folder / 'INCOMPLETE').exists():
            raise ValueError(f'Incomplete import: {folder}')
        audit = json.loads((folder / 'audit.json').read_text())
        if audit['summary']['split'] != 'test':
            raise ValueError(f'Not a Test import: {folder}')
        for record in audit['images']:
            tile_id = record['tileId']
            if tile_id not in expected or record['split'] != 'test':
                raise ValueError(f'Unknown or non-Test tile: {tile_id}')
            if record.get('annotation_source', 'human_reported') != 'human_reported':
                raise ValueError(f'Only human Test labels are admissible: {tile_id}')
            if record['original_png_sha256'] != expected[tile_id]['png_sha256']:
                raise ValueError(f'Import pixels differ from the protocol: {tile_id}')
            boxes = [{k: b[k] for k in ('x', 'y', 'w', 'h')} for b in record['boxes']]
            if tile_id in gt:
                if sorted(map(json.dumps, boxes)) != sorted(map(json.dumps, gt[tile_id])):
                    raise ValueError(f'Conflicting duplicate Test labels for {tile_id}; resolve explicitly')
                provenance[tile_id].append(str(folder))
                continue
            gt[tile_id] = boxes
            provenance[tile_id] = [str(folder)]
    return gt, provenance


def coverage(protocol, gt):
    """Covered/missing Test IDs and per-era counts of the merged labels."""
    expected = [t['tileId'] for t in protocol['test_tiles']]
    missing = [i for i in expected if i not in gt]
    return {'expected': len(expected), 'covered': len(expected) - len(missing), 'missing': missing,
            'boxes': sum(len(v) for v in gt.values()),
            'empty_label_images': sum(1 for v in gt.values() if not v)}


def run(protocol_path, import_dirs, output, attestation):
    """Infer once with the frozen settings and write the final report."""
    protocol = load_protocol(protocol_path)
    gt, provenance = merge_imports(protocol, import_dirs)
    cover = coverage(protocol, gt)
    if cover['missing']:
        raise ValueError(f"All {cover['expected']} Test tiles are required; missing {cover['missing']}")
    if not attestation or len(attestation.strip()) < 20:
        raise ValueError('A written human attestation of full-image, prediction-blind Test review is required')
    output = Path(output)
    if output.exists():
        raise FileExistsError(f'Final Test output already exists (single-shot): {output}')
    output.mkdir(parents=True)
    (output / 'INCOMPLETE').write_text('Final Test evaluation incomplete.\n')
    from pipeline.preview_detector import native_box
    from pipeline.train_detector import local_sdk
    model_cfg = protocol['model']
    tiles = protocol['test_tiles']
    model = local_sdk()(str(ROOT / model_cfg['weights']))
    started = time.perf_counter()
    results = model.predict(source=[str(ROOT / t['image_path']) for t in tiles], imgsz=model_cfg['imgsz'],
                            conf=model_cfg['confidence'], iou=model_cfg['nms_iou'],
                            max_det=model_cfg['max_det'], device=model_cfg['device'], batch=2,
                            stream=True, save=False, verbose=False)
    images = []
    for tile, result in zip(tiles, results, strict=True):
        if Path(result.path).resolve() != (ROOT / tile['image_path']).resolve():
            raise ValueError('Unexpected prediction order')
        predictions = [native_box(b, float(s), float(c), result.orig_shape)
                       for b, s, c in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(),
                                          result.boxes.cls.cpu().tolist())]
        kept, matched, matched_predictions = match_image(gt[tile['tileId']], predictions,
                                                         model_cfg['confidence'], protocol['evaluation']['match_iou'])
        images.append({'tileId': tile['tileId'], 'mapYear': tile['mapYear'], 'source_map_id': tile['source_map_id'],
                       'ground_truth_boxes': len(gt[tile['tileId']]), 'predicted_boxes': len(kept),
                       'tp': len(matched), 'fp': len(kept) - len(matched), 'fn': len(gt[tile['tileId']]) - len(matched),
                       'false_positive_boxes': [b for i, b in enumerate(kept) if i not in matched_predictions],
                       'missed_ground_truth': [b for i, b in enumerate(gt[tile['tileId']]) if i not in matched],
                       'predictions': kept, 'ground_truth': gt[tile['tileId']],
                       'label_imports': provenance[tile['tileId']]})
    seconds = time.perf_counter() - started

    def f1(m):
        p, r = m['precision'], m['recall']
        return None if p is None or r is None or p + r == 0 else 2 * p * r / (p + r)

    overall = aggregate(images)
    overall['f1'] = f1(overall)
    slices = {}
    for key in ('mapYear', 'source_map_id'):
        for value in sorted({i[key] for i in images}, key=str):
            rows = [i for i in images if i[key] == value]
            m = aggregate(rows)
            m['f1'] = f1(m)
            slices[f'{key}={value}'] = m
    negatives = [i for i in images if i['ground_truth_boxes'] == 0]
    report = {'schema_version': 1, 'scope': protocol['evaluation']['scope'],
              'protocol': str(Path(protocol_path)), 'protocol_sha256': digest(protocol_path),
              'model': model_cfg, 'match_iou': protocol['evaluation']['match_iou'],
              'matching': protocol['evaluation']['matching'], 'test_consumed_at_utc': datetime.now(timezone.utc).isoformat(),
              'human_attestation': attestation.strip(), 'label_imports': [str(p) for p in import_dirs],
              'label_import_audit_sha256': {str(p): digest(Path(p) / 'audit.json') for p in import_dirs},
              'coverage': cover, 'overall': overall, 'slices': slices,
              'reviewed_negative_images': len(negatives),
              'false_positives_on_reviewed_negatives': sum(i['fp'] for i in negatives),
              'timing': {'seconds_total': round(seconds, 3), 'images': len(images),
                         'scope': 'streamed predict incl. image decode, batch 2, after model load',
                         'hardware': platform.platform(), 'processor': platform.processor()},
              'code_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'code_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
              'code_sha256': digest(__file__),
              'limits': ['Overlapping tiles are not independent wells', 'No geographic dedup in these counts',
                         'Recall is None for slices without positive GT', 'Single checkpoint; no seed variance'],
              'images': images}
    with (output / 'final_test_report.json').open('x') as stream:
        json.dump(report, stream, indent=1)
    (output / 'INCOMPLETE').unlink()
    return {k: report[k] for k in ('coverage', 'overall', 'slices', 'false_positives_on_reviewed_negatives', 'timing')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--imports', type=Path, nargs='+', required=True, help='Audited human Test import folders')
    parser.add_argument('--out', type=Path, help='Fresh output folder (required unless --coverage-only)')
    parser.add_argument('--attestation', help='Written human statement: full-image, prediction-blind review')
    parser.add_argument('--coverage-only', action='store_true', help='Validate protocol/imports and report gaps; no inference')
    args = parser.parse_args()
    if args.coverage_only:
        protocol = load_protocol(args.protocol)
        gt, _ = merge_imports(protocol, args.imports)
        result = coverage(protocol, gt)
    else:
        if args.out is None:
            parser.error('--out is required for evaluation')
        result = run(args.protocol, args.imports, args.out, args.attestation)
    print(json.dumps(result, indent=1, default=str))


if __name__ == '__main__':
    main()
