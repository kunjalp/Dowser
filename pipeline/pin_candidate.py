"""Write an explicit, unpromoted inference pin for a completed run.

The cutoff is the run's own Val-only F1 sweep selection (threshold_selection.json
from ``evaluate_preview --sweep``). The pin binds checkpoint and manifest hashes
so detect_sheet refuses mismatched weights. It never edits canonical pins.
"""
import argparse
import hashlib
import json
from pathlib import Path

from pipeline.train_detector import ROOT


def pin(run):
    """Return the pin dict for ``data/ml/runs/<run>``."""
    record = json.loads((ROOT / f'data/ml/runs/{run}/run.json').read_text())
    if record['state'] != 'completed':
        raise ValueError('Run is not completed')
    selection = json.loads((ROOT / f'data/ml/runs/{run}/preview/threshold_selection.json').read_text())
    if 'Test' not in selection['scope'] or 'untouched' not in selection['scope']:
        raise ValueError('Expected a Val-only sweep record')
    selected = selection['selected']
    weights = (Path(record['save_dir']) / 'weights/best.pt').resolve()
    manifest = ROOT / record['config']['manifest']
    return {'schema_version': 1, 'status': 'repair_v2_candidate_pending_review_not_promoted', 'training_run': run,
            'weights': str(weights.relative_to(ROOT)),
            'weights_sha256': hashlib.sha256(weights.read_bytes()).hexdigest(),
            'manifest': record['config']['manifest'],
            'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'confidence': selected['confidence'], 'nms_iou': 0.7, 'imgsz': 1024, 'max_det': 1000, 'device': 'mps',
            'selection': 'Val-only F1 sweep .05..95 step .01, IoU .5, tie -> higher cutoff; Test unused',
            'validation_at_selected': {k: selected[k] for k in ('tp', 'fp', 'fn', 'precision', 'recall', 'f1')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run')
    args = parser.parse_args()
    output = ROOT / f'pipeline/config/inference_{args.run}.json'
    if output.exists():
        raise FileExistsError(output)
    payload = pin(args.run)
    output.write_text(json.dumps(payload, indent=2) + '\n')
    print(output.name, payload['confidence'], payload['weights_sha256'][:12])


if __name__ == '__main__':
    main()
