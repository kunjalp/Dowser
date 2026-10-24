"""Freeze a new single-shot final-Test protocol for a selected candidate pin.

The Test tile list, annotation rules and evaluation rules are copied verbatim
from an existing frozen protocol, so only the model block changes. The earlier
protocol file is never modified; the new one refuses to overwrite and records
which protocol it supersedes. Run this BEFORE any Test inference of the
candidate; evaluate_final_test refuses unfrozen or mismatched protocols.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.train_detector import ROOT


def digest(path):
    """SHA-256 of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(base_protocol, pin_path, output, purpose, selection_record):
    """Write and return the new protocol dict."""
    base_protocol, pin_path = (Path(p) if Path(p).is_absolute() else ROOT / p for p in (base_protocol, pin_path))
    base = json.loads(Path(base_protocol).read_text())
    pin = json.loads(Path(pin_path).read_text())
    if not base['status'].startswith('frozen'):
        raise ValueError('Base protocol must be frozen')
    if digest(ROOT / pin['weights']) != pin['weights_sha256'] or pin['manifest_sha256'] != base['manifest_sha256']:
        raise ValueError('Pin checkpoint or manifest does not match')
    if pin['imgsz'] != 1024:
        raise ValueError('Native 1024 px required')
    protocol = {**base,
                'status': 'frozen_before_candidate_test_inference',
                'frozen_at_utc': datetime.now(timezone.utc).isoformat(),
                'purpose': purpose,
                'model': {'training_run': pin['training_run'], 'weights': pin['weights'],
                          'weights_sha256': pin['weights_sha256'], 'confidence': pin['confidence'],
                          'nms_iou': pin['nms_iou'], 'imgsz': pin['imgsz'], 'max_det': pin['max_det'],
                          'device': pin['device']},
                'source_pin': str(Path(pin_path).relative_to(ROOT)), 'source_pin_sha256': digest(pin_path),
                'supersedes_for_this_candidate': {'protocol': str(Path(base_protocol).relative_to(ROOT)),
                                                  'sha256': digest(base_protocol),
                                                  'note': 'earlier protocol kept unchanged for its own model'},
                'selection_record': selection_record,
                'test_state_at_freeze': 'human Test labels partially imported and structurally audited (counts only); '
                                        'no model Test inference by any candidate; Test unused for selection',
                'uncompleted': ['Remaining human Test tiles', 'Human review attestation',
                                'Single Test inference and report via pipeline.evaluate_final_test']}
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.write_text(json.dumps(protocol, indent=2) + '\n')
    return protocol


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--pin', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--purpose', required=True)
    parser.add_argument('--selection-record', required=True, help='Where the Train/Val-only selection is documented')
    args = parser.parse_args()
    protocol = freeze(args.base, args.pin, args.out, args.purpose, args.selection_record)
    print(json.dumps({k: protocol[k] for k in ('status', 'frozen_at_utc', 'model', 'source_pin')}, indent=1))


if __name__ == '__main__':
    main()
