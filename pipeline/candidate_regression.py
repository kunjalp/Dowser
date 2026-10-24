"""Post-CalGEM candidate regression for a detector export (Train/Val tiles only).

Why: Val precision does not measure the product's candidate list. Real well
symbols mostly match CalGEM and leave the list, so the unmatched remainder is
dominated by detector errors (62 of the shipped 64 candidates were confirmed
false by Ryann). This diagnostic re-applies the backend rules that reproduced
Ryann's counts exactly (chained 20 m dedup, confidence-weighted centre, nearest
good CalGEM location > 100 m => candidate; distances in EPSG:3310) and reports:

* raw/group/multi-edition/matched counts (matched groups are a recall proxy);
* candidate groups, split by whether every member tile was in the model's
  Train import (fit data) or at least one member came from an unseen tile;
* which of the 62 human-confirmed false symbols are still detected, located by
  native-box IoU >= .3 on the same tile against the shipped CSV boxes of every
  member of their original dedup group.

The confirmed-false set was used to choose Train frames, so its removal is a
regression check, not independent accuracy. No OSM ranking or production
write happens here. Run with the root .venv (pyproj/scipy).
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree

from pipeline.evaluate_preview import box_iou

ROOT = Path(__file__).resolve().parents[1]
DEDUP_M = 20.0
MATCH_M = 100.0
KNOWN_FALSE_IOU = 0.3


def digest(path):
    """SHA-256 of a file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_csv(path):
    """Rows with numeric geometry/score fields parsed."""
    rows = list(csv.DictReader(Path(path).open()))
    for r in rows:
        for key in ('lat', 'lon', 'confidence', 'x', 'y', 'w', 'h'):
            r[key] = float(r[key])
        r['year'] = int(float(r['year']))
    return rows


def groups_and_candidates(rows, wells_path):
    """Backend-equivalent chained dedup and CalGEM match; returns (groups, xy)."""
    to_m = Transformer.from_crs(4326, 3310, always_xy=True)
    back = Transformer.from_crs(3310, 4326, always_xy=True)
    xy = np.column_stack(to_m.transform([r['lon'] for r in rows], [r['lat'] for r in rows]))
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in sorted(cKDTree(xy).query_pairs(DEDUP_M)):
        a, b = find(a), find(b)
        if a != b:
            parent[b] = a
    members = collections.defaultdict(list)
    for i in range(len(rows)):
        members[find(i)].append(i)
    wells = [json.loads(s) for s in Path(wells_path).read_text().splitlines() if s.strip()]
    good = [w for w in wells if w.get('locationQuality') == 'good' and 'lat' in w and 'lon' in w]
    tree = cKDTree(np.column_stack(to_m.transform([w['lon'] for w in good], [w['lat'] for w in good])))
    groups = []
    for inds in members.values():
        inds = sorted(inds, key=lambda i: -rows[i]['confidence'])
        weights = [max(.01, rows[i]['confidence']) for i in inds]
        lon, lat = back.transform(*np.average(xy[inds], axis=0, weights=weights))
        lon, lat = round(lon, 6), round(lat, 6)
        distance, _ = tree.query(to_m.transform(lon, lat))
        groups.append({'detectionId': rows[inds[0]]['detectionId'], 'lat': lat, 'lon': lon,
                       'distance_m': round(float(distance), 1),
                       'candidate': round(float(distance), 1) > MATCH_M,
                       'editionsSeen': sorted({rows[i]['year'] for i in inds}),
                       'maxConfidence': rows[inds[0]]['confidence'],
                       'members': [rows[i]['detectionId'] for i in inds],
                       'tiles': sorted({rows[i]['tileId'] for i in inds})})
    return groups, {'wells_rows': len(wells), 'wells_good': len(good)}


def known_false_targets(reference_csv, reviews_csv, reference_queue):
    """Boxes of every shipped member of each human-confirmed false candidate group."""
    reference = {r['detectionId']: r for r in read_csv(reference_csv)}
    false_ids = [r['detectionId'] for r in csv.DictReader(Path(reviews_csv).open())]
    queue = json.loads(Path(reference_queue).read_text())['rows']
    members_of = {r['detectionId']: r['detectionIds'] for r in queue}
    targets = {}
    for fid in false_ids:
        targets[fid] = [reference[m] for m in members_of.get(fid, [fid])]
    return targets


def analyse(detections_csv, wells, reference_csv, reviews_csv, reference_queue, train_import, label):
    """Full regression report for one detector export."""
    rows = read_csv(detections_csv)
    groups, wells_info = groups_and_candidates(rows, wells)
    train_ids = {r['tileId'] for r in json.loads((Path(train_import) / 'audit.json').read_text())['images']}
    targets = known_false_targets(reference_csv, reviews_csv, reference_queue)
    by_tile = collections.defaultdict(list)
    for r in rows:
        by_tile[r['tileId']].append(r)
    hit_of = {}          # new detectionId -> list of known-false IDs it reproduces
    still_detected = {}
    for fid, boxes in targets.items():
        found = []
        for target in boxes:
            for r in by_tile.get(target['tileId'], []):
                if box_iou(r, target) >= KNOWN_FALSE_IOU:
                    found.append(r['detectionId'])
                    hit_of.setdefault(r['detectionId'], []).append(fid)
        still_detected[fid] = sorted(set(found))
    candidates = [g for g in groups if g['candidate']]
    for g in candidates:
        g['known_false'] = sorted({fid for m in g['members'] for fid in hit_of.get(m, [])})
        g['all_member_tiles_in_train_import'] = all(t in train_ids for t in g['tiles'])
    unseen = [g for g in candidates if not g['all_member_tiles_in_train_import']]
    report = {
        'label': label, 'scope': 'Train/Val tiles only; regression diagnostic, not Test or field accuracy',
        'detections_csv': str(detections_csv), 'detections_sha256': digest(detections_csv),
        'reference_csv_sha256': digest(reference_csv), 'reviews_sha256': digest(reviews_csv),
        'wells_sha256': digest(wells), **wells_info,
        'rules': {'dedup_m': DEDUP_M, 'match_m': MATCH_M, 'crs': 'EPSG:3310',
                  'known_false_match': f'same tile, native IoU >= {KNOWN_FALSE_IOU}'},
        'raw_detections': len(rows), 'groups': len(groups),
        'multi_edition_groups': sum(len(g['editionsSeen']) > 1 for g in groups),
        'calgem_matched_groups': sum(not g['candidate'] for g in groups),
        'candidate_groups': len(candidates),
        'candidate_groups_known_false': sum(bool(g['known_false']) for g in candidates),
        'candidate_groups_all_tiles_in_train_import': len(candidates) - len(unseen),
        'candidate_groups_with_unseen_tile': len(unseen),
        'candidate_groups_with_unseen_tile_known_false': sum(bool(g['known_false']) for g in unseen),
        'known_false_total': len(targets),
        'known_false_still_detected_anywhere': sum(bool(v) for v in still_detected.values()),
        'known_false_still_candidates': len({fid for g in candidates for fid in g['known_false']}),
        'train_import': str(train_import), 'train_tiles': len(train_ids),
        'feedback_used_for_training': True,
        'candidates': candidates, 'known_false_detections': still_detected}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detections', type=Path, required=True)
    parser.add_argument('--train-import', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--wells', type=Path, default=ROOT / 'data/ml/ryann_calgem_v1/calgem_wells.jsonl')
    parser.add_argument('--reference-csv', type=Path, default=ROOT / 'pipeline/data/ryann_cursor_translate_v1/detections.csv')
    parser.add_argument('--reviews', type=Path, default=ROOT / 'data/ml/rollout_diagnosis_v1/ryann_confirmed_false_reviews.csv')
    parser.add_argument('--reference-queue', type=Path, default=ROOT / 'data/ml/rollout_diagnosis_v1/candidate_review_queue.json')
    args = parser.parse_args()
    report = analyse(args.detections, args.wells, args.reference_csv, args.reviews, args.reference_queue,
                     args.train_import, args.label)
    if args.out.exists():
        raise FileExistsError(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k not in ('candidates', 'known_false_detections')}, indent=1))


if __name__ == '__main__':
    main()
