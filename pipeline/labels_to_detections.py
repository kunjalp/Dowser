"""Convert audited native model boxes to Ryann's CSV, crops and sanity receipt.

Adapted from Ryann's labels_to_detections.py (received 2026-10-24). This version
uses our JSONL tile manifest and exact per-tile WKT/affine; source GeoTIFF pixels
are verified before export. It intentionally exports model detections only.
Human fallback remains a separate, explicit future command, not a silent default.
Run with the root .venv; no Torch/Pandas/GeoPandas installation is required.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from PIL import Image
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.windows import Window
from scipy.spatial import cKDTree

from pipeline.geo import box_center_to_wgs84, neatline_polygon, transformer
from pipeline.prepare_dataset import SOURCE_FILES

ROOT = Path(__file__).resolve().parents[1]
CSV_FIELDS = ['detectionId', 'lat', 'lon', 'year', 'confidence', 'crop', 'quadName',
              'source', 'tileId', 'mapYear', 'className', 'x', 'y', 'w', 'h']


def digest(path):
    """Return a source identity without interpreting its contents."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_crop(image, box, output):
    """Save a square 128 px evidence crop; white padding keeps edge symbols centered."""
    cx, cy = box['x'] + box['w'] / 2, box['y'] + box['h'] / 2
    half = math.ceil(max(24, max(box['w'], box['h']) * 1.5))
    left, top = math.floor(cx) - half, math.floor(cy) - half
    right, bottom = left + 2 * half, top + 2 * half
    valid = (max(0, left), max(0, top), min(image.width, right), min(image.height, bottom))
    result = Image.new('RGB', (2 * half, 2 * half), 'white')
    result.paste(image.crop(valid), (valid[0] - left, valid[1] - top))
    result.resize((128, 128), Image.Resampling.LANCZOS).save(output)


def detection_row(tile, box, detection_id, crop_path):
    """Build a CSV row from native xywh; center uses edges, with no extra half pixel."""
    if box.get('className') != 'well_symbol' or box.get('source') != 'model':
        raise ValueError('Require explicit model/well_symbol provenance')
    if not math.isfinite(box['confidence']) or not 0 < box['confidence'] <= 1:
        raise ValueError('Missing or invalid actual model confidence')
    location = box_center_to_wgs84(tile, box)
    return {'detectionId': detection_id, **location, 'year': tile['mapYear'],
            'mapYear': tile['mapYear'], 'confidence': box['confidence'],
            'crop': crop_path, 'quadName': tile['sheetName'], 'source': 'model',
            'tileId': tile['tileId'], 'className': 'well_symbol',
            **{key: box[key] for key in ['x', 'y', 'w', 'h']}}


def sanity_check(rows, wells_path):
    """Check nearest CalGEM distances in EPSG:3310; report missing data explicitly.

    This diagnostic is not an independent positional-accuracy measurement:
    dense well fields can make unrelated points look plausible. Uncertain
    reference locations are excluded. A low match fraction is a WARNING.
    """
    result = {'method': 'nearest documented well in EPSG:3310', 'radius_m': 100,
              'minimum_fraction': .2, 'geographic_accuracy_verified': False}
    if wells_path is None or not wells_path.exists():
        return {**result, 'status': 'SKIPPED', 'message': 'SKIPPED: CalGEM reference file is missing; sanity check not performed.'}
    if not rows:
        return {**result, 'status': 'WARNING', 'message': 'WARNING: no detections; sanity check cannot assess coordinates.'}
    if wells_path.suffix == '.jsonl':
        source = [json.loads(s) for s in wells_path.read_text().splitlines() if s.strip()]
    else:
        geo = json.loads(wells_path.read_text())
        source = [{**f['properties'], 'lon': f['geometry']['coordinates'][0],
                   'lat': f['geometry']['coordinates'][1]} for f in geo['features']
                  if f.get('geometry', {}).get('type') == 'Point']
    good = [r for r in source if r.get('locationQuality', 'good') == 'good'
            and all(isinstance(r.get(k), (float, int)) and math.isfinite(r[k]) for k in ['lat', 'lon'])
            and -90 <= r['lat'] <= 90 and -180 <= r['lon'] <= 180]
    if not good:
        return {**result, 'status': 'WARNING', 'message': 'WARNING: no usable CalGEM reference coordinates.'}
    op = Transformer.from_crs('EPSG:4326', 'EPSG:3310', always_xy=True)
    def xy(records):
        return np.column_stack(op.transform([r['lon'] for r in records], [r['lat'] for r in records], errcheck=True))
    distances, _ = cKDTree(xy(good)).query(xy(rows), k=1)
    fraction, median = float(np.mean(distances <= 100)), float(np.median(distances))
    status = 'WARNING' if fraction < .2 else 'PLAUSIBLE'
    message = (f'Sanity check {status}: {fraction:.1%} within 100 m of a documented CalGEM well; '
               f'median nearest distance {median:.1f} m. Proximity diagnostic only; map accuracy not independently verified.')
    return {**result, 'status': status, 'fraction_within_100m': fraction,
            'median_nearest_distance_m': median, 'detections': len(rows),
            'reference_rows': len(source), 'usable_reference_rows': len(good),
            'excluded_reference_rows': len(source) - len(good),
            'reference_sha256': digest(wells_path), 'message': message}


def verify_tile(tile, image, src, polygon):
    """Reject mismatched source offsets, transforms or prepared native RGB pixels."""
    col, row = tile['source_pixel_offset']
    expected = src.window_transform(Window(col, row, 1024, 1024))
    if not np.allclose(list(expected)[:6], tile['transform'], rtol=0, atol=1e-8):
        raise ValueError(f'Wrong per-tile transform: {tile["tileId"]}')
    if src.crs != rasterio.crs.CRS.from_wkt(tile['crs']):
        raise ValueError('Source CRS mismatch')
    pixels = src.read([1, 2, 3], window=Window(col, row, 1024, 1024), boundless=True, fill_value=255)
    valid = geometry_mask([polygon], (1024, 1024), Affine(*tile['transform']), invert=True)
    pixels[:, ~valid] = 255
    if not np.array_equal(np.asarray(image), pixels.transpose(1, 2, 0)):
        raise ValueError(f'Prepared image does not match masked GeoTIFF pixels: {tile["tileId"]}')
    return valid


def export(predictions_path, output, source_dir, wells_path=None):
    """Create a fresh local handoff; keep source transforms, years and model scores."""
    payload = json.loads(predictions_path.read_text())
    config = payload['config']
    manifest_path = ROOT / config['manifest']
    if payload['test_used'] or digest(manifest_path) != payload['manifest_sha256']:
        raise ValueError('Test use or manifest identity mismatch')
    if digest(ROOT / config['weights']) != payload['checkpoint_sha256']:
        raise ValueError('Checkpoint identity mismatch')
    manifest = {t['tileId']: t for t in map(json.loads, manifest_path.read_text().splitlines())}
    records = payload['images']
    expected_ids = {t['tileId'] for t in manifest.values() if t['split'] in {'train', 'val'}}
    if len(records) != len(expected_ids) or {r['tileId'] for r in records} != expected_ids:
        raise ValueError('Expected exactly the complete frozen Train/Val export scope')
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    output.mkdir(parents=True)
    (output / 'INCOMPLETE').write_text('Do not hand off this directory until export finishes.\n')
    (output / 'crops').mkdir()
    rows, tiles, operations, source_hashes = [], [], {}, {}
    rejected_padding, max_corner_error = 0, 0.0
    for map_id in sorted({manifest[r['tileId']]['source_map_id'] for r in records}):
        path = source_dir / (SOURCE_FILES[map_id] + '.tif')
        group = [r for r in records if manifest[r['tileId']]['source_map_id'] == map_id]
        source_hashes[map_id] = digest(path)
        if any(source_hashes[map_id] != manifest[r['tileId']]['source_sha256'] for r in group):
            raise ValueError('Wrong source GeoTIFF version')
        xml = ET.parse(path.with_suffix('.xml')).getroot()
        nominal = [float(xml.findtext('.//' + k)) for k in ['westbc', 'southbc', 'eastbc', 'northbc']]
        with rasterio.open(path) as src:
            polygon = neatline_polygon(src.crs.to_wkt(), nominal)
            _, operations[map_id] = transformer(src.crs.to_wkt())
            for record in group:
                tile = manifest[record['tileId']]
                if tile['split'] not in {'train', 'val'} or tile['split'] != record['split']:
                    raise ValueError('Protected split must not be exported')
                image_path = ROOT / record['image_path']
                if digest(image_path) != record['image_sha256']:
                    raise ValueError('Prediction image changed')
                with Image.open(image_path) as original:
                    image = original.convert('RGB')
                valid = verify_tile(tile, image, src, polygon)
                col, row = tile['source_pixel_offset']
                residual = max(max(abs(a-b) for a, b in zip(
                    ~src.transform * (Affine(*tile['transform']) * (x, y)), (col+x, row+y)))
                    for x, y in [(0, 0), (1024, 0), (0, 1024), (1024, 1024)])
                max_corner_error = max(max_corner_error, residual)
                if residual > 1:
                    raise ValueError('Source/tile corner reconstruction exceeds one pixel')
                tiles.append(tile)
                boxes = sorted(record['predictions'], key=lambda b: (-b['confidence'], b['x'], b['y']))
                for index, box in enumerate(boxes):
                    detection_id = f"{config['training_run']}-{tile['tileId']}-{index:04d}"
                    crop_name = detection_id + '.png'
                    entry = detection_row(tile, box, detection_id, 'pipeline/data/crops/' + crop_name)
                    if entry['confidence'] < config['confidence']:
                        raise ValueError('Detection is below pinned confidence')
                    cx, cy = box['x'] + box['w']/2, box['y'] + box['h']/2
                    if not valid[min(1023, int(cy)), min(1023, int(cx))]:
                        rejected_padding += 1
                        continue
                    save_crop(image, box, output / 'crops' / crop_name)
                    rows.append(entry)
    with (output / 'detections.csv').open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with (output / 'detections.jsonl').open('x') as stream:
        for row in rows:
            d = {k: row[k] for k in ['detectionId', 'tileId', 'mapYear', 'className', 'confidence', 'lat', 'lon', 'source']}
            d['box'] = {k: row[k] for k in ['x', 'y', 'w', 'h']}
            d['cropPath'] = row['crop']  # Local evidence path, deliberately not a published cropUrl.
            stream.write(json.dumps(d) + '\n')
    (output / 'tiles.jsonl').write_text(''.join(json.dumps(t) + '\n' for t in tiles))
    check = sanity_check(rows, wells_path)
    (output / 'sanity_check.json').write_text(json.dumps(check, indent=2))
    (output / 'sanity_check.txt').write_text(check['message'] + '\n')
    receipt = {'training_run': config['training_run'], 'inference_config': config,
               'predictions_sha256': digest(predictions_path), 'manifest_sha256': digest(manifest_path),
               'source_sha256': source_hashes, 'coordinate_operations': operations,
               'export_code_sha256': digest(__file__), 'geo_code_sha256': digest(ROOT / 'pipeline/geo.py'),
               'tiles': len(tiles), 'tiles_by_split': dict(Counter(t['split'] for t in tiles)),
               'detections': len(rows), 'detections_by_map': dict(Counter(manifest[r['tileId']]['source_map_id'] for r in rows)),
               'detections_by_year': dict(Counter(r['year'] for r in rows)),
               'padding_center_detections_rejected': rejected_padding,
               'maximum_corner_residual_px': max_corner_error,
               'test_used': False, 'excluded_splits': ['test', 'buffer'],
               'coverage': 'Partial-region integration handoff on all frozen Train/Val tiles; not full-sheet or Test inference.',
               'dedup_applied': False, 'source': 'model', 'sanity': check,
               'independent_test_evaluation': False, 'actual_map_control_checks_completed': False}
    (output / 'export_receipt.json').write_text(json.dumps(receipt, indent=2))
    (output / 'INCOMPLETE').unlink()
    print(f'Exported {len(rows)} model detections / crops from {len(tiles)} Train/Val tiles across {len(source_hashes)} editions.')
    print(check['message'])
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'data/research/maps')
    parser.add_argument('--wells', type=Path, help='CalGEM JSONL or Point FeatureCollection; uncertain rows excluded')
    args = parser.parse_args()
    export(args.predictions, args.out, args.source_dir, args.wells)


if __name__ == '__main__':
    main()
