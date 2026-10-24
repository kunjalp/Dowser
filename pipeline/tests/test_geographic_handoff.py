"""Exercise geography, protected-split exclusion, crops and real CSV serialization."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin

from pipeline.detect_sheet import exportable_tiles
from pipeline.labels_to_detections import detection_row, export, sanity_check, save_crop


class GeographicHandoffTests(unittest.TestCase):
    def tile(self):
        return {'tileId': 'train-tile', 'split': 'train', 'mapYear': 1954,
                'sheetName': 'Oil Center', 'source_map_id': 'usgs_293661',
                'source_pixel_offset': [0, 0], 'widthPx': 1024, 'heightPx': 1024,
                'crs': rasterio.crs.CRS.from_epsg(4326).to_wkt(),
                'transform': list(from_origin(-119.1, 35.4, .00001, .00001))[:6]}

    def box(self):
        return {'x': 100, 'y': 200, 'w': 14, 'h': 10, 'confidence': .9,
                'source': 'model', 'className': 'well_symbol'}

    def test_native_box_center_has_no_extra_half_pixel(self):
        row = detection_row(self.tile(), self.box(), 'id', 'crop.png')
        self.assertAlmostEqual(row['lon'], -119.1 + 107 * .00001, places=9)
        self.assertAlmostEqual(row['lat'], 35.4 - 205 * .00001, places=9)
        self.assertEqual(row['confidence'], .9)

    def test_invalid_scores_and_ground_truth_are_not_silently_model(self):
        for changes in [{'confidence': float('nan')}, {'confidence': 0},
                        {'source': 'ground_truth'}, {'w': -1}, {'x': 1023}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                detection_row(self.tile(), {**self.box(), **changes}, 'id', 'crop')

    def test_protected_images_need_not_exist_and_are_never_selected(self):
        tiles = [{**self.tile(), 'tileId': split, 'split': split}
                 for split in ['train', 'val', 'test', 'buffer']]
        self.assertEqual([t['tileId'] for t in exportable_tiles(tiles)], ['train', 'val'])
        with self.assertRaises(ValueError):
            exportable_tiles([self.tile(), self.tile()])

    def test_edge_crop_pads_white_without_moving_symbol_to_corner(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Image.new('RGB', (1024, 1024), 'white')
            image.putpixel((0, 0), (0, 0, 0))
            path = Path(folder) / 'crop.png'
            save_crop(image, {'x': 0, 'y': 0, 'w': 1, 'h': 1}, path)
            with Image.open(path) as result:
                self.assertEqual(result.size, (128, 128))
                self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
                self.assertLess(min(result.getpixel((64, 64))), 255)

    def test_missing_sanity_reference_is_explicit(self):
        self.assertEqual(sanity_check([{'lat': 35.4, 'lon': -119.1}], None)['status'], 'SKIPPED')

    def test_sanity_uses_meters_and_excludes_uncertain_reference(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'wells.jsonl'
            records = [{'lat': 35.4, 'lon': -119.1, 'locationQuality': 'good'},
                       {'lat': 35.3, 'lon': -119.1, 'locationQuality': 'uncertain'}]
            path.write_text(''.join(json.dumps(r) + '\n' for r in records))
            result = sanity_check([{'lat': 35.3, 'lon': -119.1}], path)
            self.assertEqual(result['status'], 'WARNING')
            self.assertEqual(result['usable_reference_rows'], 1)
            self.assertEqual(result['excluded_reference_rows'], 1)
            self.assertGreater(result['median_nearest_distance_m'], 10000)

    def test_geotiff_to_csv_and_crop_with_test_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            # Export receipts hash their checkout's geo implementation as well
            # as data. Give the isolated fixture that same source identity.
            (root / 'pipeline').mkdir()
            (root / 'pipeline/geo.py').write_bytes((Path(__file__).parents[1] / 'geo.py').read_bytes())
            source = root / 'maps'
            source.mkdir()
            tif = source / 'oil_center_1954_reference.tif'
            tile = self.tile()
            with rasterio.open(tif, 'w', driver='GTiff', width=1024, height=1024,
                               count=3, dtype='uint8', crs='EPSG:4326',
                               transform=rasterio.Affine(*tile['transform'])) as dst:
                dst.write(np.full((3, 1024, 1024), 255, dtype=np.uint8))
            tif.with_suffix('.xml').write_text('<metadata><westbc>-119.1</westbc>'
                '<southbc>35.38976</southbc><eastbc>-119.08976</eastbc>'
                '<northbc>35.4</northbc></metadata>')
            image = root / 'tile.png'
            Image.new('RGB', (1024, 1024), 'white').save(image)
            tile['source_sha256'] = hashlib.sha256(tif.read_bytes()).hexdigest()
            weights = root / 'weights.pt'
            weights.write_bytes(b'fake weights identity; no model needed for export test')
            manifest = root / 'manifest.jsonl'
            manifest.write_text(json.dumps(tile) + '\n' + json.dumps({**tile, 'tileId': 'protected', 'split': 'test'}) + '\n')
            payload = {'test_used': False,
                       'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
                       'checkpoint_sha256': hashlib.sha256(weights.read_bytes()).hexdigest(),
                       'config': {'manifest': 'manifest.jsonl', 'weights': 'weights.pt',
                                  'confidence': .71, 'training_run': 'fixture'},
                       'images': [{'tileId': 'train-tile', 'split': 'train', 'image_path': 'tile.png',
                                   'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                                   'predictions': [self.box()]}]}
            predictions = root / 'predictions.json'
            predictions.write_text(json.dumps(payload))
            output = root / 'handoff'
            with patch('pipeline.labels_to_detections.ROOT', root):
                receipt = export(predictions, output, source)
                with self.assertRaises(FileExistsError):
                    export(predictions, output, source)
                payload['images'].append({**payload['images'][0], 'tileId': 'protected', 'split': 'test'})
                predictions.write_text(json.dumps(payload))
                with self.assertRaises(ValueError):
                    export(predictions, root / 'bad', source)
            rows = list(csv.DictReader((output / 'detections.csv').open()))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['source'], 'model')
            self.assertEqual(float(rows[0]['confidence']), .9)
            self.assertEqual(receipt['tiles'], 1)
            self.assertFalse(receipt['test_used'])
            self.assertEqual(receipt['sanity']['status'], 'SKIPPED')
            self.assertEqual(len(list((output / 'crops').glob('*.png'))), 1)
            self.assertFalse((output / 'INCOMPLETE').exists())


if __name__ == '__main__':
    unittest.main()
