"""Assistant supervision must not overwrite human data or become held-out truth."""

import unittest

from pipeline.build_train_mix import check_assistant_record


class TrainMixTest(unittest.TestCase):
    def record(self):
        return {'tileId':'addition','annotation_source':'assistant_visual_review',
                'review_status':'assistant_reviewed','human_verified':False,
                'boxes':[{'x':100,'y':200,'w':14,'h':14}]}

    def test_explicit_assistant_review_preserves_native_box(self):
        result=check_assistant_record(self.record(),{'addition':{'split':'train'}},set())
        self.assertEqual(result,[{'row':1,'x':100.,'y':200.,'w':14.,'h':14.}])

    def test_heldouts_and_human_overwrites_fail(self):
        for split in ['val','test','buffer']:
            with self.assertRaises(ValueError):
                check_assistant_record(self.record(),{'addition':{'split':split}},set())
        with self.assertRaisesRegex(ValueError,'overwrite'):
            check_assistant_record(self.record(),{'addition':{'split':'train'}},{'addition'})

    def test_automatic_proposals_cannot_be_promoted_or_called_human(self):
        for field,value in [('review_status','unreviewed'),('human_verified',True),
                            ('annotation_source','model_predictions')]:
            with self.assertRaises(ValueError):
                check_assistant_record(dict(self.record(),**{field:value}),{'addition':{'split':'train'}},set())

    def test_assistant_negative_requires_same_explicit_review(self):
        r=dict(self.record(),boxes=[])
        self.assertEqual(check_assistant_record(r,{'addition':{'split':'train'}},set()),[])
        with self.assertRaises(ValueError):
            check_assistant_record(dict(r,review_status='unknown'),{'addition':{'split':'train'}},set())


if __name__=='__main__':
    unittest.main()
