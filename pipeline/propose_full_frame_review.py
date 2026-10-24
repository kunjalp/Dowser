"""Unreviewed symbol proposals and review sheets for complete Train-frame annotation.

Master Plan section 6 (lookalike negatives, complete labels). Input is the
human-confirmed error-source queue; only frozen Train tiles are opened. Two
independent proposal sources are unioned so a reviewer can look for misses:

* the pinned YOLO detector at a low cutoff (its score is kept as evidence only);
* normalized cross-correlation with synthetic hollow-ring templates, which does
  not depend on any label or model and finds circles the detector skipped.

Nothing here is a label. Proposals are written with ``reviewed=false`` and must be
accepted or rejected by a separate visual review (``finalize`` subcommand). Box
geometry follows the measured human convention: ring ink extent plus ~2.5 px.
Runs in pipeline/.venv (OpenCV and Torch are available there, not in root .venv).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pipeline.train_detector import ROOT

# Synthetic ring radii (px, centre to stroke middle) bracketing the measured
# human ring extent of 10-23 px (median 13-14 px). Stroke ~1.6 px on these scans.
RING_RADII = (5.0, 6.0, 7.0, 8.0, 9.5)
RING_STROKE = 1.6
NCC_MIN = 0.42          # deliberately permissive: misses are worse than extra review
MERGE_PX = 7.0          # proposals closer than this describe the same object
# Per-side padding beyond the fitted ring ink. Calibrated on the 568 original
# human TRAIN boxes only (reviewed_v2; fit_box on matched ring peaks, n=532):
# median 3.9 px horizontally / 3.2 px vertically. Validation was not used.
BOX_MARGIN_PX = 3.5


def digest(path):
    """SHA-256 of a file, binding proposals to exact pixels/configs."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ring_template(radius, stroke=RING_STROKE):
    """Dark-on-white antialiased ring, float32 in [0,1]; size odd, centre exact."""
    half = int(math.ceil(radius + stroke + 3))
    yy, xx = np.mgrid[-half:half + 1, -half:half + 1].astype(np.float32)
    dist = np.hypot(xx, yy)
    ink = np.clip(1.0 - np.abs(dist - radius) / stroke, 0, 1)
    return (1.0 - ink).astype(np.float32)


def ncc_peaks(gray, radii=RING_RADII, minimum=NCC_MIN):
    """Local NCC maxima for each ring radius: list of (x, y, score, radius).

    Coordinates are pixel-edge native coordinates of the ring centre (template
    centre + 0.5), matching the native xywh box convention used elsewhere.
    """
    import cv2
    peaks = []
    for radius in radii:
        template = ring_template(radius)
        half = template.shape[0] // 2
        score = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        local = cv2.dilate(score, np.ones((7, 7), np.uint8))
        ys, xs = np.nonzero((score >= minimum) & (score >= local))
        for x, y in zip(xs, ys):
            peaks.append((float(x + half + 0.5), float(y + half + 0.5), float(score[y, x]), radius))
    return peaks


def fit_box(gray, cx, cy, radius_hint):
    """Fit a native xywh box to the ring ink around an approximate centre.

    Uses dark pixels in an annulus around the hint radius, so neighbouring lines
    and text mostly do not widen the box. Falls back to the hint radius when the
    ring is too faint. Returns (box, ink_extent_px).
    """
    height, width = gray.shape
    reach = int(radius_hint + 5)
    x0, x1 = max(0, int(cx) - reach), min(width, int(cx) + reach + 1)
    y0, y1 = max(0, int(cy) - reach), min(height, int(cy) + reach + 1)
    patch = gray[y0:y1, x0:x1]
    ys, xs = np.nonzero(patch < 0.6)
    px, py = xs + x0 + 0.5, ys + y0 + 0.5
    dist = np.hypot(px - cx, py - cy)
    keep = (dist > radius_hint - 2.5) & (dist < radius_hint + 2.5)
    if keep.sum() >= 8:
        left, right = px[keep].min() - 0.5, px[keep].max() + 0.5
        top, bottom = py[keep].min() - 0.5, py[keep].max() + 0.5
        # A partial ring (clipped or broken) must not shrink the box below the hint.
        span = 2 * (radius_hint + RING_STROKE / 2)
        if right - left < 0.7 * span or bottom - top < 0.7 * span:
            left, right = cx - span / 2, cx + span / 2
            top, bottom = cy - span / 2, cy + span / 2
    else:
        span = 2 * (radius_hint + RING_STROKE / 2)
        left, right, top, bottom = cx - span / 2, cx + span / 2, cy - span / 2, cy + span / 2
    extent = (right - left, bottom - top)
    left, top = max(0.0, left - BOX_MARGIN_PX), max(0.0, top - BOX_MARGIN_PX)
    right, bottom = min(float(width), right + BOX_MARGIN_PX), min(float(height), bottom + BOX_MARGIN_PX)
    return {'x': round(left, 2), 'y': round(top, 2), 'w': round(right - left, 2),
            'h': round(bottom - top, 2)}, extent


def radius_hint(proposal):
    """Ring radius for box fitting: NCC radius, else derived from the YOLO box.

    The YOLO-derived value is a fixed function of the stored YOLO box (2.5 px is
    the historical padding assumption), so refits stay reproducible when only the
    output margin changes.
    """
    if proposal['ncc_radius']:
        return proposal['ncc_radius']
    return max(4.5, min(proposal['yolo_box']['w'], proposal['yolo_box']['h']) / 2 - 2.5 - 0.8)


def colour_features(rgb, box):
    """Blue-ink and centre-fill fractions inside a box (review aids, not rules)."""
    x0, y0 = int(box['x']), int(box['y'])
    x1, y1 = int(math.ceil(box['x'] + box['w'])), int(math.ceil(box['y'] + box['h']))
    patch = rgb[y0:y1, x0:x1].astype(np.int16)
    if patch.size == 0:
        return {'blue_fraction': None, 'centre_dark_fraction': None}
    r, g, b = patch[..., 0], patch[..., 1], patch[..., 2]
    gray = patch.mean(axis=2)
    h, w = gray.shape
    centre = gray[h // 3:max(h // 3 + 1, 2 * h // 3), w // 3:max(w // 3 + 1, 2 * w // 3)]
    return {'blue_fraction': round(float(((b - np.maximum(r, g)) > 20).mean()), 4),
            'centre_dark_fraction': round(float((centre < 140).mean()), 4)}


def merge(proposals):
    """Greedy union of nearby proposals; YOLO and ring evidence are combined."""
    proposals = sorted(proposals, key=lambda p: -(p.get('yolo_confidence') or 0) - (p.get('ncc') or 0))
    merged = []
    for p in proposals:
        for m in merged:
            if math.hypot(p['cx'] - m['cx'], p['cy'] - m['cy']) < MERGE_PX:
                for key in ('yolo_confidence', 'ncc'):
                    if p.get(key) is not None and (m.get(key) is None or p[key] > m[key]):
                        m[key] = p[key]
                        if key == 'ncc':
                            m['ncc_radius'] = p['ncc_radius']
                            m['cx'], m['cy'] = p['cx'], p['cy']   # ring centre is more precise
                m['sources'] = sorted(set(m['sources']) | set(p['sources']))
                break
        else:
            merged.append(dict(p))
    return merged


def queue_tiles(queue_path, manifest_path):
    """Train tiles needing complete annotation, with manifest records; refuses others."""
    queue = json.loads(Path(queue_path).read_text())
    if queue.get('test_used'):
        raise ValueError('Queue must not derive from Test')
    manifest = {r['tileId']: r for r in map(json.loads, Path(manifest_path).read_text().splitlines())}
    rows = [r for r in queue['rows'] if r['review_status'] == 'needs_complete_image_annotation']
    for row in rows:
        if manifest[row['tileId']]['split'] != 'train':
            raise ValueError(f"Only frozen Train frames may be annotated: {row['tileId']}")
    return rows, manifest


def propose(queue_path, inference_config, output):
    """Write unreviewed proposals.json and review sheets for every queued frame."""
    config = json.loads(Path(inference_config).read_text())
    manifest_path = ROOT / config['manifest']
    if digest(manifest_path) != config['manifest_sha256'] or digest(ROOT / config['weights']) != config['weights_sha256']:
        raise ValueError('Inference pin identity mismatch')
    rows, manifest = queue_tiles(queue_path, manifest_path)
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    from pipeline.preview_detector import native_box
    from pipeline.train_detector import local_sdk
    model = local_sdk()(str(ROOT / config['weights']))
    records = []
    for row in rows:
        tile = manifest[row['tileId']]
        path = (manifest_path.parent / tile['image_path']).resolve()
        rgb = np.asarray(Image.open(path).convert('RGB'))
        gray = rgb.mean(axis=2).astype(np.float32) / 255.0
        result = next(iter(model.predict(source=str(path), imgsz=1024, conf=0.05, iou=0.7, max_det=1000,
                                         device=config['device'], verbose=False, save=False)))
        raw = []
        for b, s, c in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(),
                           result.boxes.cls.cpu().tolist()):
            box = native_box(b, float(s), float(c), result.orig_shape)
            raw.append({'cx': box['x'] + box['w'] / 2, 'cy': box['y'] + box['h'] / 2,
                        'yolo_confidence': round(float(s), 4), 'yolo_box': box, 'ncc': None,
                        'ncc_radius': None, 'sources': ['yolo_low_cutoff']})
        for x, y, score, radius in ncc_peaks(gray):
            raw.append({'cx': x, 'cy': y, 'yolo_confidence': None, 'ncc': round(score, 4),
                        'ncc_radius': radius, 'sources': ['ring_ncc']})
        proposals = merge(raw)
        for index, p in enumerate(sorted(proposals, key=lambda p: (p['cy'], p['cx'])), 1):
            box, extent = fit_box(gray, p['cx'], p['cy'], radius_hint(p))
            p.update({'proposal_id': index, 'fitted_box': box, 'ring_extent_px': [round(v, 2) for v in extent],
                      **colour_features(rgb, box)})
        proposals.sort(key=lambda p: p['proposal_id'])
        records.append({'tileId': tile['tileId'], 'mapYear': tile['mapYear'], 'sheetName': tile['sheetName'],
                        'valid_fraction': tile['valid_fraction'], 'image_path': str(path.relative_to(ROOT)),
                        'original_png_sha256': digest(path),
                        'human_false_detection_ids': row['human_false_detection_ids'],
                        'proposals': proposals})
        render_tile(output, rgb, records[-1])
        print(f"{tile['tileId']}: {len(proposals)} proposals", flush=True)
    payload = {'schema_version': 1, 'reviewed': False,
               'status': 'UNREVIEWED proposals; not labels, not negatives',
               'queue_sha256': digest(queue_path), 'inference_config_sha256': digest(inference_config),
               'checkpoint_sha256': config['weights_sha256'], 'manifest_sha256': config['manifest_sha256'],
               'yolo': {'conf': 0.05, 'nms_iou': 0.7, 'imgsz': 1024, 'max_det': 1000},
               'ring_ncc': {'radii_px': RING_RADII, 'stroke_px': RING_STROKE, 'minimum': NCC_MIN},
               'merge_px': MERGE_PX, 'box_margin_px': BOX_MARGIN_PX, 'code_sha256': digest(__file__),
               'test_used': False, 'validation_used': False, 'tiles': records}
    (output / 'proposals.json').write_text(json.dumps(payload, indent=1))
    return payload


def _font(size):
    """Default bitmap font scaled where supported; review sheets only."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_tile(output, rgb, record, columns=8, context=22, scale=4):
    """Crop galleries (IDs, YOLO score, NCC) and 2x quadrant overviews with IDs."""
    image = Image.fromarray(rgb)
    font, small = _font(13), _font(11)
    tile_dir = output / record['tileId']
    tile_dir.mkdir()
    proposals = record['proposals']
    cell = 2 * context * scale
    per_sheet = columns * 6
    for sheet_index in range(0, max(1, len(proposals)), per_sheet):
        chunk = proposals[sheet_index:sheet_index + per_sheet]
        if not chunk:
            break
        rows = math.ceil(len(chunk) / columns)
        sheet = Image.new('RGB', (columns * (cell + 4), rows * (cell + 20)), 'white')
        draw = ImageDraw.Draw(sheet)
        for k, p in enumerate(chunk):
            cx, cy = p['cx'], p['cy']
            crop = Image.new('RGB', (2 * context, 2 * context), (255, 255, 255))
            left, top = int(round(cx - context)), int(round(cy - context))
            box = (max(0, left), max(0, top), min(1024, left + 2 * context), min(1024, top + 2 * context))
            crop.paste(image.crop(box), (box[0] - left, box[1] - top))
            crop = crop.resize((cell, cell), Image.NEAREST)
            cd = ImageDraw.Draw(crop)
            b = p['fitted_box']
            cd.rectangle([(b['x'] - left) * scale, (b['y'] - top) * scale,
                          (b['x'] + b['w'] - left) * scale, (b['y'] + b['h'] - top) * scale],
                         outline=(0, 160, 255), width=1)
            gx, gy = (k % columns) * (cell + 4), (k // columns) * (cell + 20)
            sheet.paste(crop, (gx, gy + 18))
            yolo = '-' if p['yolo_confidence'] is None else f"{p['yolo_confidence']:.2f}"
            ncc = '-' if p['ncc'] is None else f"{p['ncc']:.2f}"
            draw.text((gx + 2, gy + 2), f"#{p['proposal_id']} y{yolo} r{ncc}", fill=(0, 0, 0), font=small)
        sheet.save(tile_dir / f'gallery_{sheet_index // per_sheet + 1:02d}.png')
    for qy in range(2):
        for qx in range(2):
            quad = image.crop((qx * 512, qy * 512, qx * 512 + 512, qy * 512 + 512)).resize((1024, 1024), Image.LANCZOS)
            draw = ImageDraw.Draw(quad)
            for p in proposals:
                x, y = (p['cx'] - qx * 512) * 2, (p['cy'] - qy * 512) * 2
                if -10 <= x <= 1034 and -10 <= y <= 1034:
                    draw.text((x + 12, y - 16), str(p['proposal_id']), fill=(0, 120, 255), font=font)
                    draw.line([(x - 4, y), (x + 4, y)], fill=(0, 120, 255))
            quad.save(tile_dir / f'quad_{qy}{qx}.png')


def gallery_selection(proposals, yolo_min=0.15, ncc_min=0.5):
    """Proposals shown in evidence galleries, strongest first.

    Weaker proposals are not discarded: the completeness pass over the whole
    frame is what guarantees unlisted circles are still found and added.
    """
    chosen = [p for p in proposals if (p['yolo_confidence'] or 0) >= yolo_min or (p['ncc'] or 0) >= ncc_min]
    return sorted(chosen, key=lambda p: (-(p['yolo_confidence'] or 0), -(p['ncc'] or 0)))


def review_sheets(proposals_path, output, columns=8, rows=6, context=28, scale=3):
    """Evidence-sorted crop galleries per tile for accept/reject decisions."""
    payload = json.loads(Path(proposals_path).read_text())
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    small = _font(11)
    cell = 2 * context * scale
    summary = {}
    for record in payload['tiles']:
        image = Image.open(ROOT / record['image_path']).convert('RGB')
        chosen = gallery_selection(record['proposals'])
        summary[record['tileId']] = len(chosen)
        tile_dir = output / record['tileId']
        tile_dir.mkdir()
        per_sheet = columns * rows
        for start in range(0, len(chosen), per_sheet):
            chunk = chosen[start:start + per_sheet]
            sheet = Image.new('RGB', (columns * (cell + 4), math.ceil(len(chunk) / columns) * (cell + 18)), 'white')
            draw = ImageDraw.Draw(sheet)
            for k, p in enumerate(chunk):
                left, top = int(round(p['cx'] - context)), int(round(p['cy'] - context))
                crop = Image.new('RGB', (2 * context, 2 * context), (255, 255, 255))
                box = (max(0, left), max(0, top), min(1024, left + 2 * context), min(1024, top + 2 * context))
                crop.paste(image.crop(box), (box[0] - left, box[1] - top))
                crop = crop.resize((cell, cell), Image.NEAREST)
                b = p['fitted_box']
                ImageDraw.Draw(crop).rectangle(
                    [(b['x'] - left) * scale, (b['y'] - top) * scale,
                     (b['x'] + b['w'] - left) * scale, (b['y'] + b['h'] - top) * scale],
                    outline=(0, 160, 255), width=1)
                gx, gy = (k % columns) * (cell + 4), (k // columns) * (cell + 18)
                sheet.paste(crop, (gx, gy + 16))
                yolo = '-' if p['yolo_confidence'] is None else f"{p['yolo_confidence']:.2f}"
                ncc = '-' if p['ncc'] is None else f"{p['ncc']:.2f}"
                draw.text((gx + 2, gy + 1), f"#{p['proposal_id']} y{yolo} r{ncc}", fill=(0, 0, 0), font=small)
            sheet.save(tile_dir / f'sel_{start // per_sheet + 1:02d}.png')
    return summary


def accepted_boxes(record, decision):
    """Native boxes for accepted proposals plus manually added ring centres."""
    image = np.asarray(Image.open(ROOT / record['image_path']).convert('RGB'))
    gray = image.mean(axis=2).astype(np.float32) / 255.0
    by_id = {p['proposal_id']: p for p in record['proposals']}
    unknown = set(decision.get('accept', [])) - set(by_id)
    if unknown:
        raise ValueError(f"{record['tileId']}: unknown proposal IDs {sorted(unknown)}")
    boxes = []
    for pid in decision.get('accept', []):
        # Refit from the stored centre so the current, Train-calibrated margin applies.
        p = by_id[pid]
        box, _ = fit_box(gray, p['cx'], p['cy'], radius_hint(p))
        boxes.append({**box, 'proposal_id': pid, 'origin': 'accepted_proposal'})
    for item in decision.get('add', []):
        x, y = float(item[0]), float(item[1])
        radius = float(item[2]) if len(item) > 2 else 6.5
        # Re-centre on the strongest ring response near the reviewer's click.
        best = None
        for r in RING_RADII:
            template = ring_template(r)
            half = template.shape[0] // 2
            x0, y0 = int(x) - half - 4, int(y) - half - 4
            window = gray[max(0, y0):y0 + 2 * half + 9, max(0, x0):x0 + 2 * half + 9]
            if window.shape[0] < template.shape[0] or window.shape[1] < template.shape[1]:
                continue
            import cv2
            score = cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED)
            yy, xx = np.unravel_index(int(score.argmax()), score.shape)
            if best is None or score[yy, xx] > best[0]:
                best = (float(score[yy, xx]), max(0, x0) + xx + half + 0.5, max(0, y0) + yy + half + 0.5, r)
        if best and best[0] >= 0.35 and math.hypot(best[1] - x, best[2] - y) <= 5:
            cx, cy, radius = best[1], best[2], best[3]
        else:
            cx, cy = x, y
        box, _ = fit_box(gray, cx, cy, radius)
        boxes.append({**box, 'origin': 'manual_addition', 'reviewer_point': [x, y]})
    for b in boxes:
        if not (0 <= b['x'] and 0 <= b['y'] and b['x'] + b['w'] <= 1024 + 1e-6 and b['y'] + b['h'] <= 1024 + 1e-6
                and b['w'] > 0 and b['h'] > 0):
            raise ValueError(f"{record['tileId']}: invalid box {b}")
    return boxes


def completeness_sheets(proposals_path, decisions_path, output):
    """2x quadrants with accepted boxes and a 64 px native coordinate grid."""
    payload = json.loads(Path(proposals_path).read_text())
    decisions = json.loads(Path(decisions_path).read_text())['tiles']
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    font = _font(14)
    for record in payload['tiles']:
        decision = decisions.get(record['tileId'])
        if decision is None:
            continue
        boxes = accepted_boxes(record, decision)
        image = Image.open(ROOT / record['image_path']).convert('RGB')
        tile_dir = output / record['tileId']
        tile_dir.mkdir(exist_ok=True)
        full = image.copy()
        draw = ImageDraw.Draw(full)
        for g in range(0, 1025, 128):
            draw.line([(g, 0), (g, 1024)], fill=(255, 170, 0), width=1)
            draw.line([(0, g), (1024, g)], fill=(255, 170, 0), width=1)
            draw.text((g + 2, 2), str(g), fill=(200, 100, 0), font=font)
            draw.text((2, g + 2), str(g), fill=(200, 100, 0), font=font)
        for b in boxes:
            colour = (0, 170, 60) if b['origin'] == 'accepted_proposal' else (170, 0, 200)
            draw.rectangle([b['x'] - 1, b['y'] - 1, b['x'] + b['w'] + 1, b['y'] + b['h'] + 1], outline=colour, width=2)
        full.save(tile_dir / 'check_full.png')
        for qy in range(2):
            for qx in range(2):
                ox, oy = qx * 512, qy * 512
                quad = image.crop((ox, oy, ox + 512, oy + 512)).resize((1024, 1024), Image.LANCZOS)
                draw = ImageDraw.Draw(quad)
                for g in range(0, 513, 64):
                    draw.line([(g * 2, 0), (g * 2, 1024)], fill=(255, 170, 0), width=1)
                    draw.line([(0, g * 2), (1024, g * 2)], fill=(255, 170, 0), width=1)
                    draw.text((g * 2 + 2, 2), str(ox + g), fill=(200, 100, 0), font=font)
                    draw.text((2, g * 2 + 2), str(oy + g), fill=(200, 100, 0), font=font)
                for b in boxes:
                    colour = (0, 170, 60) if b['origin'] == 'accepted_proposal' else (170, 0, 200)
                    draw.rectangle([(b['x'] - ox) * 2, (b['y'] - oy) * 2,
                                    (b['x'] + b['w'] - ox) * 2, (b['y'] + b['h'] - oy) * 2], outline=colour, width=2)
                quad.save(tile_dir / f'check_{qy}{qx}.png')


def finalize(proposals_path, decisions_path, output):
    """Write assistant-reviewed annotations for build_train_mix from decisions.

    Only tiles whose decision status is ``complete`` are exported; excluded or
    unfinished tiles never become empty negatives. Labels are explicitly
    assistant_visual_review / human_verified=false.
    """
    payload = json.loads(Path(proposals_path).read_text())
    decisions_doc = json.loads(Path(decisions_path).read_text())
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    images, excluded = [], []
    for record in payload['tiles']:
        decision = decisions_doc['tiles'].get(record['tileId'])
        if decision is None or decision.get('status') != 'complete':
            excluded.append({'tileId': record['tileId'],
                             'reason': (decision or {}).get('notes', 'not reviewed to completion')})
            continue
        boxes = accepted_boxes(record, decision)
        images.append({'tileId': record['tileId'], 'annotation_source': 'assistant_visual_review',
                       'review_status': 'assistant_reviewed', 'human_verified': False,
                       'original_png_sha256': record['original_png_sha256'],
                       'review_notes': decision.get('notes', ''),
                       'ambiguous_left_as_background': decision.get('ambiguous', []),
                       'boxes': [{k: b[k] for k in ('x', 'y', 'w', 'h')} | {'origin': b['origin']} for b in boxes]})
    document = {'schema_version': 1,
                'authorization': decisions_doc['authorization'],
                'reviewer': decisions_doc['reviewer'],
                'class_names': ['well_symbol'], 'split': 'train',
                'box_coordinates': 'native 1024 px xywh pixel edges',
                'method': decisions_doc['method'],
                'policy': decisions_doc['policy'],
                'box_margin_px': BOX_MARGIN_PX,
                'box_margin_calibration': 'median human Train (reviewed_v2) padding beyond fitted ring ink; Val unused',
                'proposals_sha256': digest(proposals_path), 'decisions_sha256': digest(decisions_path),
                'code_sha256': digest(__file__), 'test_used': False, 'validation_used': False,
                'images': images, 'excluded_tiles': excluded}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(document, stream, indent=1)
    return {'complete_tiles': len(images), 'boxes': sum(len(i['boxes']) for i in images),
            'empty_reviewed_tiles': sum(not i['boxes'] for i in images), 'excluded_tiles': len(excluded)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('propose', help='Unreviewed proposals for queued Train frames')
    p.add_argument('--queue', type=Path,
                   default=ROOT / 'data/ml/rollout_diagnosis_v1/train_error_sources_human_confirmed.json')
    p.add_argument('--inference-config', type=Path, default=ROOT / 'pipeline/config/inference_cursor_translate.json')
    p.add_argument('--out', type=Path, required=True)
    s = sub.add_parser('sheets', help='Evidence-sorted review galleries')
    s.add_argument('--proposals', type=Path, required=True)
    s.add_argument('--out', type=Path, required=True)
    c = sub.add_parser('check', help='Completeness quadrants for reviewed decisions')
    c.add_argument('--proposals', type=Path, required=True)
    c.add_argument('--decisions', type=Path, required=True)
    c.add_argument('--out', type=Path, required=True)
    f = sub.add_parser('finalize', help='Assistant-reviewed annotations JSON from decisions')
    f.add_argument('--proposals', type=Path, required=True)
    f.add_argument('--decisions', type=Path, required=True)
    f.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'propose':
        payload = propose(args.queue, args.inference_config, args.out)
        result = {'tiles': len(payload['tiles']), 'proposals': sum(len(t['proposals']) for t in payload['tiles'])}
    elif args.command == 'sheets':
        result = review_sheets(args.proposals, args.out)
    elif args.command == 'check':
        completeness_sheets(args.proposals, args.decisions, args.out)
        result = {'written': str(args.out)}
    else:
        result = finalize(args.proposals, args.decisions, args.out)
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
