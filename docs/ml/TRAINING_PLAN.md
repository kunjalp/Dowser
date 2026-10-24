# First detector training plan

Decision date: 2026-10-24, America/Los_Angeles. This is a selected baseline and
execution plan, not a completed detector run. See [status](STATUS.md) for progress.

## Location and environment

First run: locally on Emir's Apple M5 Mac, 24 GiB unified memory, using PyTorch
MPS (Apple GPU). A small convolution forward/backward and NumPy transfer passed
on `mps:0`; MPS is available. This is a backend check, not a YOLO benchmark.

Use ignored `pipeline/.venv/` with Python 3.12.14. Currently installed/probed:
PyTorch 2.14.1 and NumPy 2.0.2. Preserve the existing root `.venv/` (Python 3.9.6)
for map preparation/auditing. The training SDK, full dependency lock, weights,
and runner still need setup; PyPI listed Ultralytics 8.4.185 during this check.
Do not call the full training environment ready based only on the backend probe.

Probe output: ignored `data/ml/training_environment_probe.json`. No cloud
instance, hosted training session, or paid compute was started by this check.

## Selected model and planned settings

Start with pretrained **YOLO11n** (`yolo11n.pt`), ordinary object detection,
one class `well_symbol`. Its small size is useful for a quick first run on this
machine. It has not been shown to outperform other models on our well symbols.
The earlier YOLOv8 export selected the label format, not a training architecture.

| Setting | Planned first value | Reason |
| --- | --- | --- |
| Transfer learning | Pretrained yolo11n.pt | Learn from existing features rather than train from scratch |
| imgsz | 1024 | Master Plan; preserve tiny scanned symbols |
| device | mps | Available local Apple GPU |
| batch | 2 | Conservative initial memory use; check on full model |
| workers | 0 | Simple first macOS process setup |
| amp | false | Start with float32 and fewer mixed-precision variables |
| seed | 42 | Record repeatable inputs; no cross-device bit-identity claim |
| First diagnostic run | 5 epochs | Verify loading, loss, checkpoints, and prediction rendering |
| First baseline | Up to 50 epochs, patience 10 | Select checkpoint on independent validation, record actual stopping |
| Initial augmentation | Off for diagnostic run | Establish data/box correctness before extra transformations |
| max_det | 1000 for prediction/evaluation | Avoid a low detection cap on dense symbol maps |

The actual config will be committed with the runner and exact installed versions
before training. Weights stay outside Git, with source and SHA-256 recorded.
Measure memory and per-epoch time in the first run before estimating wall time.
MPS backend success alone does not guarantee every YOLO operation will work.

## Data and readiness

Training input: `data/ml/reviewed_v2/`, 5 user-annotated images and 568 boxes:
297 from 1954, 271 from 1992. Use original PNG pixels and audited label files.
V2 resolves the requested loose-boundary examples; full completeness is not
independently established. No further redraw of these same examples is requested.

**Missing prerequisite for the normal training/validation run:** reviewed labels
for the 13 frozen Validation images. The 30 frozen Test images must remain
excluded from fitting and tuning; label them independently for final evaluation.
Current exports contain training labels only. The exported YAML is not runnable
as-is because its validation/test paths do not exist in that export.

Do not randomly split the five overlapping training images, reuse them as
independent validation, or turn unreviewed images into empty negative labels.
Include verified negatives in the expanding training dataset. Team labeling
help is already part of the Master Plan; no labeling assignment was sent here.

## Execution sequence

1. Inspect and integrate pending upstream main changes before adding the runner.
2. Install/pin the training SDK in the separate environment, fetch pinned-source
   pretrained weights, and check full-model compatibility on the local GPU.
3. Import/audit independent Validation annotations, preserving the frozen
   geography. Keep Test protected. The existing five-image Train set stays Train.
4. Commit the exact run config and execute the 5-epoch diagnostic run. Inspect
   loss/checkpoints and render predictions. Debug previews on seen Train images
   are marked as seen data and do not establish quality on unseen territory.
5. Run the baseline, up to 50 epochs. Use Validation for checkpoint/threshold
   selection. Record actual metrics, per-era counts, errors, code/environment,
   weight hashes, duration and device in [experiments](EXPERIMENTS.md).
6. Freeze the selected model/threshold, then evaluate on the independently labeled
   30-image Test set. Report held-out precision/recall and representative mistakes.
7. Convert reviewed model detections to WGS84, preserve tile/year/crop provenance,
   check known-well offsets, and hand the agreed detection export to Ryann.

The first visible model artifact will be a prediction preview with boxes and
scores from our fine-tuned model. The existing proposal preview reuses published
predictions and must remain distinguishable from this future result.

## Primary references

- [Ultralytics YOLO11 models and pretrained detection weights](https://docs.ultralytics.com/models/yolo11/).
- [Ultralytics training and Apple MPS configuration](https://docs.ultralytics.com/modes/train/).
- [PyTorch 2.14 MPS backend](https://docs.pytorch.org/docs/2.14/notes/mps.html).
- [Current Master Plan](../master-plan/source.txt), ingestion/detector acceptance.
