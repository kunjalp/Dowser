"""A model comparison must not quietly change the evaluation labels or images."""

import copy
import unittest
import tempfile
from pathlib import Path

from pipeline.compare_previews import validation_pairs


class ComparisonTest(unittest.TestCase):
    def records(self):
        return [{'tileId':'same','split':'val','mapYear':1954,'ground_truth':[],
                 'image_path':'/same.png','predictions':[]}]

    def test_identical_validation_pairs_allow_different_predictions(self):
        a=self.records();b=copy.deepcopy(a);b[0]['predictions']=[{'confidence':.5}]
        self.assertEqual(len(validation_pairs(a,b)),1)

    def test_changed_labels_images_and_provenance_fail(self):
        for field,value in [('ground_truth',[{'x':1}]),('image_path','/other.png'),
                            ('annotation_source','assistant_visual_review'),('mapYear',1992)]:
            b=self.records();b[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                validation_pairs(self.records(),b)

    def test_test_duplicate_and_missing_ids_fail(self):
        for b in [self.records()*2,[],[dict(self.records()[0],split='test')]]:
            with self.assertRaises(ValueError):
                validation_pairs(self.records(),b)

    def test_identical_copies_across_worktrees_pass_but_changed_pixels_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            first=Path(folder)/'original.png';second=Path(folder)/'copy.png'
            first.write_bytes(b'fixed native pixels');second.write_bytes(first.read_bytes())
            a=self.records();b=self.records()
            a[0]['image_path']=str(first);b[0]['image_path']=str(second)
            self.assertEqual(len(validation_pairs(a,b)),1)
            second.write_bytes(b'changed image')
            with self.assertRaisesRegex(ValueError,'image sources differ'):
                validation_pairs(a,b)


if __name__=='__main__':
    unittest.main()
