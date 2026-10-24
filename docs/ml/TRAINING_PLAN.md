# First detector training plan

Decision date: 2026-10-24, America/Los_Angeles. Current outcomes/next action are
in [STATUS.md](STATUS.md). The initial five-epoch diagnostic is recorded in
[EXPERIMENTS.md](EXPERIMENTS.md); use that record for its actual old config.

## Environment and model

Train locally on the Apple M5, 24 GiB unified memory, using PyTorch MPS.
Use separate ignored `pipeline/.venv/`, Python 3.12.14. Installed dependencies:
[direct requirements](../../pipeline/requirements-train.txt),
[full macOS lock](../../pipeline/requirements-train.lock.txt).
Preserve root `.venv/` for map preparation/auditing. Do not install preparation's
NumPy 2.0.2 pin into training: the current SDK/macOS dependencies exclude 2.0.x;
the resolved training version is 2.5.4.

On another compatible Mac with Python 3.12.14 and uv, if the environment is absent:

```sh
uv venv --python 3.12.14 pipeline/.venv
uv pip install --python pipeline/.venv/bin/python -r pipeline/requirements-train.lock.txt
```

Do not recreate an existing environment or apply the ARM64/MPS config unchanged
to CUDA/Linux. Record a different environment/config as a separate run.
Task-local SDK settings disable external logger sync. This is an implementation
choice; the user withdrew the earlier project-wide zero-cost restriction.

Start with pretrained **YOLO11n**, one class `well_symbol`. YOLOv8 ZIP export
selects a label format, not an architecture. The small model is a practical
candidate, not proven superior for these symbols. Weights stay outside Git at
`data/ml/weights/yolo11n.pt`; source URL and checksum are pinned in the config.
On another machine fetch that exact URL and verify the checksum before use.

The full native-1024 model loss/backward probe passed on one real Train image,
without optimizer updates or trained weights. This verifies those operations,
not the complete batch-2 training/validation/checkpoint/rendering path.
See [experiment records](EXPERIMENTS.md) for raw probe results and versions.

## Data and settings

Active frozen manifest: `data/ml/kern_1024_v2/manifest.jsonl`: 72 Train, 15 Val,
30 Test, 72 buffer. Original v1 is preserved. Two full-content Val tiles were
added to the padded edge strips before fitting, preserving human Train/Test
and excluding overlapping neighbors from Train.

Fit only `data/ml/reviewed_v2/`: 5 user-reviewed images, 568 boxes, both eras,
native PNGs. All other unreviewed Train images are excluded.
Reviewed Validation must be imported to `data/ml/reviewed_validation_v1/`
and audited against the active manifest. The supplied export is now imported:
15 Val images, 49 symbols, 11 verified-empty images. All positives are from
Oildale 1954; 1992 recall is unavailable from this Val set.
Never fabricate negatives, re-split the five Train images or tune against Test.
Final Test labels are needed for evaluation, not the first training diagnostic.

[Diagnostic config](../../pipeline/config/train_smoke.json): 5 epochs,
imgsz 1024, batch 2, nbs 2, mps, workers 0, amp false, seed 42, AdamW/lr0 0.001,
warmup 0, augmentation off, max_det 1000, plots/checkpoints enabled.
Measure actual memory and epoch timing in that run.

If all reviewed Val images are negative, the diagnostic explicitly permits it
but records quality metrics as unavailable. Raw framework zeros are not measured
recall/mAP. The full baseline requires independent positives before quality-based
checkpoint selection. Any further split change needs an explicit version and
contamination review; do not silently change it after examining model results.

## Commands and sequence

The commands below describe the recorded runs; their output names now exist and
must not be overwritten. For reproduction choose fresh run/output names.
Current trained checkpoint/preview and interpretation are in [STATUS.md](STATUS.md).

After independent review/export of all 15 Validation images (see
[annotation handoff](ANNOTATION.md#active-validation-handoff)):

```sh
# Replace the placeholder with the actual preserved export filename.
.venv/bin/python -m pipeline.audit_annotations \
  data/ml/reviewed_exports/VALIDATION_EXPORT.yolov8.zip \
  --dataset data/ml/kern_1024_v2 --split val \
  --output data/ml/reviewed_validation_v1
pipeline/.venv/bin/python -m pipeline.train_detector --check-only
# Only after preflight passes; refuses existing run/output names:
pipeline/.venv/bin/python -m pipeline.train_detector --name kern_yolo11n_smoke_v1
```

The audit requires explicit empty TXT files for reviewed negatives, reconciles
IDs/partitions and restores native PNGs. It never moves labels between folds.
Default preflight refuses fitting while Validation is missing.

The runner records audit/manifest hashes, config/versions, commit/dirty state,
status and metrics under `data/ml/runs/<name>/run.json`. SDK checkpoints/curves
live in its `training/` subdirectory. Preserve failed/interrupted runs and use
fresh names for retries. Commit final code/config before fitting; record actual
parameters, timing and checkpoint checksums in the experiment log.

Inspect the diagnostic's data loading, losses, memory/device, saved weights and
predictions. The first visible model result will be a prediction preview from
our fine-tuned detector. Seen-Train previews are marked as such and do not
establish unseen quality. Existing published-proposal HTML is distinct.

The [baseline config](../../pipeline/config/train_baseline.json) uses up to
50 epochs, patience 10, warmup 3, `allow_negative_only_validation=false`, and
nbs=2 for batch=2. This avoids the SDK's nbs=64 default accumulating essentially
the whole tiny diagnostic before an update. Actual update counts are recorded;
the first diagnostic is preserved rather than rewritten to match new settings.
Run the baseline with a fresh name:

```sh
pipeline/.venv/bin/python -m pipeline.train_detector \
  --config pipeline/config/train_baseline.json --check-only
pipeline/.venv/bin/python -m pipeline.train_detector \
  --config pipeline/config/train_baseline.json --name kern_yolo11n_baseline_v1
```

Start from pinned pretrained weights, select checkpoint/threshold on Val, record
actual stopping and per-era errors. Freeze choices, evaluate on independently
labeled 30-image Test, then export WGS84 detections/crops and check well offsets.

## Inspect predictions and fixed-cutoff metrics

Actual baseline stopped at 29 epochs/87 updates; the first Val-tuned inference
candidate is pinned in `pipeline/config/inference_baseline.json` at confidence
.70. Fixed-cutoff precision .5741 / recall .6327 is distinct from the SDK's
confidence-sweep metrics. Final Test remains unlabeled/unmeasured.

```sh
# These artifact paths already exist; use new --output destinations for replay.
pipeline/.venv/bin/python -m pipeline.preview_detector \
  data/ml/runs/kern_yolo11n_baseline_v1
pipeline/.venv/bin/python -m pipeline.evaluate_preview \
  data/ml/runs/kern_yolo11n_baseline_v1/preview/predictions.json
pipeline/.venv/bin/python -m pipeline.evaluate_preview \
  data/ml/runs/kern_yolo11n_baseline_v1/preview/predictions.json --sweep
```

Open `preview/preview_selected.html` under the baseline run. Green is human GT,
orange is model output, Train is explicitly marked as seen during fitting.
Moving its slider is a visual diagnostic, not a recomputed metric report.
Quality helpers exclude Train and reject Test inputs; Val-only threshold tuning
does not replace the Master Plan's final held-out acceptance or real geo checks.

## Authorized mixed-supervision experiments and comparison

Emir explicitly asked the assistant to finish annotations/training autonomously.
Current results are in STATUS.md; assistant supervision remains distinct from
human labels. `build_train_mix` preserves the 568 original human boxes, checks
native source hashes/Train IDs and requires explicit assistant visual-review
records. Train configs opt in; preflight still requires >=300 human boxes and
rejects assistant labels in Val. The frozen 15-image human Val is unchanged.

Actual additional runs (outputs already exist; choose fresh names for replay):

```sh
.venv/bin/python -m pipeline.build_train_mix --config pipeline/config/train_mix_v1.json
pipeline/.venv/bin/python -m pipeline.train_detector \
  --config pipeline/config/train_data_v2.json --name kern_yolo11n_data_v2
.venv/bin/python -m pipeline.build_train_mix --config pipeline/config/train_mix_v2.json
pipeline/.venv/bin/python -m pipeline.train_detector \
  --config pipeline/config/train_data_v3.json --name kern_yolo11n_data_v3
```

Data_v2 is selected by human-Val F1: 8 Train images, 568 human +49 assistant
boxes, one assistant-reviewed empty image, 24 epochs/96 optimizer updates.
Data_v3 adds two more reviewed backgrounds and is preserved as a comparison.
Architecture, pretrained start and settings stay the same, but larger data gives
different optimizer-update counts; do not claim an equal-compute causal study.

For each run, generate native predictions and select its threshold using the
same evaluate_preview --sweep procedure. Selected data_v2 cutoff is .24 rather
than baseline .70; classifier score scale changed after training. At common .70,
data_v2 emits no Val boxes. Thus report both common and separately selected
operating points, never present the Val-selected improvement as fixed-.70 quality.
All model/threshold selection remains tuning, not final held-out Test.

```sh
pipeline/.venv/bin/python -m pipeline.compare_previews \
  data/ml/runs/kern_yolo11n_baseline_v1/preview/predictions.json \
  data/ml/runs/kern_yolo11n_data_v2/preview/predictions.json \
  --output data/ml/runs/kern_yolo11n_data_v2/comparison_to_baseline
```

The comparison refuses changed human-Val IDs/years/boxes/image paths, duplicates
and Test inputs. Default paired overlays show selected cutoffs; button offers
common .70. Preview metadata/legend distinguishes human (green), assistant
(purple, Train only) and model (orange). Current inference settings are pinned in
`pipeline/config/inference_selected.json`; geospatial/Test acceptance is pending.

## Primary references

- [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/).
- [Training and Apple MPS](https://docs.ultralytics.com/modes/train/).
- [PyTorch MPS](https://docs.pytorch.org/docs/2.14/notes/mps.html).
- [Master Plan](../master-plan/source.txt), ingestion/detector acceptance.
