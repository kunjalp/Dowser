# ML experiments

The first model diagnostic is recorded below. Do not fill results from
expectations. Add one record per meaningful run; link larger reports
and artifacts instead of committing generated directories.

## Preparation: kern_1024_v1 — 2026-10-23

Purpose: Master Plan map preparation, native-resolution tiling, and protected
geographic holdouts. This is a data preparation run, not a model experiment.

- Command: `.venv/bin/python -m pipeline.prepare_dataset` from repository root,
  after `.venv/bin/python -m pipeline.download_sources`.
- Code base: `ddd1423883c0bda15da6f5d98c946190a7ba04fc`, with the implementation
  changes in this PR uncommitted at run time. Exact executable/config hashes
  are recorded in ignored `data/ml/kern_1024_v1/summary.json`.
- Configs: `pipeline/config/region.json` and `pipeline/config/dataset.json`.
- Sources: USGS 293661 (1954, revision 1968, imprint 1970), 293664 (1954,
  imprint 1956), 102321 (1992, edit/imprint 1995). Three raster editions cover
  two distinct geographic quadrangles. Source hashes are in the region config.
- Geometry: 1024 px, stride 819 px; native CRS/affine preserved, collars masked.
  Shared geographic bands across editions; boundary-crossing tiles quarantined.
- Output: ignored `data/ml/kern_1024_v1/`, with 189 manifest entries: 84 train,
  13 validation, 30 test, 62 buffer. No buffer images exported.
- Full manifest SHA-256:
  `fdc01146873c0d5e5e0c6c4c95e7eae51998f872fd1746dc8c6919151f4d19af`.
  The full manifest includes local source paths; another clone can preserve the
  same split IDs without having a byte-identical full manifest.
- Era counts (1954 / 1992): train 56 / 28, validation 10 / 3, test 19 / 11.
- Labels: zero human-reviewed tiles and zero boxes. No negative label files.
- Software: Python 3.9.6, rasterio 1.4.3, Pillow 11.3.0, pyproj 3.6.1,
  numpy 2.0.2, affine 3.0.1; macOS 26.6.2 ARM64, local CPU preparation.
- Verification: 127 RGB PNGs at 1024×1024; ZIP integrity and content identity
  checked for all three archives; 189 unique tile IDs; 127 backend tile rows;
  no incomplete marker or label files. One training image visually inspected.
- Maximum affine corner reconstruction residual: `2.3283064365386963e-10` px.
  Cross-split envelope overlap pairs: zero. These checks do not establish
  absolute map accuracy or independent symbol counts.
- Pinned public NADCON grid acquired; transforms run offline. Chosen operations
  report 5 m nominal accuracy for WGS84 and 0.15 m for California Albers.
  PROJ still reports `best_available=false` and unavailable preferred operations;
  per-tile metadata preserves warnings. Those operation figures are not observed
  well-location accuracy. No additional grid purchase or cloud call is needed.
- Weights, training, inference, precision/recall, known-well offsets: not run.
  Next action: human annotation per [ANNOTATION.md](ANNOTATION.md), then actual
  map/control-point checks and a recorded YOLO baseline.

## Proposal pilot: proposals_pilot_v2 — 2026-10-23

- Purpose: reduce drawing from scratch while preserving human review; Master
  Plan symbol-labeling acceptance remains pending. This is not training/evaluation.
- Command: `.venv/bin/python -m pipeline.propose_annotations`.
- Code base: `97cb53abf68bf07d1fa23ebe56bcbf8646753605` with uncommitted proposal
  implementation in this PR; exact script hash is recorded in the output summary.
- Input manifest: the `kern_1024_v1` manifest above, unchanged.
- Attributed input: [Ciulla et al. EDX outputs](https://doi.org/10.18141/2452768),
  `CA_OilCenter_293661_1954_24000_geo_detected.json`, SHA-256
  `87c2ec22f1b38068be568fb58425c5ed769c11cc16ef640637af50f6863dc6d5`.
  The source README describes CC BY 4.0. No external weights/code were executed.
- Method: convert published WGS84 centers into native pixels using each exact
  raster/tile transform, then clip heuristic 16 px boxes at image boundaries.
  Deterministic greedy selection maximizes additional published IDs in four
  training examples; validation/test/buffer and other rasters are rejected.
- Output: `data/ml/proposals_pilot_v2/`, ignored. Four Oil Center 1954 training
  images, 973 proposals, 889 distinct published IDs because images overlap.
  Images are byte-identical to preparation outputs; no original labels changed.
- Preview: `preview.html`; optional import: `roboflow_proposals_train.zip`.
  The import includes `darknet.labels` for the class name. Earlier local v1 is
  retained as preliminary; use v2, which adds the label map and dirty-tree record.
  The preview toggles generated SVG rectangles over original PNGs, preserving
  the original image pixels. No active training config was generated.
- Validation: 15 ML unit tests passed; 973 YOLO rows checked for counts,
  normalization and clipping; all four copied image hashes and ZIP integrity
  checked. Original preparation directory still has no label files.
- Software/hardware: same local preparation environment recorded above, CPU;
  no new dependency install, external upload, account login, API or GPU cost.
- Human review: zero verified locally. No precision/recall, actual well count,
  completeness, geographic accuracy, or time-saving claim. Known risks: source
  false predictions/omissions, coordinate shifts, approximate box sizes, and
  absent 1992 coverage. Review the whole image, not only proposed boxes.
- Next: correct/complete pilot annotations, record reviewer/tile IDs, add the
  other era and negatives, then prepare a reviewed YOLO training subset.

## Human export audit: reviewed_v1 — 2026-10-23

- Purpose: Master Plan annotation/1024 px/source-split acceptance, before training.
  Code base `7bb3eb6b64de0d111cbc4ccce07a8ed550bb3f1e` with uncommitted audit
  implementation in this PR; exact script hash and dirty state are in `audit.json`.
- Command: `.venv/bin/python -m pipeline.audit_annotations data/ml/reviewed_exports/dowser-kern-well-symbols.v1-manual_5_images_v1.yolov8.zip`.
- Archive SHA-256:
  `70a6d70a642271b6bd6e4dcffaf8cb77359001070771ead80ea315d37d40271e`.
  Original ZIP unchanged; matches Roboflow v1 `manual_5_images_v1`.
- Frozen input manifest SHA-256:
  `fdc01146873c0d5e5e0c6c4c95e7eae51998f872fd1746dc8c6919151f4d19af`.
- Output: ignored `data/ml/reviewed_v1/`, original PNGs plus imported label files,
  `audit.json`, toggleable `review.html`, `large_boxes_review.png`, YAML template.
- Exact tile/counts, all still Train:

| Tile ID | Date-on-map | Boxes |
| --- | --- | ---: |
| usgs_102321_x01250_y03651 | 1992 | 271 |
| usgs_293661_x02149_y03639 | 1954 | 232 |
| usgs_293661_x03787_y05277 | 1954 | 27 |
| usgs_293661_x04606_y04458 | 1954 | 15 |
| usgs_293661_x04606_y05277 | 1954 | 23 |

- Total: 568 boxes (297 from 1954, 271 from 1992), class 0 `well_symbol`.
  Zero empty negative images, zero labeled validation/test images. User reports
  all five complete; full semantic/completeness approval is pending.
- Export JPEGs are RGB 1024×1024, recompressed (mean absolute channel difference
  2.44–4.27 from source PNGs), with identity pixel alignment preferred over
  tested 1/2 px shifts. Restore original source PNGs rather than training on
  recompressed copies; hashes verified. This is not absolute geographic validation.
- Three boxes exceed edges by <=0.005 px from export rounding. Only these tiny
  overflows are clipped/logged in the derived copy. No semantic bounds or cloud
  annotations changed. Source rows are preserved in the original archive.
- Fifteen 1992 boxes exceed the 40 px review heuristic. Visual inspection of
  their plotted neighborhoods shows unnecessarily loose bounds around symbols;
  this is a quality issue, not rejection solely by size. Source export rows:
  11,12,18,20,23,24,26,27,30,31,32,35,36,38,39. Other labels still need review.
- All 21 ML tests passed. Actual output counts, original PNG hashes, and source
  archive identity rechecked separately. No training/precision/recall measured.
- Added audit environment: PyYAML 6.0.2 and matplotlib 3.9.4 on the existing local
  CPU/Python 3.9.6 environment. Dependencies are pinned; no cloud compute started.
  Roboflow version-generation credit usage was not observed by this local audit.
- Export YAML references absent valid/test directories. No active training YAML
  is generated; do not silently random-split five overlapping training images or
  claim quality against training examples. Correct identified bounds, preserve
  revised export, then complete independent evaluation data/training setup.

## Corrected human export: reviewed_v2 — 2026-10-24

- Command: `.venv/bin/python -m pipeline.audit_annotations data/ml/reviewed_exports/dowser-kern-well-symbols.v2-manual_5_images_v2.yolov8.zip --output data/ml/reviewed_v2`.
- Committed auditor: `7db062f67a0fb0db81b4472b312880b03e3f7dfb`, clean at run time;
  script SHA-256 `fc04807bfba3018d9b4e2265f96a1e39080b891bc11d1269cad0fb152d5f8d3b`.
  Same frozen manifest/environment as v1; no new dependencies or model run.
- New ZIP SHA-256:
  `cf894e141a525300c2d3acb01af0e9521ed1a4c6b8a7d8b3c7f5bdcdcb7da5dd`.
  Both original ZIPs and derived v1 are preserved.
- V2: same five Train IDs, 568 boxes, one class, 1024 px, 297 boxes from 1954
  and 271 from 1992. Native PNG hashes and export alignment pass. Two <=0.005 px
  edge-rounding overflows are clipped/logged only in the derived copy.
- Compared the two audit JSON files by tile ID and coordinate multisets rounded
  to 1e-7 px: 527 boxes retain geometry (including all 297 from the four 1954
  images). The 1992 image retains 230 unchanged boxes and 41 unmatched boxes in
  each version. Raw row-by-row comparison is invalid because one annotation
  moved to the end, shifting many line numbers.
- Remaining boxes paired by minimum total Euclidean center distance with
  `scipy.optimize.linear_sum_assignment` (existing SciPy 1.13.1). Maximum paired
  displacement 7.657 px. Pairing is a geometric aid, not persistent object identity.
- Old large-box flags: 15; new flags: 0. All 15 old large boxes are present among
  the changed/pairable regions. Visually inspected `changes_review.png`: the new
  bounds are tighter around the symbols. No new redraw request for this batch.
- Comparison saved in `data/ml/reviewed_v2/comparison_v1_v2.json`; native-pixel
  review figure uses red for v1 and green for v2. No source pixels/ZIPs changed.
- Limits: no complete independent label review, reviewed empty negatives,
  validation/test annotations, training or measured precision/recall. Zero size
  flags alone is not semantic approval. V2 is the current label version for the
  first training setup; preserve the global holdouts rather than random-splitting
  these five overlapping training images.

## Training hardware probe — 2026-10-24

- Purpose: choose the first training location; no dataset/model training.
- Hardware: Apple M5, 25,769,803,776 bytes (24 GiB) unified memory.
- Separate ignored `pipeline/.venv/`, Python 3.12.14, PyTorch 2.14.1, NumPy 2.0.2.
  The existing preparation/audit environment is unchanged.
- Setup: `uv venv --python /Users/emirtg/.local/bin/python3.12 pipeline/.venv`,
  then `uv pip install --python pipeline/.venv/bin/python torch==2.14.1 numpy==2.0.2`.
- Check: MPS built/available; Conv2d(3,8,3,padding=1) on input
  `(1,3,128,128)` on `mps`, squared-mean loss `.backward()`, synchronize, assert
  finite input gradient and finite NumPy round-trip. All passed on `mps:0`.
- Output: `data/ml/training_environment_probe.json`. First cold computation
  took approximately 0.521 s; this is not YOLO training latency or a benchmark.
- Decision: first model candidate YOLO11n on local MPS, per
  [training plan](TRAINING_PLAN.md). Full SDK/weights and Validation labels still
  pending. No detector weights trained, no accuracy measured, no cloud compute.

## Validation split revision — 2026-10-24

- Purpose: improve held-out content before fitting, without moving human Train
  or original Test; Master Plan tiling/frozen-holdout acceptance and independent
  validation discipline. Inspection found original 13 Val tiles mostly contain
  padded edge strips. No trained-model errors or Test labels were used to select
  the new tiles; positive well presence is not established until human review.
- Command: `.venv/bin/python -m pipeline.reserve_validation`.
  Config: `pipeline/config/validation_revision.json`; base manifest hash remains
  `fdc01146873c0d5e5e0c6c4c95e7eae51998f872fd1746dc8c6919151f4d19af`.
- Code base: `e1a4b4cc1ab01257b177dc51711bc57cf713d40b` with uncommitted
  implementation. Script SHA-256:
  `7424be94a944375579a5b8aa85a493b25732c033fb2494e06ee7fdf472e8874e`.
- Reserved full-content images: `usgs_293661_x03787_y02820` (1954) and
  `usgs_102321_x03707_y02832` (1992). Kept old 13 Val; ten other overlapping
  Train neighbors across editions became buffer. All five human Train tiles and
  original 30 Test IDs stay unchanged. This was done before any optimizer step.
- New output `data/ml/kern_1024_v2/`: 189 rows, 72 Train / 15 Val / 30 Test /
  72 buffer; 117 native PNGs. Original v1 is preserved. New manifest SHA-256:
  `ebb2f8a4fdfefabf7dcdd9f3e4339f4c5912d4b2b2ecbb448b3f6da06c0ef572`.
- New `annotation_import/val.zip`: 15 PNGs, images only, SHA-256
  `fe518b3af93be4973e0971b155bb6cde3cae3ca992f038a21c0fd46712af69a9`.
  ZIP integrity and every image's byte identity checked; all 117 retained PNGs
  equal original preparation outputs. Zero cross-split metric-envelope overlap.
  No labels, negatives, geographic accuracy, or detector metrics inferred.
- Source v1/v2 Roboflow ZIP hashes and 568 Train boxes reverified unchanged.
  New Validation uses a separate Roboflow project to avoid duplicate skipping of
  two tiles already present in the original project's unreviewed Train queue.
  Original remaining queue is obsolete as a split list: 67 still Train, 2 Val,
  10 buffer. None of those unreviewed files enters fitting.

## YOLO environment and full-model compatibility — 2026-10-24

- Purpose: prepare the first local detector run, not fit/evaluate a detector.
  Hardware/OS: Apple M5, 24 GiB, macOS 26.6.2 ARM64. Separate Python 3.12.14
  environment `pipeline/.venv/`; root preparation environment unchanged.
- Installation with `ultralytics==8.4.185 numpy==2.0.2` failed dependency
  resolution because current macOS SDK dependencies exclude NumPy 2.0.x.
  Resolved with `uv pip install --python pipeline/.venv/bin/python
  ultralytics==8.4.185 'numpy>=2.3.5,<3'`. Actual NumPy 2.5.4, torch 2.14.1,
  torchvision 0.29.1. Direct requirements and all 41 installed package pins are
  committed; each pin checked against installed metadata. No cloud compute.
- Pretrained weights: official
  [yolo11n.pt release](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt),
  5,613,764 bytes, SHA-256
  `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
  Local ignored weights/metadata under `data/ml/weights/`. No external model
  architecture source was substituted for the planned YOLO detector.
- Command: `pipeline/.venv/bin/python -m pipeline.probe_training`.
  Code base `e1a4b4c` plus uncommitted implementation, script SHA-256
  `8b8c674d41c9ab36d21bf36a9b33163f9db5455ba3216bb24a38383abb39d752`.
  Single-class DetectionModel transfers compatible pretrained features; input
  `usgs_102321_x01250_y03651`, 271 actual human Train boxes, batch 1, 1024 px,
  MPS, float32. Detection loss and backward pass, no optimizer creation/step.
- Result `data/ml/yolo11n_backend_probe.json`: finite gradients, loss
  9.857385635375977 (box 3.723721742630005, cls 4.3629584312438965,
  DFL 1.7707054615020752), approximately 5.976 s. This probe was not seeded for
  identical loss replay; its purpose is operator compatibility. No epochs,
  optimizer updates, trained checkpoints, Val/Test reads or quality measurements.
  No complete training latency, batch-2 capacity or successful rendering claim.
- Runner/config: `pipeline.train_detector`, `pipeline/config/train_smoke.json`;
  pinned pretrained weights, 5 epochs, native 1024, batch 2, mps, workers 0,
  amp false, seed 42, AdamW/lr0 0.001, warmup 0, augmentation off, max_det 1000.
  Five human Train images only; all 15 Val must be independently reviewed.
  Negative-only Val is explicitly diagnostic: recall/mAP unavailable. A later
  quality baseline requires positive independent Val and a separate config.
- `pipeline/.venv/bin/python -m pipeline.train_detector --check-only` exits 2
  with `Missing reviewed val import`, expected. It creates no training run.
  33 ML unit tests passed, covering added archive/negative/split/preflight cases.
- Setup receipt `data/ml/training_setup_receipt.json`, recorded at
  `2026-10-24T10:30:23Z`, preserves code/config/lock/artifact hashes and dirty
  state. Full-lock SHA-256:
  `5794c25ad8f342769da318955f4ec130e57d0f21ced409c00df79a15c9ced9f7`.
  No hosted session, API call, account upload or paid compute started by setup.
  Installed SDK/pretrained checks do not establish detector accuracy.

## Human Validation import — 2026-10-24

- Command: `.venv/bin/python -m pipeline.audit_annotations data/ml/reviewed_exports/dowser-kern-validation.v1-manual_validation_v1.yolov8.zip --dataset data/ml/kern_1024_v2 --split val --output data/ml/reviewed_validation_v1`.
- Source ZIP SHA-256:
  `ec7d27d31dd023420aeac3a0c9e09e5ce9fc3526e0a4cf9f26fa79f64a5ac8bb`;
  unchanged. Clean code `a3cf3793a571d993c67be53293a5691dde779fdb`;
  auditor SHA `ee6076f64a5eee8e7c8d38cf22f586cae71e86e24714f9f1815cd74d35bcd709`.
- Frozen v2 manifest SHA:
  `ebb2f8a4fdfefabf7dcdd9f3e4339f4c5912d4b2b2ecbb448b3f6da06c0ef572`.
  All 15 Val IDs matched, no resized/shifted geometry; original PNGs restored.
  49 boxes on four Oildale 1954 strips (8, 13, 27, 1), 11 explicit empty labels.
  All four 1992 images are negative; no per-era 1992 recall can be measured.
  Box instances across overlapping images are not counts of unique wells.
- One <=0.005 px right-edge rounding overflow clipped/logged only in the derived
  copy. Zero >40 px size flags. Native-pixel contact figure for four positives
  and both full negative tiles visually inspected; not full independent semantic
  completeness approval. Audit/review HTML and contact figure are local artifacts.
- Audit JSON SHA:
  `1a88c5c0d2d38e96c87ff7ad395e93d0c2cae52a80ccfa7437a39170201fcc2e`.
  Preflight now passes 5/568 Train and 15/49 Val, test_used=false.
  Preparation/audit Python 3.9.6 environment unchanged. No cloud training/upload.

## First five-epoch diagnostic: kern_yolo11n_smoke_v1 — 2026-10-24

- Command: `pipeline/.venv/bin/python -u -m pipeline.train_detector --name kern_yolo11n_smoke_v1`, log `data/ml/kern_yolo11n_smoke_v1.log`.
- Clean code `a3cf3793a571d993c67be53293a5691dde779fdb`, config at that commit
  (before nbs was explicitly set). Run metadata preserves the actual full config.
  Pinned official pretrained YOLO11n, source SHA
  `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1`.
  Train audit SHA `eee6fa445dd1b0ddd606ad18704f870e617c0156d310925425e8bde8a746d55b`;
  Val/manifest identities above. 5 Train images/568 boxes; 15 Val images/49 boxes.
  Final Test not read. Python 3.12.14, torch 2.14.1, torchvision 0.29.1,
  ultralytics 8.4.185, numpy 2.5.4, Apple M5/MPS, 24 GiB.
- Actual settings: 5 epochs, imgsz 1024, batch 2, workers 0, amp false, seed 42,
  AdamW/lr0 .001, warmup 0, augmentation off, max_det 1000. SDK default nbs=64.
  Completed all epochs; cumulative epoch clock ~14.645 s (not full process wall
  time). Final validation speed: ~40.9 ms inference per image in this tiny run,
  excluding preprocessing (~0.7 ms) and postprocessing (~18.5 ms); not full-sheet
  latency or a production benchmark. MPS warned some operations are nondeterministic.
- Saved best-checkpoint framework Val metrics: P=0.2787836770837814,
  R=0.08163265306122448, mAP50=0.04438908780269761,
  mAP50-95=0.017124950603355435. These are SDK sweep-based metrics, not measured
  at fixed confidence 0.4, not per-era 1992 recall, and not untouched final Test.
  Final revalidation differs slightly from the final CSV row; report which one.
- Local outputs under `data/ml/runs/kern_yolo11n_smoke_v1/`: run.json,
  training/results.csv, plots and weights. Best.pt SHA:
  `c1f0b64a6f34c1d4819b1f8e86c1ec7f82f1059d70d0656941184d0eb8234f94`;
  last.pt SHA `636e53745030c9eaf3121be61bfcaee6c7098cf5fb67deb24eb5f0d9cbc04030`.
- Finding from installed primary SDK source: accumulate=min(round(nbs/batch),
  total_batches)=15, with only 15 batches in this run. Cadence implies one
  optimizer step, not five meaningful training passes; no step counter was
  installed in this historical run. Do not infer updates from epoch count.
  Before the baseline, set nbs=2 at batch=2 and record actual optimizer post-step
  calls/epochs/timestamps. Added two failure/progress tests; all 35 ML tests pass.
- Next: separately committed baseline config, up to 50 epochs/patience 10,
  warmup 3, nbs 2, same pretrained start and frozen data. Render predictions and
  inspect false positives/negatives. The diagnostic is preserved as a setup run,
  not acceptable detector quality or a reason to change final Test membership.

## First baseline: kern_yolo11n_baseline_v1 — 2026-10-24

- Command: `pipeline/.venv/bin/python -u -m pipeline.train_detector --config pipeline/config/train_baseline.json --name kern_yolo11n_baseline_v1`, log
  `data/ml/kern_yolo11n_baseline_v1.log`. Clean code
  `13c0f7ca1d9012ff58b29dcf6c640421c5e48535`.
- Config SHA `1204376aa8ed9336c333a6e5e06f9a4025eeb6b49038d0e9d75a847924cbf1c7`.
  Same frozen manifest, five-image Train import (568 boxes), 15-image Val import
  (49 boxes/11 negatives), source weights and Python 3.12.14/SDK environment as
  the diagnostic above. Started from pretrained YOLO11n, not the smoke checkpoint.
  Apple M5/MPS, 24 GiB, batch 2, nbs 2, imgsz 1024, workers 0, amp false,
  AdamW/lr0 .001, warmup 3, seed 42, augmentation off, max_det 1000.
- Requested up to 50 epochs, patience 10. Started `2026-10-24T11:31:13.958657Z`,
  finished `11:32:23.077495Z`; runner elapsed **69.107 s**. Early stop after
  **29 epochs / 87 actual optimizer post-step calls**. CSV best mAP50-95 row is
  epoch 19. MPS logged ~3.25 GiB allocated during observed batches, not a measured
  system-wide peak; nondeterministic-operation warnings mean seed does not imply
  bit-identical MPS replay. No cloud compute or Test inputs.
- SDK revalidation of selected best.pt: precision 0.5388106177570324,
  recall 0.8345309161603993, mAP50 0.6483984825827707,
  mAP50-95 0.33465734125197244. SDK confidence-sweep metrics are distinct from
  fixed-cutoff predictions below. Do not conflate them or call either final Test.
- Best.pt SHA:
  `c1a09e4b094408283f3f425c6e2e98504195995b3fa4649cabe7aa63898379bb`;
  last.pt `bccf92fd910164e41cd2dea2ee4134a6ee7a141b9a9faa583813f078f79f6d4a`.
  run.json SHA `3fb8782eb7af5a39016d20cb8f6e7a929c2508080ce671e105c8a1e4e516df98`;
  results.csv SHA `6cbf2c47393374d0751f257347e1d7bd80ac60dbd321e4b80c870b4649a77798`.
  Actual SDK args, plots, and all checkpoints stay under the ignored run directory.
  Training curves and the SDK Val prediction mosaic were visually inspected.

## Baseline preview and threshold tuning — 2026-10-24

- `pipeline/.venv/bin/python -m pipeline.preview_detector data/ml/runs/kern_yolo11n_baseline_v1`
  generated 20 records: 15 Val and 5 seen-Train. Test never read. Helpers were
  being added on top of committed training code; final source/artifact hashes
  are retained in the run's `artifact_receipt.json` after report verification.
  Prediction source is the best checkpoint above, 1024 px, MPS float32, batch 2,
  NMS IoU .7, max_det 1000, minimum saved confidence .05. Native xyxy is converted
  directly to xywh with no half-pixel shift; original PNGs are referenced unchanged.
- Prediction iteration took ~1.884 s for 20 images, excluding model construction
  and HTML rendering. This is local diagnostic timing, not full-sheet throughput.
  `preview/predictions.json` SHA:
  `ad760bc4c73af38c9f2c1b5ad00ad5ff2e425c7032cd07cd150bc8c0e1c25b43`.
  Original `preview.html` opens at .40; `preview_selected.html` at the selected .70.
  Interactive controls select Train/Val, display cutoff and ground-truth/model
  overlays; sliders do not recompute metrics or change the saved predictions.
- Fixed evaluation command: `pipeline/.venv/bin/python -m pipeline.evaluate_preview data/ml/runs/kern_yolo11n_baseline_v1/preview/predictions.json`.
  Confidence .40, IoU .50: **48 TP / 215 FP / 1 FN**, P .18250950570342206,
  R .9795918367346939. High recall at this starting cutoff hides many lookalike
  false detections; do not report SDK sweep P/R as the score at .40.
- Threshold tuning command: same evaluator with `--sweep`. Maximize per-tile
  F1 over .05..95 inclusive in .01 steps, ties favor higher cutoff. The original
  selection/grid were replayed into a separate temporary report and matched.
  Selection is Val tuning only; no Test/Train quality used. Matching: confidence
  descending, highest-IoU unmatched human box per prediction, threshold IoU .50,
  one-to-one within a tile. Overlapping tiles are counted separately, no geo dedup.
- Selected .70: **31 TP / 23 FP / 18 FN**, P .5740740740740741,
  R .6326530612244898, F1 .6019417475728156. Per era: 1954 TP31/FP21/FN18
  (P .5961538461538461, R .6326530612244898); 1992 TP0/FP2/FN0, recall undefined
  because there are no positive 1992 Val labels. Selection saved in
  `preview/threshold_selection.json` and `pipeline/config/inference_baseline.json`.
- Fixed selected-cutoff replay: evaluator with `--confidence .7 --output
  data/ml/runs/kern_yolo11n_baseline_v1/preview/evaluation_conf070_iou050.json`.
  The evaluator refuses to overwrite reports. To regenerate the selected HTML
  without GPU inference, call `pipeline.preview_detector.render` with the saved
  JSON records, minimum .05, initial .70, filename `preview_selected.html`.
- Limits: four positive strips are geographically narrow and overlap. No held-out
  Test labels/performance, calibrated confidence, absolute geo accuracy or broad
  1992 recall. Overall fixed-cutoff precision remains below .60 target. Next
  inspect false detections, add reviewed **Train** negatives/lookalikes from its
  existing partition (never repurpose Val/Test), then independent Test/geo checks.
- 40 ML tests pass, including native-box preview checks, one-to-one duplicate
  matching, Train exclusion and undefined recall for all-negative examples.
  Original source ZIP hashes and native image references rechecked. No backend
  detections/candidate load, evidence publication, deployment or API call.

## Text/lookalike error review and Train mining — 2026-10-24

- Trigger: user observed letters/digits detected as wells in the baseline preview.
  No retraining or change to baseline/Val/Test annotations in this task.
- Reused baseline saved predictions SHA
  `ad760bc4c73af38c9f2c1b5ad00ad5ff2e425c7032cd07cd150bc8c0e1c25b43`.
  Error gallery filters score>=.70 and max IoU to any existing label <.10;
  32 unmatched candidates across seen-Train/Val, 16 displayed with <=4 per tile.
  `data/ml/error_review_v1/review.json` preserves tile/box/source identities;
  `unmatched_predictions.png` shows native 90 px neighborhoods. Visual inspection
  confirms letter/number examples (O/9/4/8/e), structures and contour marks.
  Unmatched candidates are not automatically approved false/negative GT.
- Existing data: five Train images/568 boxes, no explicitly empty Train images;
  positive-image background is present but diverse hard negatives are limited.
  Working hypothesis is insufficient data/context variety and possible label
  inconsistency, not proven architecture failure. See IMPROVEMENT_PLAN.md.
- Mining code base `154ce556e3f8d4ce4683595c725c516f0bba9fa2`, dirty helper
  additions. Pinned baseline best.pt SHA
  `c1a09e4b094408283f3f425c6e2e98504195995b3fa4649cabe7aa63898379bb`;
  active frozen manifest SHA unchanged:
  `ebb2f8a4fdfefabf7dcdd9f3e4339f4c5912d4b2b2ecbb448b3f6da06c0ef572`.
  Same local training environment, MPS, native 1024, batch 2, NMS IoU .7,
  proposal cutoff .4, max_det 1000. No model parameter updates.
- First command `pipeline/.venv/bin/python -m pipeline.mine_training_batch`
  used a preliminary config output `data/ml/hard_negative_review_v1` and inferred
  **55** full-content unreviewed Train images. Twelve other unreviewed Train images
  failed valid_fraction>=.95; all five human Train IDs, Val/Test/buffer excluded.
  Initial six-image selection included a 207-prediction dense tile, so it is
  superseded for this small review workload, not presented as empty background.
- Revised selection replay, without a second GPU inference:
  `pipeline/.venv/bin/python -m pipeline.mine_training_batch --predictions data/ml/hard_negative_review_v1/proposals.json`.
  Current config output `hard_negative_review_v2`. Prefer 1..35 predictions at
  .70, up to two per source, disjoint envelopes across editions; return five
  rather than force a sixth dense frame. This ranks workload, not true object
  count or actual text errors; all selected images still require full review.
- Selected IDs: `usgs_102321_x04526_y05289`, `usgs_293661_x01330_y05277`,
  `usgs_293664_x02138_y05275`, `usgs_102321_x02888_y05289`,
  `usgs_293664_x03776_y03637`. All five visually inspected. Gallery includes
  text/contours/tanks and sparse real-looking symbol groups; no empty label files
  or semantic approvals generated. Human labels added: **0**.
- Current proposals JSON SHA:
  `f5d713f033da557499a770b2462d67a13bc22ee36e2b4a1ac4985a3f248ddb4c`.
  `review_train_images.zip` SHA:
  `699ffa995d5ffa7d3a652db8eb37da3e8763bb9848d9a591e768ebd363ea0b8c`.
  ZIP contains five native PNGs only; integrity, source-byte hashes, exact selected
  IDs and replayed selection checked. Preview labels proposals as unreviewed.
- 44 ML unit tests pass, including four mining selection/integrity-boundary
  cases. Baseline checkpoint, source label imports and frozen held-outs unchanged.
  No claim of improved precision/recall before reviewed additions and a controlled
  retrain/comparison. Actual package source/script identity is in proposals.json.

## Model-run template

```yaml
run_id: pending
date_timezone: pending
purpose_and_prd_ids: pending
code_commit: pending
working_tree_clean_or_diff_reference: pending
dataset_manifest_and_checksum: pending
label_version: pending
split_manifest_and_checksum: pending
sheet_ids_map_years_and_geographic_groups: pending
train_val_test_tiles_and_box_counts: pending
base_weights_source_version_and_checksum: pending
config_path_and_checksum: pending
seed_and_augmentations: pending
software_lockfile_versions_and_hardware: pending
exact_train_command: pending
exact_eval_command: pending
selected_confidence_and_selection_method: pending
iou_matching_and_dedup_protocol: pending
actual_precision_recall_per_era_and_counts: pending
latency_and_measurement_conditions: pending
weights_uri_and_checksum: pending
metrics_curves_and_error_crops_uri: pending
observations_limitations_and_next_action: pending
```

For the final report, identify the selected run and explain the selection. State
which results were used for tuning and which, if any, came from untouched test
data. Preserve false-positive and false-negative examples, not only successful
crops. A fixed seed helps reproduce a run but does not guarantee bit-identical
results across devices or software versions.
