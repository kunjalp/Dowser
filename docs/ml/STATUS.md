# ML status and handoff

Last verified: 2026-10-24, America/Los_Angeles.
Branch: `ml/tile-georeferencing`; incorporates main `2b4678a` via `bc3c0ae`.
[Draft PR #3](https://github.com/kunjalp/Dowser/pull/3) is the integration proposal.
PRs #1/#2 are superseded; ML agent has not merged any PR into main.
Editor entry point: [CONTINUE.md](../CONTINUE.md).

## Current result

**First YOLO11n baseline trained and a prediction preview is available.**
Diagnostic: 5 epochs. Baseline: 29 epochs/87 actual optimizer updates, early stop
with patience 10; best CSV fitness at epoch 19. Total baseline runner time
69.107 s on Apple M5/MPS, 24 GiB. No cloud training/deployment was started.

Open locally:
`data/ml/runs/kern_yolo11n_baseline_v1/preview/preview_selected.html`.
Green boxes are human labels; orange are model predictions. Default view is
Validation at confidence 0.70, with toggles and a cutoff slider. Train images
are explicitly marked as seen during fitting. There are 20 images total
(15 Val + 5 Train), and protected Test is excluded. Original PNGs are unchanged.

**Fixed-cutoff Val result at confidence 0.70 / IoU 0.50:**
31 TP, 23 FP, 18 FN; precision 0.5741, recall 0.6327.
Cutoff was selected on Val F1 over 0.05..0.95, step 0.01.
At the original 0.40 cutoff: 48 TP, 215 FP, 1 FN (P 0.1825, R 0.9796).
The model still over-detects lookalikes; the 0.60 precision target is not met.

SDK best-checkpoint metrics separately report P 0.5388, R 0.8345, mAP50 0.6484,
mAP50-95 0.3347. Those confidence-sweep metrics use the SDK evaluation path and
must not be substituted for our fixed-cutoff preview evaluation.
All results are **Validation/tuning, not independent final Test performance**.
All 49 Val positives are on four overlapping Oildale 1954 strips; 1992 contains
negatives only, so its recall is undefined. No claim of accuracy on all maps/eras.

## Artifacts and provenance

- Master Plan is authoritative; Emir owns ML, Ryann dedup/matching/enrichment/
  ranking/overlay conversion, Kunjal map UI. The user withdrew the zero-cost
  restriction on 2026-10-23; record actual material usage.
- Three pinned GeoTIFF editions: Oil Center 293661 (1954, revised 1968, imprint
  1970), Oildale 293664 (1954, imprint 1956), Oil Center 102321 (1992, edit/imprint
  1995). Three editions across two geographic quadrangles. Native 1024 px tiles,
  stride 819, per-tile WKT/affine, masked collars and shared geographic splits.
- Active manifest `data/ml/kern_1024_v2/manifest.jsonl`: 72 Train / 15 Val /
  30 Test / 72 buffer, 189 rows. All retained PNGs equal original v1 pixels.
  Old `kern_1024_v1` remains intact. Revised split preserved five human Train
  IDs and exact 30 Test IDs, with zero cross-split metric-envelope overlap.
- Train import `data/ml/reviewed_v2/`: 5 images, 568 boxes (297 from 1954,
  271 from 1992), class 0 well_symbol. The 15 previously loose boundaries were
  corrected/visually checked; original v1/v2 source ZIPs remain unchanged.
- New Val import `data/ml/reviewed_validation_v1/`: all 15 frozen IDs,
  49 boxes on four images, 11 explicit empty labels, native PNGs restored.
  Original `dowser-kern-validation.v1-manual_validation_v1.yolov8.zip` preserved.
  One 0.005 px edge overflow clipped/logged only in derived copy; zero size flags.
  Positive-strip contact sheet and both full negative tiles visually inspected.
  Structural audit/user-complete status is not independent semantic completeness.
- Baseline weights:
  `data/ml/runs/kern_yolo11n_baseline_v1/training/weights/best.pt`,
  SHA-256 `c1a09e4b094408283f3f425c6e2e98504195995b3fa4649cabe7aa63898379bb`.
  Selected diagnostic inference settings: `pipeline/config/inference_baseline.json`.
- Exact run data/config/code/environment/metrics/checksum records are in
  [EXPERIMENTS.md](EXPERIMENTS.md). Run metadata and checkpoints are ignored.
- Two environments: root `.venv/` Python 3.9.6 for maps/audit;
  `pipeline/.venv/` Python 3.12.14 for training, torch 2.14.1, torchvision
  0.29.1, ultralytics 8.4.185, numpy 2.5.4. Preserve both and their separate pins.
- First diagnostic used default nbs=64, accumulating all 15 batches before one
  inferred update. Config now nbs=2 at batch=2. Baseline instrumented actual
  optimizer post-step calls and epoch/timing progress; interrupted runs retain it.
- Old `proposals_pilot_v2/preview.html` is attributed published research, not
  this trained model. Its old IDs predate split revision; reconcile before reuse.
  Neither published proposals nor Val/Test predictions become Train ground truth.

## Next action

**User update, 2026-10-24:** Emir explicitly asked the assistant to do the additional
annotation and training itself. The previous request for a human Roboflow additions
export is superseded for this experiment. All five candidate images were visually
reviewed by the assistant; 49 target boxes (22 on 1992, 27 on 1954) and three
empty-background decisions are stored under `data/ml/assistant_review_v1/`.
These are assistant-reviewed labels, **not human ground truth**. Enlarged native
views and final box overlays were inspected; blue water-well symbols, digits,
letters, rectangular buildings, solid tanks and contour loops were excluded.

`pipeline.build_train_mix` created `data/ml/train_mixed_v1/`: original 568 human
boxes untouched, plus the two positive additions and one reviewed background tile:
8 Train images/617 boxes, including 49 assistant boxes and one empty image.
Two other reviewed backgrounds are retained for a separate data-ratio experiment.
`train_data_v2.json` keeps baseline settings/pretrained start and explicitly opts
into assistant-reviewed training. Preflight still requires >=300 human boxes and
refuses assistant labels in Validation. Next: run and compare this data ablation
against the same human Val and fixed .70 cutoff; Test unchanged. No further
annotation work is currently required from Emir.

The paragraphs below retain the preceding error-analysis/mining context.

Emir reported letters/digits being detected as wells. Native error-neighborhood
inspection confirms O, 9, 4, 8, e and rectangular/contour lookalikes among unmatched
predictions. Main hypothesis: too little Train variety/context, with possible
annotation inconsistency; the 568-symbol count on five images is not a guarantee.
See [improvement plan](IMPROVEMENT_PLAN.md) for evidence and a controlled data-first
experiment, not a promise that more labels or a larger model automatically work.

**Prepared next batch:** `data/ml/hard_negative_review_v2/preview.html` and
`review_train_images.zip`, five native images from unreviewed **Train only**.
Human task: full-image review in Roboflow, only real well_symbol boxes, Mark Null
only for confirmed empty tiles; preserve Train/1024 px/no random split. Separate
additions project avoids duplicates in the original queue. Export unchanged ZIP
under reviewed_exports. Review instructions and exact IDs are in the plan.

Mining inferred on 55 eligible Train images; model scores select review candidates,
not known negatives. All five selected images were visually inspected, but zero
human labels/negative approvals were invented. Val/Test and original five-image
labels are unchanged. The overly dense preliminary v1 batch is superseded by v2.
No new training run or improved-model result yet; await reviewed additions before
combining versioned Train imports and comparing against the same Val.

Before reporting pitch/final accuracy: independently label the protected 30 Test
images, add positive-era coverage if claiming 1992 recall, freeze model/cutoff,
and evaluate without tuning on Test. Any dataset expansion must retain provenance
and account for already used Val; never silently move it into Train.

Geographic work next: real-map control points and 10+ verified CalGEM well
offsets, then model/fallback CSV/crops for Ryann. Pixel-to-WGS84 primitives already
exist; full detection export/crop publication is not yet completed. The teammate's
described detect_sheet.py/labels_to_detections.py files have not been supplied or
found in main. See [integration review](INTEGRATION_REVIEW.md), a historical
pre-training assessment. YOLO11n is an architecture name, not eleven trained runs.

## Verification and collaboration

- 50 ML tests pass, including fixed-cutoff one-to-one matching, Train exclusion,
  undefined negative-only recall, native preview coordinates and progress/failure
  records. Baseline/saved prediction artifacts and threshold-grid replay checked.
  Four mining checks cover held-out/reviewed/padded exclusions, dense-batch
  filtering and cross-era overlap. Five-image ZIP/native hashes checked; no labels.
  New mix/provenance cases reject held-out additions, human-label overwrites,
  unreviewed predictions, false human-review claims and assistant Validation.
- First diagnostic and baseline finished; previews contain 20 exact audited
  Train/Val inputs and no Test. Native-image links resolve, source ZIPs preserved.
- Main through 2b4678a integrated; app/Convex/mobile/backend team code unchanged.
  No live loading, brief generation, replay, mobile publishing or UI end-to-end
  validation by ML. Vercel success is not ML quality evidence.
- Kunjal works directly on main. Fetch/review again before another code task or
  merge. PR #3 remains an incremental integration proposal requiring team review.
- Keep local data, label ZIPs, checkpoints and environments: Git cannot restore
  ignored artifacts. Ground-truth fallback requires explicit source=ground_truth,
  numeric 1.0 plus the hand-labeled UI convention, not model confidence.
