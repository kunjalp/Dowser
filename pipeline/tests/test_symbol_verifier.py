"""Guard native crop identity and Train-only learning without importing Torch."""
import unittest

import numpy as np
from PIL import Image

from pipeline.train_symbol_verifier import patch_tensor, require_train, choose_cutoff


class SymbolVerifierTests(unittest.TestCase):
    def test_calibration_cannot_trade_away_required_recall(self):
        point = choose_cutoff([.9, .8, .7, .1, .05]+[.08]*10,
                              [1]*5+[0]*10, positive_total=5, minimum_tp=5)
        self.assertEqual(point['tp'], 5)
        self.assertEqual(point['fp'], 10)
        self.assertEqual(point['fn'], 0)

    def test_calibration_counts_symbols_missed_by_first_stage(self):
        point = choose_cutoff([.9, .8, .1], [1, 1, 0], positive_total=3, minimum_tp=2)
        self.assertEqual((point['tp'], point['fp'], point['fn']), (2, 0, 1))

    def test_white_background_remains_zero_ink(self):
        result = patch_tensor(Image.new('RGB', (100, 100), 'white'),
                              {'x': 40, 'y': 40, 'w': 10, 'h': 10})
        self.assertTrue(np.isfinite(result).all())
        self.assertEqual(float(result.max()), 0)

    def test_edge_symbol_stays_centered_in_white_padding(self):
        image = Image.new('RGB', (100, 100), 'white')
        for x in range(4):
            for y in range(4):
                image.putpixel((x, y), (0, 0, 0))
        result = patch_tensor(image, {'x': 0, 'y': 0, 'w': 4, 'h': 4})
        self.assertGreater(float(result[:, 24, 24].mean()), .9)
        self.assertEqual(float(result[:, 0, 0].mean()), 0)

    def test_invalid_native_geometry_is_rejected(self):
        image = Image.new('RGB', (100, 100), 'white')
        for box in [{'x': -1, 'y': 0, 'w': 5, 'h': 5},
                    {'x': 99, 'y': 0, 'w': 5, 'h': 5},
                    {'x': 0, 'y': 0, 'w': 0, 'h': 5},
                    {'x': float('nan'), 'y': 0, 'w': 5, 'h': 5}]:
            with self.subTest(box=box), self.assertRaises(ValueError):
                patch_tensor(image, box)

    def test_protected_splits_never_enter_verifier_training(self):
        require_train({'split': 'train'})
        for split in ['val', 'test', 'buffer', 'unknown']:
            with self.subTest(split=split), self.assertRaises(ValueError):
                require_train({'split': split})


if __name__ == '__main__':
    unittest.main()
