"""Check real YOLO detection-loss/backward on Train without optimizer updates.

This compatibility probe is not an epoch run, trained detector, or accuracy test.
Validation/Test labels or images are not read.
"""

import argparse
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

from pipeline.train_detector import ROOT, local_sdk


def probe(output):
    """Use pinned pretrained features and one training image to check GPU gradients."""
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite: {output}")
    config = json.loads((ROOT/"pipeline/config/train_smoke.json").read_text())
    weights = ROOT/config["weights"]
    if hashlib.sha256(weights.read_bytes()).hexdigest() != config["weights_sha256"]:
        raise ValueError("Wrong pretrained weights")
    YOLO = local_sdk()
    import numpy as np
    import torch
    from PIL import Image
    from ultralytics.nn.tasks import DetectionModel
    from ultralytics.utils import DEFAULT_CFG
    if not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable")
    pretrained = YOLO(str(weights)).model
    model = DetectionModel(pretrained.yaml,nc=1,ch=3,verbose=False)
    model.load(pretrained)
    model.args = DEFAULT_CFG
    model.to("mps").train()
    image_path = sorted((ROOT/config["train_import"]/"images/train").glob("*.png"))[0]
    labels_path = ROOT/config["train_import"]/"labels/train"/(image_path.stem+".txt")
    rows = np.loadtxt(labels_path,dtype=np.float32,ndmin=2)
    array = np.asarray(Image.open(image_path).convert("RGB"),dtype=np.float32)/255
    batch = {"img":torch.from_numpy(array.transpose(2,0,1).copy()).unsqueeze(0).to("mps"),
             "batch_idx":torch.zeros(len(rows),device="mps"),
             "cls":torch.from_numpy(rows[:,:1].copy()).to("mps"),
             "bboxes":torch.from_numpy(rows[:,1:].copy()).to("mps")}
    start = time.perf_counter()
    loss,components = model.loss(batch)
    total = loss.sum()
    if not bool(torch.isfinite(total).item()):
        raise RuntimeError("Nonfinite detection loss")
    total.backward()
    norm = torch.stack([p.grad.detach().square().sum() for p in model.parameters() if p.grad is not None]).sum()
    torch.mps.synchronize()
    if not bool(torch.isfinite(norm).item()):
        raise RuntimeError("Nonfinite gradients")
    result = {"state":"model_loss_backward_passed_no_optimizer_updates","image_id":image_path.stem,
              "training_boxes_in_probe":len(rows),"input_size":list(batch["img"].shape),"classes":1,
              "device":"mps","seconds":round(time.perf_counter()-start,3),"loss":float(total.detach().cpu()),
              "components":{k:float(v.detach().cpu()) for k,v in components.items()},
              "finite_gradients":True,"optimizer_steps":0,"epochs":0,"trained_weights_saved":False,
              "weights_sha256":config["weights_sha256"],
              "versions":{p:importlib.metadata.version(p) for p in ["torch","torchvision","ultralytics","numpy"]}}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"data/ml/yolo11n_backend_probe.json")
    args = parser.parse_args()
    print(json.dumps(probe(args.output),indent=2))


if __name__ == "__main__":
    main()
