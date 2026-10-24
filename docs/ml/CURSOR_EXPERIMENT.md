# Independent Cursor model-improvement experiment

Requested by Emir on 2026-10-24, America/Los_Angeles. The user will ask Cursor to
improve the detector independently, then return for a review of the experiment.
This file is the concrete task/handoff; no chat history is required.

## Workspace and branch

Open **`/Users/emirtg/Desktop/dowser-cursor`**, branch **`ml/cursor-improvements`**.
This is a separate Git worktree based on the current ML branch, not main: the ML
implementation has not been merged into main. The original checkout is
`/Users/emirtg/Desktop/dowser`, branch `ml/tile-georeferencing`.

Local `data/`, root `.venv/` and `pipeline/.venv/` are copied with macOS/APFS file
cloning, not symlinked. They initially contain the same bytes, but later writes
are independent. Preserve original reference artifacts in the Cursor copy too;
use fresh `cursor_*` configs/imports/runs/reports. Do not switch branches in the
original checkout or force-push/shared-history rebase. The worktrees share Git
objects/remotes, but their branches, working files and local model artifacts differ.

Some historical run/prediction metadata retains absolute paths to the original
checkout as provenance. Do not rewrite frozen manifests or original run records
merely to relocate them. New training scripts use their own checkout ROOT plus
relative config paths. Historical images may be read as immutable references;
the comparison helper accepts different-root image copies only if bytes match.
Use current-ROOT paths for all new outputs. If adding dependencies, modify only
this copied environment and record its new lock; invoke pip through its Python.

## Read first

Read AGENTS.md, CONTRIBUTING.md, pipeline/AGENTS.md, docs/CONTINUE.md, the full
Master Plan, then docs/ml/STATUS.md, REQUIREMENTS.md, CONTRACT.md,
TRAINING_PLAN.md, IMPROVEMENT_PLAN.md and the latest EXPERIMENTS.md records.
The user has authorized assistant visual annotation and local model training;
do not ask the user to repeat existing labels or treat assistant labels as human
truth. Paid resources are not categorically banned; record material usage.

## Frozen reference to beat

Model/code reference commit before this handoff:
`8b44b8a76bf6b969b633871c23dc927745f58005`.

- Reference run: `kern_yolo11n_data_v2` (not the older baseline_v1).
- Weights: `data/ml/runs/kern_yolo11n_data_v2/training/weights/best.pt`.
- Weights SHA-256: `a409254df3769cb119b0b2396e44df5038a669dc748d22a28a4fdf173095f5df`.
- Inference reference config: `pipeline/config/inference_selected.json`.
- Train import: `data/ml/train_mixed_v1/`, 8 images/617 boxes: 568 human boxes,
  49 assistant-visual boxes, one assistant-reviewed empty image.
- Additional reviewed pool: `train_mixed_v2` has 10 images, same 617 boxes and
  three empty images. This was already tested and was slightly worse on Val F1;
  do not present that unchanged experiment as a new improvement.
- Reference at selected cutoff .24 / matching IoU .50: **TP44 / FP17 / FN5**,
  P=.7213114754, R=.8979591837, F1=.8000. This is human-Val tuning only.
- At common cutoff .70 the selected reference emits no Val boxes. Scores changed
  scale after training; .24 is not a calibrated probability. Always state cutoff.
- Raw predictions and threshold grid are in that run's `preview/` folder; paired
  comparison with the older model is under `comparison_to_baseline/`.

Do not overwrite this reference config/checkpoint/reports to make a candidate
look better. Keep the original reference in any comparison, even if unsuccessful
candidates are trained. The selected baseline is already trained, not a plan.

## Task and invariants

Improve letter/digit/structure false positives while retaining useful recall.
Work autonomously: inspect failures and labels; consider more diverse **Train**
examples, assistant-reviewed hard backgrounds, carefully tested augmentations or
a different YOLO size. Change one major factor per initial experiment where
practical. Record actual update counts/time: adding data changes compute too.
Do not promise a gain in advance or call increased precision with collapsed
recall an overall improvement.

- Keep native 1024 px/image transforms/year/source provenance and the same ROI.
- Frozen manifest: `data/ml/kern_1024_v2/manifest.jsonl`, SHA-256
  `ebb2f8a4fdfefabf7dcdd9f3e4339f4c5912d4b2b2ecbb448b3f6da06c0ef572`.
- Preserve original 568 human Train labels byte-for-byte. New labels get source,
  reviewer/method/image hashes and semantic limitations; uncertain cases must be
  resolved or excluded. Never convert raw predictions to GT/empty negatives by
  default. AI labels stay `assistant_visual_review`, not human labels.
- Preserve **all 15 human-Val images and their existing labels**. Audit SHA-256
  `1a88c5c0d2d38e96c87ff7ad395e93d0c2cae52a80ccfa7437a39170201fcc2e`.
  Never move its negatives into Train, remove hard cases, relabel from model
  suggestions or change geography across splits to improve a score.
- **30 Test images stay protected and unused for model/threshold selection.**
  Do not use their predictions or labels to guide these experiments.
- Val has only 49 positive instances on four overlapping 1954 Oildale strips.
  1992 Val is all-negative. No broad/per-era recall or independent Test claim.
- Keep work under pipeline/ and relevant docs. Backend/UI/schema/deployment and
  merging into main are not required to improve the local model.

## Comparable evaluation

Use the same native-box evaluation protocol: IoU .50, descending confidence,
highest-IoU unmatched GT per prediction, one-to-one per tile. Keep max_det=1000
and record NMS/inference settings. Compare the same human-Val IDs/years/images/
boxes with `pipeline.compare_previews`; do not compare Train scores to Val.

Report both a common fixed cutoff and each model's cutoff selected using the
same `.05..95`, step `.01` Val F1 sweep (ties favor higher cutoff). If changing
evaluation or preprocessing is itself the experiment, re-evaluate both models
under the new protocol and label that comparison separately. SDK P/R/AP must
remain distinct from the native fixed-cutoff counts. Show FP/FN cases, especially
digits/text and 1992 negatives. Gains on this repeatedly used Val are tuning,
not independent proof; small gains may need repeat seeds to assess stability.

## Setup checks and output for the later review

Setup was verified on the handoff machine: separate branch/worktree created,
data/environments file-cloned, copied activation/launcher paths relocated and SDK
output directories isolated inside the new checkout. Python resolves the Cursor
checkout/environment, reference checkpoint/manifest/label hashes match without
shared file identities, training preflight passes and **54 ML tests pass**.
This verifies setup, not a new model improvement. No Cursor model run started yet.

```sh
git status --short --branch
pipeline/.venv/bin/python -m pipeline.train_detector \
  --config pipeline/config/train_data_v2.json --check-only
.venv/bin/python -m unittest discover -s pipeline/tests -q
```

Do not rerun a completed experiment using an existing output name. New weights
stay under `data/ml/runs/cursor_<name>/`; new candidate config should not replace
inference_selected.json before the independent review. Commit code/config/docs
on ml/cursor-improvements; preserve local labels/weights outside Git with hashes.
Update EXPERIMENTS.md and STATUS.md in this branch after meaningful work.

Create **`docs/ml/CURSOR_RESULTS.md`** containing:

1. Branch and commit(s); problem/hypothesis and implemented changes.
2. Each run's exact command/config, pretrained or fine-tuned starting checkpoint
   and SHA, versions/lock, device, seed, elapsed time, epochs/actual updates.
3. Train ID/count/era/source changes, negative-image count, annotation provenance
   and hashes; proof that original human Train, human Val and Test split remained.
4. Reference-versus-candidate TP/FP/FN/P/R/F1 at stated common and selected
   cutoffs, raw metric/prediction/threshold report paths, per-era limitations.
5. Checkpoint path/SHA and a paired local HTML preview; representative improved
   cases and remaining errors. Include unsuccessful experiments, not just wins.
6. Tests actually run, results/limitations and exact next action.

The returning reviewer will inspect this file, branch diff, label provenance,
checksums and real predictions before deciding whether to adopt the candidate.
Do not auto-merge the work or claim success if the candidate is worse/uncertain.
