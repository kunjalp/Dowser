"""Fixed-cutoff, per-tile Validation counts from saved native-box predictions.

This diagnostic uses confidence-first, one-to-one IoU matching. It is distinct
from the SDK's confidence sweep/AP and never reports Train as held-out quality.
"""

import argparse
import hashlib
import json
from pathlib import Path


def box_iou(a, b):
    """IoU of positive-size native xywh boxes; no geographic merging."""
    width=max(0,min(a['x']+a['w'],b['x']+b['w'])-max(a['x'],b['x']))
    height=max(0,min(a['y']+a['h'],b['y']+b['h'])-max(a['y'],b['y']))
    intersection=width*height
    return intersection/(a['w']*a['h']+b['w']*b['h']-intersection)


def evaluate(records, confidence=.4, iou=.5):
    """Return Val counts at one cutoff; empty-positive recall is None, not zero."""
    if not 0<confidence<=1 or not 0<iou<=1:
        raise ValueError('Cutoffs must be in (0,1]')
    if any(r['split'] not in {'train','val'} for r in records):
        raise ValueError('Only Train/Val preview inputs are permitted')
    images=[]
    for r in records:
        if r['split']!='val':
            continue
        ground_truth=r['ground_truth']
        predictions=sorted((b for b in r['predictions'] if b['confidence']>=confidence),
                           key=lambda b:b['confidence'],reverse=True)
        matched=set()
        for prediction in predictions:
            candidates=[(box_iou(prediction,truth),index) for index,truth in enumerate(ground_truth)
                        if index not in matched]
            if candidates:
                overlap,index=max(candidates)
                if overlap>=iou:
                    matched.add(index)
        images.append({'tileId':r['tileId'],'mapYear':r['mapYear'],
                       'ground_truth_boxes':len(ground_truth),'predicted_boxes':len(predictions),
                       'tp':len(matched),'fp':len(predictions)-len(matched),
                       'fn':len(ground_truth)-len(matched)})
    if not images:
        raise ValueError('No Validation records')

    def aggregate(rows):
        tp,fp,fn=(sum(r[key] for r in rows) for key in ['tp','fp','fn'])
        return {'images':len(rows),'tp':tp,'fp':fp,'fn':fn,
                'precision':tp/(tp+fp) if tp+fp else None,
                'recall':tp/(tp+fn) if tp+fn else None}

    return {'confidence':confidence,'iou':iou,'scope':'Validation, not final Test',
            'matching':'descending confidence; highest-IoU unmatched GT per prediction; per tile',
            'test_used':False,'overall':aggregate(images),
            'by_year':{str(year):aggregate([r for r in images if r['mapYear']==year])
                       for year in sorted({r['mapYear'] for r in images})},'images':images}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('predictions',type=Path)
    parser.add_argument('--confidence',type=float,default=.4)
    parser.add_argument('--iou',type=float,default=.5)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--sweep',action='store_true',help='Select cutoff on Val F1 over 0.05..0.95, step 0.01')
    args=parser.parse_args()
    payload=json.loads(args.predictions.read_text())
    if payload['test_used'] or args.confidence<payload['minimum_saved_confidence']:
        raise ValueError('Test is excluded; cutoff cannot precede saved prediction threshold')
    if args.sweep:
        if payload['minimum_saved_confidence']>.05:
            raise ValueError('Sweep requires saved predictions down to 0.05')
        grid=[]
        for i in range(5,96):
            cutoff=i/100
            metrics=evaluate(payload['images'],cutoff,args.iou)['overall']
            precision,recall=metrics['precision'] or 0,metrics['recall'] or 0
            grid.append({'confidence':cutoff,**metrics,
                         'f1':2*precision*recall/(precision+recall) if precision+recall else 0})
        report={'scope':'Validation tuning only; final Test untouched','iou':args.iou,
                'method':'maximize per-tile F1 on 0.05..0.95 inclusive, step 0.01; tie -> higher cutoff',
                'selected':max(grid,key=lambda r:(r['f1'],r['confidence'])),'grid':grid}
    else:
        report=evaluate(payload['images'],args.confidence,args.iou)
    report['predictions_sha256']=hashlib.sha256(args.predictions.read_bytes()).hexdigest()
    report['checkpoint_sha256']=payload['checkpoint_sha256']
    name='threshold_selection.json' if args.sweep else f'evaluation_conf{round(args.confidence*100):03d}_iou{round(args.iou*100):03d}.json'
    output=args.output or args.predictions.parent/name
    with output.open('x') as f:
        f.write(json.dumps(report,indent=2))
    print(json.dumps({key:report[key] for key in (['selected'] if args.sweep else ['overall','by_year'])},indent=2))


if __name__=='__main__':
    main()
