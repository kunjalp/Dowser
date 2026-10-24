"""Render local Train/Validation predictions over unchanged native PNG images.

This visual diagnostic never reads Test images or writes backend detections.
Changing the display cutoff does not recompute evaluation metrics.
"""

import argparse
import hashlib
import html
import json
import math
import os
import time
from pathlib import Path

from pipeline.train_detector import ROOT, check_inputs, local_sdk


def native_box(xyxy, confidence, class_id, shape):
    """Convert SDK original-image xyxy to native xywh, rejecting invalid output."""
    if tuple(shape) != (1024,1024) or class_id != 0:
        raise ValueError("Expected original 1024 px well_symbol predictions")
    if not all(math.isfinite(v) for v in [*xyxy,confidence]):
        raise ValueError("Nonfinite prediction")
    x,y,right,bottom = xyxy
    if not (0<=x<right<=1024 and 0<=y<bottom<=1024 and 0<=confidence<=1):
        raise ValueError("Prediction outside original pixels or invalid score")
    return {"x":x,"y":y,"w":right-x,"h":bottom-y,"confidence":confidence,
            "className":"well_symbol","source":"model"}


def render(output, records, minimum, initial, filename="preview.html"):
    """Write a standalone report referencing native PNGs without changing pixels."""
    panels=[]
    for r in records:
        source=html.escape(os.path.relpath(r["image_path"],output),quote=True)
        def rect(b, kind):
            score=b.get("confidence")
            attr='' if score is None else f' data-score="{score}"'
            assistant=r.get("annotation_source")=="assistant_visual_review"
            if score is None and assistant:
                kind+=" assistant"
            label=("Assistant visual label; not human verified" if assistant else "Human label") if score is None else f'Model score {score:.3f}'
            return (f'<rect class="{kind}"{attr} x="{b["x"]}" y="{b["y"]}" '
                    f'width="{b["w"]}" height="{b["h"]}"><title>{label}</title></rect>')
        panels.append(f'<section data-split="{r["split"]}"><h2>{html.escape(r["tileId"])} '
                      f'· {r["mapYear"]} · {r["split"]}</h2>'
                      f'<p>Рамок разметки: {len(r["ground_truth"])}. '
                      '<span class="count"></span></p>'
                      '<svg viewBox="0 0 1024 1024">'
                      f'<image href="{source}" width="1024" height="1024"/>'+
                      ''.join(rect(b,"truth") for b in r["ground_truth"])+
                      ''.join(rect(b,"prediction") for b in r["predictions"])+
                      '</svg></section>')
    document='''<!doctype html><html lang="ru"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dowser — предсказания модели</title><style>
body{font:16px system-ui;margin:24px;background:#f5f5f3;color:#222}
header{position:sticky;top:0;background:#fff;padding:16px;z-index:1;border:1px solid #ccc}
h1{font-size:22px;margin:0 0 8px}h2{font-size:17px}section{margin:24px 0}
svg{display:block;width:100%;max-width:1024px;background:white}
rect{fill:none;stroke-width:1.5;vector-effect:non-scaling-stroke}
.truth{stroke:#00834b}.truth.assistant{stroke:#8844cc}.prediction{stroke:#e15c00}label{display:inline-block;margin:8px 16px 0 0}
body.hide-truth .truth,body.hide-prediction .prediction{display:none}
</style><header><h1>Dowser — результат обучения</h1>
<p>Зелёные рамки — твоя разметка. Фиолетовые — разметка, проверенная ИИ.
Оранжевые — предсказания модели.</p>
<p>Validation не использовался для обучения весов. Train — уже виденные картинки.
Эта страница помогает разбирать ошибки; положение ползунка не пересчитывает метрики.</p>
<label>Набор <select id="split"><option value="val">Validation</option>
<option value="train">Train</option><option value="all">Все</option></select></label>
<label>Порог <input id="cutoff" type="range" step="0.01" min="MINIMUM" max="0.95"
value="INITIAL"><output id="value"></output></label>
<label><input type="checkbox" id="truth" checked>Ручная разметка</label>
<label><input type="checkbox" id="prediction" checked>Модель</label>
</header>PANELS<script>
const split=document.getElementById('split'),cutoff=document.getElementById('cutoff');
function update(){
 document.getElementById('value').value=Number(cutoff.value).toFixed(2);
 for(const s of document.querySelectorAll('section')){
  s.hidden=split.value!=='all'&&s.dataset.split!==split.value;
  let n=0;for(const r of s.querySelectorAll('.prediction')){
   const visible=Number(r.dataset.score)>=Number(cutoff.value);
   r.style.display=visible?'':'none';if(visible)n++;
  }s.querySelector('.count').textContent='Предсказаний при этом пороге: '+n;
 }
 for(const key of ['truth','prediction'])
  document.body.classList.toggle('hide-'+key,!document.getElementById(key).checked);
}
for(const el of document.querySelectorAll('input,select'))el.addEventListener('input',update);
update();</script></html>'''
    (output/filename).write_text(document.replace("MINIMUM",str(minimum))
                                      .replace("INITIAL",str(initial)).replace("PANELS","".join(panels)))


def preview(run_dir, output, minimum=.05, initial=.4):
    """Predict audited Train/Val at native size using a completed run's best.pt."""
    if not 0<minimum<=initial<=.95:
        raise ValueError("Expected 0 < minimum <= initial <= 0.95")
    run_record=json.loads((run_dir/"run.json").read_text())
    if run_record["state"] != "completed":
        raise ValueError("Preview requires a completed training run")
    config=run_record["config"]
    check_inputs(config)
    weights=Path(run_record["save_dir"])/"weights/best.pt"
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    output.mkdir(parents=True)
    (output/"INCOMPLETE").write_text("Prediction report is not complete.\n")
    records=[]
    for split,key in [("val","validation_import"),("train","train_import")]:
        folder=ROOT/config[key]
        for r in json.loads((folder/"audit.json").read_text())["images"]:
            records.append({"tileId":r["tileId"],"mapYear":r["mapYear"],"split":split,
                            "annotation_source":r.get("annotation_source","human_reported"),
                            "ground_truth":r["boxes"],"image_path":str(folder/"images"/split/(r["tileId"]+".png"))})
    model=local_sdk()(str(weights))
    started=time.perf_counter()
    results=model.predict(source=[r["image_path"] for r in records],imgsz=1024,
                          device=config["training"]["device"],conf=minimum,iou=.7,
                          max_det=1000,batch=2,stream=True,verbose=False,save=False)
    count=0
    for r,result in zip(records,results,strict=True):
        if Path(result.path).resolve()!=Path(r["image_path"]).resolve():
            raise ValueError("Prediction order differs from source images")
        r["predictions"]=[native_box(b,float(s),float(c),result.orig_shape)
                          for b,s,c in zip(result.boxes.xyxy.cpu().tolist(),
                                           result.boxes.conf.cpu().tolist(),result.boxes.cls.cpu().tolist())]
        count+=1
    if count!=len(records):
        raise ValueError("Missing prediction results")
    payload={"schema_version":1,"checkpoint_sha256":hashlib.sha256(weights.read_bytes()).hexdigest(),
             "run_record_sha256":hashlib.sha256((run_dir/"run.json").read_bytes()).hexdigest(),
             "minimum_saved_confidence":minimum,"initial_display_confidence":initial,
             "nms_iou":.7,"imgsz":1024,"max_det":1000,"test_used":False,
             "seconds":round(time.perf_counter()-started,3),"images":records}
    (output/"predictions.json").write_text(json.dumps(payload,indent=2))
    render(output,records,minimum,initial)
    (output/"INCOMPLETE").unlink()
    return {"preview":str(output/"preview.html"),"images":count,
            "predictions_at_initial_cutoff":sum(b["confidence"]>=initial for r in records for b in r["predictions"])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    print(json.dumps(preview(args.run,args.output or args.run/"preview"),indent=2))


if __name__=="__main__":
    main()
