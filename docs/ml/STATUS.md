# ML status and handoff

Last verified: 2026-10-24, America/Los_Angeles.
Branch: `ml/tile-georeferencing`; main `2b4678a` incorporated via `bc3c0ae`.
[Draft PR #3](https://github.com/kunjalp/Dowser/pull/3) remains the integration proposal.
PRs #1/#2 superseded; ML agent has not merged a PR into main.
Editor entry point: [CONTINUE.md](../CONTINUE.md).

## Current selected model

**Assistant completed the additional annotation and trained two data experiments
under Emir's explicit instruction. Current candidate is kern_yolo11n_data_v2.**
Original human annotations and frozen Val/Test are unchanged. New labels are
explicitly assistant-reviewed, not human ground truth.

Open the paired report:
`data/ml/runs/kern_yolo11n_data_v2/comparison_to_baseline/comparison.html`.
It shows the same 15 human-Val images side by side, both selected thresholds,
and an option to display a common .70 cutoff. Individual new-model preview:
`data/ml/runs/kern_yolo11n_data_v2/preview/preview_selected.html`.

| Run | Train supervision | Epochs / actual updates | Val-selected cutoff | TP / FP / FN | Precision / recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| baseline_v1 | 5 human images / 568 boxes | 29 / 87 | .70 | 31 / 23 / 18 | .5741 / .6327 | .6019 |
| data_v2 (selected) | 5 human + 3 assistant images / 617 boxes, 1 empty | 24 / 96 | .24 | 44 / 17 / 5 | .7213 / .8980 | .8000 |
| data_v3 | 5 human + 5 assistant images / 617 boxes, 3 empty | 27 / 135 | .27 | 43 / 17 / 6 | .7167 / .8776 | .7890 |

Both data experiments start from the same pinned pretrained YOLO11n and baseline
settings (native 1024, batch=nbs=2, MPS, AdamW, no augmentation, max 50 epochs,
patience 10). More data changes actual optimizer-update count, so this is not a
perfect equal-compute causal test. Data_v2 ran 52.689 s, data_v3 62.010 s on M5.

Thresholds were independently selected using the **same Val-only F1 grid**
.05..95 step .01, IoU .50, confidence-first one-to-one per-tile matching.
Confidence scores changed scale after retraining: at common .70 data_v2 emits
no Val detections (P undefined/R0), while data_v3 has TP7/FP0/FN42.
Do not claim improvement at the same .70 cutoff or confuse scores with calibrated
probability. The report includes both common and selected operating points.

These are **human Validation/tuning results, not final Test performance**.
All 49 positive Val instances occur on four overlapping Oildale 1954 strips.
There are no positive 1992 Val labels. At selected cutoffs, baseline has 2 FP on
1992 negatives, data_v2 has 3 and data_v3 has 2: not every slice improved.
Visible residual errors include digits, rectangular signs and tanks; 17 FP remain.
Do not claim the text-confusion problem is solved or broad per-era accuracy.

## Reproducible artifacts and label provenance

- Selected weights: `data/ml/runs/kern_yolo11n_data_v2/training/weights/best.pt`,
  SHA `a409254df3769cb119b0b2396e44df5038a669dc748d22a28a4fdf173095f5df`.
  Current diagnostic inference config: `pipeline/config/inference_selected.json`.
  The baseline weights/config remain preserved separately.
- Original user import `data/ml/reviewed_v2/`: 5 images, **568 human boxes**,
  297 old-era/271 1992, untouched. Original source ZIPs retained.
- User authorized assistant labeling/training on 2026-10-24. All five proposed
  Train additions were visually reviewed in full, with enlarged coordinate plots
  for positive cases. `data/ml/assistant_review_v1/annotations.json` has
  **49 assistant boxes**, 22 on 1992 and 27 on 1954, plus 3 assistant-reviewed
  empty-background decisions. `human_verified=false`, assistant_visual_review.
  Two missed circle centers were added explicitly; one right-edge symbol clipped
  to visible pixels. Blue water-well marks, text/rectangles/solid tanks/contours
  were excluded. Review is not independent human/field verification.
- `data/ml/train_mixed_v1/`: 8 images/617 boxes/1 empty, selected experiment.
  `train_mixed_v2/`: 10 images/617 boxes/3 empty, comparison experiment.
  Human PNGs/labels copied byte-for-byte; extra annotations remain traceable.
  Builder never promotes raw model proposals into labels or alters split IDs.
- Mixed-supervision configs require explicit opt-in, source-specific counts,
  and >=300 original human boxes. Preflight rejects assistant Val truth and
  human-label overwrites. Preview uses green for human, purple for assistant
  annotations and orange for model predictions. Paired Val report is human GT only.
- Active `data/ml/kern_1024_v2/manifest.jsonl`: 72 Train / 15 Val / 30 Test /
  72 buffer, SHA `ebb2f8a4fdfefabf7dcdd9f3e4339f4c5912d4b2b2ecbb448b3f6da06c0ef572`.
  Val import `reviewed_validation_v1`: 15 images/49 boxes/11 human-reviewed
  negatives, original audit/hash untouched. Test remains unlabeled and unused.
- Three pinned GeoTIFF editions: Oil Center 1954/revised1968, Oildale 1954 and
  Oil Center 1992/edit1995, across two quadrangles. Native pixels, source dates,
  WKT/affine, masked collars and shared cross-year geographic partition preserved.
  Original v1 preparation retained; zero cross-split metric-envelope overlap.
- Environments: root `.venv/` Python 3.9.6 for maps/audit; `pipeline/.venv/`
  Python 3.12.14, torch 2.14.1, torchvision 0.29.1, ultralytics 8.4.185, numpy
  2.5.4 for MPS training. Keep separate pins. Configs/commands/checksums/results:
  [EXPERIMENTS.md](EXPERIMENTS.md), [TRAINING_PLAN.md](TRAINING_PLAN.md).
- The old EDX proposal pilot and Train mining queues are proposals, not the
  selected model's GT or final performance. Pre-existing review instructions
  asking Emir for another Roboflow export are superseded for this experiment.

## Next action

User's latest plan: run an independent Cursor improvement attempt, then return
for review. Dedicated worktree `/Users/emirtg/Desktop/dowser-cursor`, branch
`ml/cursor-improvements`, task/rules/reference identities in
[CURSOR_EXPERIMENT.md](CURSOR_EXPERIMENT.md). Code derives from the current ML
branch because main does not yet contain this pipeline. Local data/environments
are independent copied files, not writable symlinks. This original branch/model
remains the review reference. Cursor must return `docs/ml/CURSOR_RESULTS.md`
and preserve its checkpoints/predictions for inspection; no results exist yet.

No additional annotation work is required from Emir for the completed data
experiments. The paired report is ready to inspect. Current model improves
aggregate Val, but remaining high-score numbers/rectangles need further work.
Use separate future experiments for more context diversity or model changes;
never alter current Val labels to improve a score or absorb Val into Train.

Before pitch/final accuracy: independently label the protected 30 Test tiles,
freeze model/cutoff, evaluate once without Test-based tuning and state map/era
coverage. Assistant training labels are not independently verified evaluation GT.
Do actual-map control points and 10+ known CalGEM offsets before asserting
geographic accuracy; pixel-to-WGS84 primitives already exist.

Then implement model/fallback CSV/crops for Ryann and publish evidence paths.
No backend candidate load, crop publication or final inference-sheet handoff yet.
The teammate's described detect_sheet.py/labels_to_detections.py files remain
absent. Master Plan ownership: Emir ML, Ryann matching/dedup/scoring and overlay
conversion, Kunjal map UI. User withdrew the zero-cost constraint on 2026-10-23.

## Verification and collaboration

- 53 ML tests pass: geometry/split, source/label integrity, mining guards, mixed
  supervision/negative provenance, actual optimizer progress, native preview,
  per-tile matching, human-Val comparison consistency and Test exclusion.
- Both data runs completed from clean committed code; raw metadata records actual
  progress, versions/times/metrics. Original human Train/Val and manifest hashes
  are verified unchanged. Paired reports use identical human Val images/boxes.
- Main 2b4678a integrated; app/Convex/mobile/backend team files unchanged.
  No deployment/API generation/sensor replay/mobile publishing by ML. Training
  was local; no paid cloud compute. Repo docs/config/code stay in the task branch.
- Kunjal works directly on main; fetch/review again before another task/merge.
  PR #3 needs team review; Vercel success is not ML accuracy evidence.
- Preserve ignored annotation JSON/ZIPs, data, weights and environments; Git
  cannot restore them. Ground-truth fallback must retain explicit source and
  the UI convention; never call annotation value 1.0 a model probability.
