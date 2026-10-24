"""A model comparison must not quietly change the evaluation labels or images."""

import copy
import unittest

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


if __name__=='__main__':
    unittest.main()
