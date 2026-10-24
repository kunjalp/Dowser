"""Propose a small human-review batch from unreviewed Train only.

Model predictions rank review candidates; they never establish false positives,
ground truth, or empty backgrounds. Source images remain native 1024 px PNGs.
"""

import argparse
import hashlib
import html
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

from pipeline.preview_detector import native_box
from pipeline.train_detector import ROOT, local_sdk


def eligible_tiles(manifest, reviewed_ids):
    """Select full-content unreviewed frozen Train; reject all held-outs/buffers."""
    return [r for r in manifest if r['split']=='train' and r['tileId'] not in reviewed_ids
            and r['valid_fraction']>=.95]


def choose_candidates(records, per_map=2, cutoff=.7):
    """Prefer moderate prediction counts and disjoint coverage across sources.

    Ranking is an annotation-workload heuristic, not a text detector or label.
    Predicted density can undercount real objects; reviewers inspect whole tiles.
    """
    if any(r['split']!='train' for r in records):
        raise ValueError('Review selection accepts Train only')
    def priority(r):
        boxes=[b for b in r['predictions'] if b['confidence']>=cutoff]
        count=len(boxes)
        return (0<count<=35,max((b['confidence'] for b in boxes),default=0),-count,r['tileId'])
    chosen=[]
    manageable=[r for r in records if 0<sum(b['confidence']>=cutoff for b in r['predictions'])<=35]
    groups={source:sorted([r for r in manageable if r['source_map_id']==source],key=priority,reverse=True)
            for source in sorted({r['source_map_id'] for r in records})}
    def overlaps(a,b):
        x,y,r,s=a['split_bounds_m'];u,v,w,z=b['split_bounds_m']
        return min(r,w)>max(x,u) and min(s,z)>max(y,v)
    for _ in range(per_map):
        for group in groups.values():
            for candidate in group:
                if not any(overlaps(candidate,previous) for previous in chosen):
                    chosen.append(candidate)
                    group.remove(candidate)
                    break
    return chosen


def write_package(output, records):
    """Write images-only ZIP and clearly unreviewed browser proposals; no labels."""
    panels=[]
    (output/'images').mkdir()
    with zipfile.ZipFile(output/'review_train_images.zip','w',zipfile.ZIP_STORED) as archive:
        for r in records:
            name=r['tileId']+'.png'
            shutil.copyfile(r['image_path'],output/'images'/name)
            archive.write(output/'images'/name,name)
            rects=''.join(f'<rect data-score="{b["confidence"]}" x="{b["x"]}" y="{b["y"]}" '
                          f'width="{b["w"]}" height="{b["h"]}"><title>{b["confidence"]:.3f}</title></rect>'
                          for b in r['predictions'])
            panels.append(f'<h2>{html.escape(r["tileId"])} · {r["mapYear"]}</h2>'
                          '<p>Наличие скважин не проверено. Оранжевые рамки — предположения модели.</p>'
                          f'<svg viewBox="0 0 1024 1024"><image href="images/{name}" '
                          f'width="1024" height="1024"/>{rects}</svg>')
    (output/'preview.html').write_text('''<!doctype html><html lang="ru"><meta charset="utf-8">
<title>Dowser — новая партия Train для проверки</title><style>
body{font:16px system-ui;margin:24px}header{position:sticky;top:0;background:#fff;padding:16px;z-index:1}
svg{display:block;max-width:1024px;width:100%}rect{fill:none;stroke:#e15c00;stroke-width:1.5}
body.hide rect{display:none}</style><header><h1>Новые картинки Train</h1>
<p>Проверь каждую целиком. Отметь только настоящие скважины классом well_symbol.
Mark Null — только если убедился, что скважин нет. Буквы и цифры не размечай.</p>
<p>Это предложения для проверки, а не готовые отрицательные примеры. Обучение на них ещё не запускалось.</p>
<label><input type="checkbox" checked onchange="document.body.classList.toggle('hide',!this.checked)">Показать предположения модели</label>
<label>Порог <input id="cutoff" type="range" min="0.4" max="0.95" step=".01" value=".7"><output id="value"></output></label>
</header>'''+''.join(panels)+'''<script>
const c=document.getElementById('cutoff');function update(){document.getElementById('value').value=Number(c.value).toFixed(2);
for(const r of document.querySelectorAll('rect'))r.style.display=Number(r.dataset.score)>=Number(c.value)?'':'none';}
c.addEventListener('input',update);update();</script></html>''')


def mine(config_path, predictions_path=None):
    """Infer on eligible Train and prepare an isolated, unreviewed labeling queue."""
    config=json.loads(config_path.read_text())
    output=ROOT/config['output']
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite: {output}')
    manifest_path=ROOT/config['manifest']
    manifest=list(map(json.loads,manifest_path.read_text().splitlines()))
    audit=json.loads((ROOT/config['reviewed_train']/'audit.json').read_text())
    candidates=eligible_tiles(manifest,{r['tileId'] for r in audit['images']})
    if not candidates:
        raise ValueError('No unreviewed full-content Train tiles')
    weights=ROOT/config['weights']
    if hashlib.sha256(weights.read_bytes()).hexdigest()!=config['weights_sha256']:
        raise ValueError('Wrong baseline checkpoint')
    output.mkdir(parents=True)
    (output/'INCOMPLETE').write_text('Mining not complete\n')
    for r in candidates:
        r['image_path']=str(ROOT/config['dataset']/r['image_path'])
    if predictions_path:
        cached=json.loads(predictions_path.read_text())
        if (cached['manifest_sha256']!=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
                or cached['config']['weights_sha256']!=config['weights_sha256']):
            raise ValueError('Cached predictions use different data or weights')
        by_id={r['tileId']:r for r in cached['images']}
        if set(by_id)!={r['tileId'] for r in candidates}:
            raise ValueError('Cached predictions must contain exactly eligible Train IDs')
        for r in candidates:
            previous=by_id[r['tileId']]
            if hashlib.sha256(Path(r['image_path']).read_bytes()).hexdigest()!=previous['image_sha256']:
                raise ValueError('Changed cached source image')
            r['predictions']=previous['predictions']
    else:
        model=local_sdk()(str(weights))
        results=model.predict(source=[r['image_path'] for r in candidates],imgsz=1024,
                              conf=.4,iou=.7,max_det=1000,device='mps',batch=2,stream=True,
                              verbose=False,save=False)
        for r,result in zip(candidates,results,strict=True):
            if Path(r['image_path']).resolve()!=Path(result.path).resolve():
                raise ValueError('Source/prediction order mismatch')
            r['predictions']=[native_box(b,s,c,result.orig_shape) for b,s,c in zip(
                result.boxes.xyxy.cpu().tolist(),result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist())]
    for r in candidates:
        r['review_status']='unreviewed; not ground truth or confirmed negative'
        r['image_sha256']=hashlib.sha256(Path(r['image_path']).read_bytes()).hexdigest()
    selected=choose_candidates(candidates,config['per_map'])
    if not selected:
        raise ValueError('No manageable review candidates; do not invent negative labels')
    write_package(output,selected)
    payload={'config':config,'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
             'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
             'code_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
             'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'cached_predictions':str(predictions_path) if predictions_path else None,
             'inferred_train_images':len(candidates),'selected_images':len(selected),
             'val_used':False,'test_used':False,'human_labels_added':0,
             'selected_ids':[r['tileId'] for r in selected],'images':candidates}
    (output/'proposals.json').write_text(json.dumps(payload,indent=2))
    (output/'INCOMPLETE').unlink()
    return {k:payload[k] for k in ['inferred_train_images','selected_images','selected_ids','human_labels_added']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'pipeline/config/hard_negative_review.json')
    parser.add_argument('--predictions',type=Path,help='Reuse a checked mining report without GPU inference')
    args=parser.parse_args()
    print(json.dumps(mine(args.config,args.predictions),indent=2))


if __name__=='__main__':
    main()
