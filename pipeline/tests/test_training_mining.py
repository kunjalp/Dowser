"""Review selection never includes held-outs, old labels, or huge dense batches."""

import unittest

from pipeline.mine_training_batch import eligible_tiles, choose_candidates


class TrainingMiningTest(unittest.TestCase):
    def tile(self, name, split='train', count=2, bounds=None, source='one'):
        return {'tileId':name,'split':split,'valid_fraction':1.,'source_map_id':source,
                'split_bounds_m':bounds or [0,0,10,10],
                'predictions':[{'confidence':.8} for _ in range(count)]}

    def test_only_full_content_unreviewed_train_is_eligible(self):
        rows=[self.tile('train'),self.tile('done'),self.tile('val','val'),
              self.tile('test','test'),self.tile('buffer','buffer'),
              dict(self.tile('padded'),valid_fraction=.2)]
        self.assertEqual([r['tileId'] for r in eligible_tiles(rows,{'done'})],['train'])

    def test_dense_unknowns_and_no_error_candidates_are_not_silently_selected(self):
        rows=[self.tile('dense',count=207),self.tile('no-proposals',count=0),self.tile('review')]
        self.assertEqual([r['tileId'] for r in choose_candidates(rows)],['review'])

    def test_cross_era_overlapping_coverage_does_not_fill_review_batch_twice(self):
        rows=[self.tile('a',source='old'),self.tile('b',source='new'),
              self.tile('c',source='new',bounds=[20,0,30,10])]
        chosen=choose_candidates(rows)
        self.assertEqual(len(chosen),2)
        self.assertIn('c',{r['tileId'] for r in chosen})

    def test_direct_selection_rejects_validation(self):
        with self.assertRaisesRegex(ValueError,'Train only'):
            choose_candidates([self.tile('held-out',split='val')])


if __name__=='__main__':
    unittest.main()
