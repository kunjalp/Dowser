# ML status and handoff

Last verified: 2026-10-24, America/Los_Angeles.
This worktree branch: `ml/cursor-improvements`. Parent ML branch remains
`ml/tile-georeferencing`; main `2b4678a` incorporated via `bc3c0ae`.
[Draft PR #3](https://github.com/kunjalp/Dowser/pull/3) remains the integration proposal.
PRs #1/#2 superseded; ML agent has not merged a PR into main.
Editor entry point: [CONTINUE.md](../CONTINUE.md).

## In progress: repair_v2 (complete-frame annotation + retraining)

Updated 2026-10-24. Details: [EXPERIMENTS.md](EXPERIMENTS.md) "repair_v2".

- Done: all 20 queued error-source Train frames fully reviewed by the
  assistant (156 boxes on 6 frames, 14 reviewed empty; `human_verified=false`)
  in `data/ml/repair_annotation_v2/`. Two Train mixes built, preflight passed.
- Seed 42 Val: `full` (17/30 empty) 33/0/16 at .05, rejected on recall;
  `mixed` 43/0/6 at .67, F1 .9348 vs reference .9293 — not yet a claim.
  Seeds 43/7 and the post-CalGEM candidate regression are running.
- Test: 27/30 audited human tiles present, no conflicts; 3 missing tiles block
  the final run. `pipeline/evaluate_final_test.py` exists; Test untouched.
- Reference pins (`inference_cursor_translate.json`, `inference_selected.json`)
  and delivered archives are unchanged.

## Rollout quality issue: investigate final candidates before promotion

User initially reported 11/15; the expanded Ryann CSV confirms **62 false
symbols among the 64 original unmatched candidates** (58 Train / 4 Val).
The unchanged .71 CSV reproduces 1,657 dedup groups / 796 multi-era / 64 unmatched
candidates. This is a post-CalGEM quality failure; Val P=.92 is not final-candidate
precision. All 64 crops were inspected and the human IDs reconciled. Three new
YOLO fits were worse and rejected. A second-stage verifier prototype improves
Val to 46/2/3 at YOLO .71 + verifier .059, but still leaves 22 known false groups
among 24 unmatched candidates; it is **not promoted**. Original files/model pins
and production statuses are unchanged. [ROLLOUT_REPAIR.md](ROLLOUT_REPAIR.md)
records failures, code, weights and exact evidence. 67 software tests pass; Test
is unused. Do not present the earlier package's candidate list as verified wells.

### Incoming Test annotation and next-agent brief

Latest user screenshot: 12 of 30 Test tiles annotated in Roboflow, 18 pending.
No new Test ZIP is present locally. Export completed images as **100% Test**,
native 1024, no preprocessing/augmentation, YOLOv8 ZIP. Prepared intake folders:
`data/ml/reviewed_exports/test_emir_v1/` and `test_teammate_v1/`. Combine by
original ID and require all 30 unique reviewed tiles; assignments overlap.
Test is evaluation-only. Training repair uses the separate frozen Train images.
See [FINAL_TEST.md](FINAL_TEST.md) and
[NEXT_AGENT_TRAINING.md](NEXT_AGENT_TRAINING.md) for exact continuation.

## Ready for Ryann: geographic integration package

[RYANN_HANDOFF.md](RYANN_HANDOFF.md):
Latest user-requested minimal delivery is `/Users/emirtg/Desktop/Dowser_Ryann.zip`:
exactly `detections.csv`, `crops/` (3,116 PNGs), and the reviewed `best.pt`.
Send sanity output / qualified Val metrics as message text. The earlier detailed
archive `data/ml/handoffs/dowser_ryann_cursor_translate_v1.zip` is preserved with
metadata/provenance. Actual model is the explicit
Cursor translate pin at .71; canonical `inference_selected.json` remains data_v2.
87 Train/Val tiles across three source editions were processed; Test/buffer
were excluded. Raw counts retain overlap duplicates, not distinct/unknown wells.

Sanity: 97.6% within 100 m of a usable CalGEM location, median nearest distance
15.4 m, PLAUSIBLE. This is proximity plausibility, not independent map accuracy.
GeoTIFF source pixels/offsets/affines were verified; actual geographic controls
remain pending. The package itself was produced with 61 checks; current software
has 67 passing tests. Ryann reports using its unchanged CSV; it is not evidence
that ML verified a deployed application. Original
checkout remains unchanged. No dependencies were added.

## Current selected model

Independent Codex review of Cursor commit `0d476cf` is complete:
[CODEX_REVIEW.md](CODEX_REVIEW.md). All candidate metrics reproduce exactly in
fresh MPS inference; 54 tests pass. Two errors were found in the additional
Cursor assistant labels (a filled-circle positive and a missed hollow circle),
which are **not used by the winning translate candidate**. Repair them in a new
annotation version before using `train_mixed_cursor_v1/v2` again. Original
reference pin remains unchanged. The review records seed instability and the
limits of repeatedly tuned, narrowly covered Val results.

Pinned diagnostic config is still `kern_yolo11n_data_v2` /
`pipeline/config/inference_selected.json` pending a separate promotion decision. Cursor's best
challenger is **`cursor_translate_mps`** (translate=0.1, same mix_v1, seed 42):
Val-selected .71, **TP46 / FP4 / FN3**, P=.9200 / R=.9388 / F1=.9293 vs data_v2
.8000. Pair: `data/ml/runs/cursor_translate_mps/comparison_to_data_v2/comparison.html`.
Candidate pin: `pipeline/config/inference_cursor_translate.json`. Seed 43 also
beats .8000 (F1 .8113); seed 7 collapsed. Val-only, not Test.

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

Current priority is detector/candidate repair: complete mixed-context Train
annotations in the 24 human-error source frames (20 not yet fully annotated),
preserving original positives, then compare both native Val and the post-CalGEM
candidate slice. Use `train_error_sources_human_confirmed.json` in
`data/ml/rollout_diagnosis_v1/`. Feedback crop negatives are not empty full images.
Keep the unpromoted verifier as a documented experiment, not a new best.pt.

Start the independent [final-Test labeling handoff](FINAL_TEST.md):
`data/ml/final_test_cursor_v1/test_images.zip` has 30 original Test PNGs, verified
against the active manifest (19 dated 1954, 11 dated 1992). Model/threshold/
scoring/IDs are frozen in `pipeline/config/final_test_cursor_translate_v1.json`.
Human labels and the Test-specific evaluation path/report are still pending;
no model Test inference was run. Keep predictions hidden while labeling.
For teammate help, `/Users/emirtg/Desktop/Dowser_Test_second_half_16-30.zip`
contains original-ZIP positions 16–30 (15 images); Emir retains positions 1–15.
Original 30-image ZIP is unchanged. Exact filenames for each half are in
`data/ml/final_test_cursor_v1/second_half_16-30_receipt.json` and the Test guide.
Latest custom request: `/Users/emirtg/Desktop/Dowser_Test_selected_15.zip` contains
the 15 filenames from Emir's screenshots; this selection overlaps both earlier
halves. Its exact membership is in `selected_15_screenshots_receipt.json` under
the same local Test folder. Combine future exports by IDs, not archive order.
English website instructions for the teammate are in
[TEAMMATE_LABELING.md](TEAMMATE_LABELING.md); annotation and final Test results
are still pending.

The ready [Ryann handoff](RYANN_HANDOFF.md) can be sent in parallel, noting partial
coverage, duplicates and Val-only accuracy. Ryann owns dedup/matching/enrichment/
scoring/loading/publication. Do actual-map controls and 10+ reviewed CalGEM
matches. Preserve data_v2 as reference and correct separate Cursor annotations
before reusing those mixes. No further training is needed for the fixed-model
evaluation or the integration package.

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

Model CSV/crops export is now implemented and packaged; a human-ground-truth
fallback command and full-region inference remain separate unfinished work.
No backend candidate load or crop publication yet. Ryann's supplied scripts
were preserved and adapted under pipeline/; commands are in the handoff doc.
Master Plan ownership: Emir ML, Ryann matching/dedup/scoring and overlay
conversion, Kunjal map UI. User withdrew the zero-cost constraint on 2026-10-23.

## Verification and collaboration

- 67 ML tests pass: geometry/split, source/label integrity, mining guards, mixed
  supervision/negative provenance, actual optimizer progress, native preview,
  per-tile matching, human-Val comparison consistency and Test exclusion.
  The independent Cursor worktree passes training preflight and all 54 tests
  after the new mixes; 67 now pass with geographic handoff and verifier guards.
  Copied data/environments are not symlinks; reference
  bytes match with independent file identities. Cursor trained several named
  `cursor_*` runs; none replaced the selected data_v2 checkpoint.
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
