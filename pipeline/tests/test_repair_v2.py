"""Guards for final-Test merging, shared matching, candidate rules and review boxes."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline.candidate_regression import analyse
from pipeline.evaluate_final_test import coverage, merge_imports
from pipeline.evaluate_preview import match_image


def protocol(ids):
    return {'test_tiles': [{'tileId': i, 'png_sha256': f'sha-{i}'} for i in ids]}


def write_import(folder, records, split='test'):
    folder.mkdir(parents=True)
    (folder / 'audit.json').write_text(json.dumps({'summary': {'split': split}, 'images': records}))
    return folder


def record(tile_id, boxes, **extra):
    return {'tileId': tile_id, 'split': 'test', 'original_png_sha256': f'sha-{tile_id}',
            'boxes': [dict(zip('xywh', b)) for b in boxes], **extra}


class FinalTestMergeTests(unittest.TestCase):
    def test_merges_by_tile_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write_import(Path(tmp) / 'a', [record('t1', [(1, 2, 10, 10)])])
            b = write_import(Path(tmp) / 'b', [record('t2', [])])
            gt, provenance = merge_imports(protocol(['t1', 't2', 't3']), [a, b])
            self.assertEqual(set(gt), {'t1', 't2'})
            self.assertEqual(coverage(protocol(['t1', 't2', 't3']), gt)['missing'], ['t3'])
            self.assertEqual(provenance['t1'], [str(a)])

    def test_identical_duplicates_allowed_conflicts_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write_import(Path(tmp) / 'a', [record('t1', [(1, 2, 10, 10)])])
            same = write_import(Path(tmp) / 'same', [record('t1', [(1, 2, 10, 10)])])
            other = write_import(Path(tmp) / 'other', [record('t1', [(5, 2, 10, 10)])])
            gt, provenance = merge_imports(protocol(['t1']), [a, same])
            self.assertEqual(len(provenance['t1']), 2)
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                merge_imports(protocol(['t1']), [a, other])

    def test_refuses_assistant_labels_other_splits_and_changed_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            assistant = write_import(Path(tmp) / 'assistant',
                                     [record('t1', [], annotation_source='assistant_visual_review')])
            with self.assertRaisesRegex(ValueError, 'human'):
                merge_imports(protocol(['t1']), [assistant])
            val = write_import(Path(tmp) / 'val', [record('t1', [])], split='val')
            with self.assertRaisesRegex(ValueError, 'Not a Test import'):
                merge_imports(protocol(['t1']), [val])
            changed = write_import(Path(tmp) / 'changed', [{**record('t1', []), 'original_png_sha256': 'x'}])
            with self.assertRaisesRegex(ValueError, 'pixels'):
                merge_imports(protocol(['t1']), [changed])


class SharedMatchingTests(unittest.TestCase):
    def test_confidence_order_one_to_one(self):
        gt = [{'x': 0, 'y': 0, 'w': 10, 'h': 10}]
        predictions = [{'x': 0, 'y': 0, 'w': 10, 'h': 10, 'confidence': .6},
                       {'x': 1, 'y': 0, 'w': 10, 'h': 10, 'confidence': .9},
                       {'x': 50, 'y': 50, 'w': 10, 'h': 10, 'confidence': .3}]
        kept, matched, matched_predictions = match_image(gt, predictions, .5, .5)
        self.assertEqual([p['confidence'] for p in kept], [.9, .6])
        self.assertEqual(matched, {0})
        self.assertEqual(matched_predictions, {0})


class CandidateRegressionTests(unittest.TestCase):
    def write_csv(self, path, rows):
        fields = ['detectionId', 'lat', 'lon', 'year', 'confidence', 'tileId', 'x', 'y', 'w', 'h']
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_rules_and_known_false_tracking(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            base = {'year': 1954, 'w': 18, 'h': 18}
            # a/b: same symbol on overlapping tiles (~11 m apart) -> one group next to a well.
            # c: isolated and far from wells -> candidate; it is the confirmed-false symbol.
            reference = [{**base, 'detectionId': 'a', 'lat': 35.40000, 'lon': -119.00000, 'confidence': .9, 'tileId': 'T1', 'x': 10, 'y': 10},
                         {**base, 'detectionId': 'b', 'lat': 35.40010, 'lon': -119.00000, 'confidence': .8, 'tileId': 'T2', 'x': 10, 'y': 800},
                         {**base, 'detectionId': 'c', 'lat': 35.41000, 'lon': -119.00000, 'confidence': .85, 'tileId': 'T1', 'x': 500, 'y': 500}]
            self.write_csv(tmp / 'reference.csv', reference)
            (tmp / 'wells.jsonl').write_text(json.dumps({'lat': 35.40005, 'lon': -119.0, 'locationQuality': 'good'}) + '\n')
            with (tmp / 'reviews.csv').open('w') as stream:
                stream.write('detectionId\nc\n')
            (tmp / 'queue.json').write_text(json.dumps({'rows': [{'detectionId': 'c', 'detectionIds': ['c']}]}))
            (tmp / 'train').mkdir()
            (tmp / 'train/audit.json').write_text(json.dumps({'images': [{'tileId': 'T1'}]}))
            report = analyse(tmp / 'reference.csv', tmp / 'wells.jsonl', tmp / 'reference.csv',
                             tmp / 'reviews.csv', tmp / 'queue.json', tmp / 'train', 'test')
            self.assertEqual((report['raw_detections'], report['groups'], report['candidate_groups']), (3, 2, 1))
            self.assertEqual(report['candidate_groups_known_false'], 1)
            self.assertEqual(report['candidate_groups_all_tiles_in_train_import'], 1)
            # A new export that shifts c by 2 px still counts as the same false symbol;
            # one that drops it removes the candidate.
            shifted = [r if r['detectionId'] != 'c' else {**r, 'detectionId': 'c2', 'x': 502} for r in reference]
            self.write_csv(tmp / 'shifted.csv', shifted)
            again = analyse(tmp / 'shifted.csv', tmp / 'wells.jsonl', tmp / 'reference.csv',
                            tmp / 'reviews.csv', tmp / 'queue.json', tmp / 'train', 'test')
            self.assertEqual(again['known_false_still_candidates'], 1)
            self.write_csv(tmp / 'dropped.csv', reference[:2])
            gone = analyse(tmp / 'dropped.csv', tmp / 'wells.jsonl', tmp / 'reference.csv',
                           tmp / 'reviews.csv', tmp / 'queue.json', tmp / 'train', 'test')
            self.assertEqual((gone['candidate_groups'], gone['known_false_still_detected_anywhere']), (0, 0))


class ReviewBoxTests(unittest.TestCase):
    def test_fit_box_follows_ring_with_calibrated_margin(self):
        from pipeline.propose_full_frame_review import BOX_MARGIN_PX, fit_box, ring_template
        gray = np.ones((64, 64), np.float32)
        ring = ring_template(6.5)
        h = ring.shape[0] // 2
        gray[32 - h:32 + h + 1, 32 - h:32 + h + 1] = ring
        box, extent = fit_box(gray, 32.5, 32.5, 6.5)
        self.assertAlmostEqual(box['x'] + box['w'] / 2, 32.5, delta=0.6)
        self.assertAlmostEqual(box['w'] - extent[0], 2 * BOX_MARGIN_PX, delta=1e-6)
        self.assertTrue(14 <= box['w'] <= 22)


if __name__ == '__main__':
    unittest.main()
