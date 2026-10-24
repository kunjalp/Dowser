"""Build versioned Train imports, preserving human/assistant label provenance.

Assistant labels require explicit visual-review records and native-image hashes.
This module never generates labels from predictions or changes frozen splits.
"""

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

from pipeline.audit_annotations import parse_labels
from pipeline.train_detector import ROOT, read_import


def check_assistant_record(record, manifest, existing_ids):
    """Reject unknown/held-out IDs, overwrites, unaudited guesses and bad geometry."""
    tile_id=record['tileId']
    if tile_id not in manifest or manifest[tile_id]['split']!='train':
        raise ValueError('Only frozen Train additions are permitted')
    if tile_id in existing_ids:
        raise ValueError('Cannot overwrite existing human labels')
    if (record.get('annotation_source')!='assistant_visual_review'
            or record.get('review_status')!='assistant_reviewed'
            or record.get('human_verified') is not False):
        raise ValueError('Require explicit assistant provenance; never claim human review')
    boxes=[]
    for index,box in enumerate(record['boxes'],1):
        x,y,w,h=(box[key] for key in ['x','y','w','h'])
        rows,_=parse_labels(f'0 {(x+w/2)/1024} {(y+h/2)/1024} {w/1024} {h/1024}')
        rows[0]['row']=index
        boxes.extend(rows)
    return boxes


def build(config_path):
    """Combine an intact human import with explicitly selected assistant records."""
    config=json.loads(config_path.read_text())
    output=ROOT/config['output']
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite: {output}')
    dataset=ROOT/config['dataset']
    manifest_path=dataset/'manifest.jsonl'
    manifest={r['tileId']:r for r in map(json.loads,manifest_path.read_text().splitlines())}
    base=ROOT/config['human_import']
    original=json.loads((base/'audit.json').read_text())
    verified=read_import(base,'train',manifest)
    if set(verified['images_by_source'])!={'human_reported'}:
        raise ValueError('Base import must preserve the original human labels')
    additions_path=ROOT/config['assistant_annotations']
    payload=json.loads(additions_path.read_text())
    by_id={r['tileId']:r for r in payload['images']}
    if len(by_id)!=len(payload['images']) or len(set(config['include_ids']))!=len(config['include_ids']):
        raise ValueError('Duplicate annotation/addition IDs')
    records=copy.deepcopy(original['images'])
    sources={r['tileId']:base/'images/train'/(r['tileId']+'.png') for r in records}
    for r in records:
        r['annotation_source']='human_reported'
        r['source_audit_sha256']=verified['audit_sha256']
    for tile_id in config['include_ids']:
        r=by_id[tile_id]
        boxes=check_assistant_record(r,manifest,verified['ids'])
        image=dataset/manifest[tile_id]['image_path']
        if hashlib.sha256(image.read_bytes()).hexdigest()!=r['original_png_sha256']:
            raise ValueError('Assistant annotation/source pixel identity mismatch')
        records.append({**r,'mapYear':manifest[tile_id]['mapYear'],'split':'train','boxes':boxes,
                        'source_annotation_sha256':hashlib.sha256(additions_path.read_bytes()).hexdigest(),
                        'semantic_review':'assistant visual only; not independently human verified'})
        sources[tile_id]=image
    output.mkdir(parents=True)
    (output/'INCOMPLETE').write_text('Train import not complete\n')
    for directory in ['images/train','labels/train']:
        (output/directory).mkdir(parents=True)
    for r in records:
        tile_id=r['tileId']
        shutil.copyfile(sources[tile_id],output/'images/train'/(tile_id+'.png'))
        if r['annotation_source']=='human_reported':
            shutil.copyfile(base/'labels/train'/(tile_id+'.txt'),output/'labels/train'/(tile_id+'.txt'))
        else:
            lines=[f'0 {(b["x"]+b["w"]/2)/1024:.12f} {(b["y"]+b["h"]/2)/1024:.12f} '
                   f'{b["w"]/1024:.12f} {b["h"]/1024:.12f}' for b in r['boxes']]
            (output/'labels/train'/(tile_id+'.txt')).write_text('\n'.join(lines)+ ('\n' if lines else ''))
    summary={'state':'mixed_human_and_assistant_training_not_human_ground_truth',
             'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
             'config':config,'human_images':verified['images'],'human_boxes':verified['boxes'],
             'assistant_images':len(config['include_ids']),
             'assistant_boxes':sum(len(r['boxes']) for r in records if r['annotation_source']=='assistant_visual_review'),
             'empty_images':sum(not r['boxes'] for r in records),
             'base_audit_sha256':verified['audit_sha256'],
             'assistant_annotations_sha256':hashlib.sha256(additions_path.read_bytes()).hexdigest(),
             'validation_or_test_changed':False}
    (output/'audit.json').write_text(json.dumps({'summary':summary,'images':records},indent=2))
    (output/'INCOMPLETE').unlink()
    read_import(output,'train',manifest)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'pipeline/config/train_mix_v1.json')
    args=parser.parse_args()
    print(json.dumps(build(args.config),indent=2))


if __name__=='__main__':
    main()
