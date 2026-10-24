"""One object cannot satisfy duplicate predictions; negatives have no recall."""

import unittest

from pipeline.evaluate_preview import evaluate


class FixedEvaluationTest(unittest.TestCase):
    def record(self, split='val', truth=True):
        box={'x':0,'y':0,'w':10,'h':10}
        return {'tileId':'fixture','mapYear':1954,'split':split,
                'ground_truth':[box] if truth else [],
                'predictions':[dict(box,confidence=.8),dict(box,confidence=.7)]}

    def test_duplicates_are_false_positives_and_train_is_excluded(self):
        report=evaluate([self.record(),self.record(split='train')])
        self.assertEqual(report['overall']['tp'],1)
        self.assertEqual(report['overall']['fp'],1)
        self.assertEqual(report['overall']['fn'],0)
        self.assertEqual(report['overall']['precision'],.5)

    def test_negatives_have_undefined_recall_and_threshold_filters_predictions(self):
        report=evaluate([self.record(truth=False)],confidence=.75)
        self.assertEqual(report['overall']['fp'],1)
        self.assertIsNone(report['overall']['recall'])
        self.assertEqual(report['overall']['precision'],0)

    def test_nonoverlap_is_miss_and_test_inputs_fail(self):
        row=self.record()
        for box in row['predictions']:
            box['x']=100
        report=evaluate([row])
        self.assertEqual(report['overall']['fn'],1)
        self.assertEqual(report['overall']['tp'],0)
        with self.assertRaisesRegex(ValueError,'Only Train/Val'):
            evaluate([self.record(split='test')])


if __name__=='__main__':
    unittest.main()
