"""Compare two saved model previews on identical human Validation boxes.

Reports both a common fixed cutoff and per-model Validation-selected cutoffs.
Does not infer, mutate labels, or read final Test images.
"""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path

from pipeline.evaluate_preview import evaluate


def validation_pairs(before, after):
    """Reject changed/assistant GT, held-out Test or duplicate/mismatched IDs."""
    def index(records):
        if any(r['split'] not in {'train','val'} for r in records):
            raise ValueError('Comparison excludes Test/unknown splits')
        rows=[r for r in records if r['split']=='val']
        by_id={r['tileId']:r for r in rows}
        if not rows or len(by_id)!=len(rows):
            raise ValueError('Missing or duplicate Validation IDs')
        if any(r.get('annotation_source','human_reported')!='human_reported' for r in rows):
            raise ValueError('Comparison requires human Validation truth')
        return by_id
    a,b=index(before),index(after)
    if a.keys()!=b.keys():
        raise ValueError('Validation ID sets differ')
    for key in a:
        if a[key]['mapYear']!=b[key]['mapYear'] or a[key]['ground_truth']!=b[key]['ground_truth']:
            raise ValueError('Validation labels or years differ')
        if Path(a[key]['image_path']).resolve()!=Path(b[key]['image_path']).resolve():
            raise ValueError('Validation image sources differ')
    return [(a[key],b[key]) for key in sorted(a)]


def create(before_path, after_path, output):
    """Write paired native-image overlays and fully specified comparison metrics."""
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite: {output}')
    before=json.loads(before_path.read_text());after=json.loads(after_path.read_text())
    if before['test_used'] or after['test_used']:
        raise ValueError('Test must remain excluded')
    pairs=validation_pairs(before['images'],after['images'])
    selected=[]
    for path in [before_path,after_path]:
        selected.append(json.loads((path.parent/'threshold_selection.json').read_text())['selected']['confidence'])
    report={'scope':'Validation/tuning only, final Test untouched','common_confidence':.7,'match_iou':.5,
            'test_used':False,'models':[]}
    for payload,path,cutoff in zip([before,after],[before_path,after_path],selected):
        report['models'].append({'predictions_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'checkpoint_sha256':payload['checkpoint_sha256'],'selected_confidence':cutoff,
            'at_common_cutoff':evaluate(payload['images'],.7)['overall'],
            'at_selected_cutoff':evaluate(payload['images'],cutoff)['overall']})
    sections=[]
    for a,b in pairs:
        panels=[]
        for i,r in enumerate([a,b]):
            image=html.escape(os.path.relpath(r['image_path'],output),quote=True)
            truth=''.join(f'<rect class="truth" x="{q["x"]}" y="{q["y"]}" width="{q["w"]}" height="{q["h"]}"/>' for q in r['ground_truth'])
            predictions=''.join(f'<rect class="pred" data-model="{i}" data-score="{q["confidence"]}" '
                f'x="{q["x"]}" y="{q["y"]}" width="{q["w"]}" height="{q["h"]}"><title>{q["confidence"]:.3f}</title></rect>' for q in r['predictions'])
            panels.append(f'<div><h3>{"Baseline" if i==0 else "Новая модель"}</h3>'
                          '<svg viewBox="0 0 1024 1024">'
                          f'<image href="{image}" width="1024" height="1024"/>{truth}{predictions}</svg></div>')
        sections.append(f'<section><h2>{html.escape(a["tileId"])} · {a["mapYear"]} · разметка: {len(a["ground_truth"])}</h2>'
                        '<div class="pair">'+''.join(panels)+'</div></section>')
    def summary(model):
        r=model['at_selected_cutoff']
        p='—' if r['precision'] is None else f'{r["precision"]:.1%}'
        recall='—' if r['recall'] is None else f'{r["recall"]:.1%}'
        return f'порог {model["selected_confidence"]:.2f}: P {p}, R {recall}; найдено {r["tp"]}, лишних {r["fp"]}, пропущено {r["fn"]}'
    document='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dowser — сравнение моделей</title><style>
body{font:16px system-ui;margin:24px;background:#f5f5f3;color:#222}header{position:sticky;top:0;background:white;padding:16px;border:1px solid #ccc;z-index:1}
h1{font-size:23px}h2{font-size:17px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}svg{width:100%;display:block;background:white}
rect{fill:none;stroke-width:1.5;vector-effect:non-scaling-stroke}.truth{stroke:#00834b}.pred{stroke:#e15c00}label{display:inline-block;margin:8px 16px 0 0}
body.hide-truth .truth{display:none}button{margin:8px;padding:8px}@media(max-width:750px){.pair{grid-template-columns:1fr}}
</style><header><h1>До / после дополнительной разметки</h1>
<p>Baseline: BEFORE</p><p>Новая модель: AFTER</p>
<p>Одинаковые 15 картинок Validation и ручная разметка. Пороги подобраны для каждой модели одним способом по Validation.
Это результат настройки, не финальный Test. Зелёные рамки — твои; оранжевые — модель.</p>
<label>Baseline <input id="c0" type="range" min="0.05" max="0.95" step=".01" value="C0"><output id="v0"></output></label>
<label>Новая <input id="c1" type="range" min="0.05" max="0.95" step=".01" value="C1"><output id="v1"></output></label>
<button onclick="setCutoffs(.7,.7)">Одинаковый порог 0.70</button>
<button onclick="setCutoffs(C0,C1)">Выбранные пороги</button>
<label><input id="truth" type="checkbox" checked>Ручная разметка</label>
<p>Ползунки меняют только отображение. Числа выше соответствуют выбранным порогам.</p></header>SECTIONS
<script>function update(){for(let i=0;i<2;i++){
let c=document.getElementById('c'+i);document.getElementById('v'+i).value=Number(c.value).toFixed(2);
for(const r of document.querySelectorAll('.pred[data-model="'+i+'"]'))r.style.display=Number(r.dataset.score)>=Number(c.value)?'':'none';}
document.body.classList.toggle('hide-truth',!document.getElementById('truth').checked);}
function setCutoffs(a,b){document.getElementById('c0').value=a;document.getElementById('c1').value=b;update();}
for(const el of document.querySelectorAll('input'))el.addEventListener('input',update);update();</script></html>'''
    output.mkdir(parents=True)
    (output/'comparison.json').write_text(json.dumps(report,indent=2))
    (output/'comparison.html').write_text(document.replace('BEFORE',summary(report['models'][0]))
        .replace('AFTER',summary(report['models'][1])).replace('C0',str(selected[0]))
        .replace('C1',str(selected[1])).replace('SECTIONS',''.join(sections)))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',type=Path);parser.add_argument('after',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(create(args.before,args.after,args.output),indent=2))


if __name__=='__main__':
    main()
