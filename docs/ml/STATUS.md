# ML status and handoff

Last verified: 2026-10-24, America/Los_Angeles.
Branch: `ml/tile-georeferencing`; incorporates main `558a00b` via `e1a4b4c`.
[Draft PR #3](https://github.com/kunjalp/Dowser/pull/3) proposes integration into main.
PRs #1/#2 are closed/superseded. No PR was merged by the ML agent.
For another editor, start at [CONTINUE.md](../CONTINUE.md).

## Current stage

Human Train annotations and the local YOLO environment/runner are ready.
**No detector fitting: zero optimizer updates, zero epochs, no trained checkpoint,
no measured detection accuracy.** Independent Validation labels are next.
A full-model loss/backward compatibility probe passed on the Apple GPU;
that is not a trained detector.

The [Master Plan](../master-plan/source.txt) supersedes the original PRD.
Emir owns ML; Ryann owns dedup/matching/enrichment/scoring and overlay conversion;
Kunjal owns the interactive map. User withdrew the zero-cost rule on 2026-10-23.
No cloud training, deployment or API generation was started here.

## Verified artifacts

- Three pinned Kern raster editions: Oil Center 293661 (base 1954, revised 1968,
  imprint 1970), Oildale 293664 (1954, imprint 1956), Oil Center 102321 (1992,
  edit/imprint 1995). Region/source config is unchanged.
- Native 1024 px images, stride 819, per-tile WKT/affine, masked collars, common
  geographic partitions across years. Numerical geo checks pass; actual-map
  control points and known-well accuracy remain pending.
- Original preparation `data/ml/kern_1024_v1/` is preserved: 84 Train / 13 Val /
  30 Test / 62 buffer. Its Val consists mostly of padded edge strips.
- **Active split: `data/ml/kern_1024_v2/`**, revised before any fitting:
  72 Train / 15 Val / 30 Test / 72 buffer, 189 rows, 117 retained PNGs.
  Added two full-content unreviewed Val tiles, one per era; quarantined ten
  other overlapping Train tiles across editions. All five human Train IDs and
  exact original 30 Test IDs remain; zero cross-split envelope overlap.
  All 117 retained PNGs are byte-identical to original preparation outputs.
- Human import `data/ml/reviewed_v2/`: **5 Train images, 568 boxes**,
  class 0 `well_symbol`; 297 from 1954, 271 from 1992. Native PNGs restored.
  Both source ZIPs in `data/ml/reviewed_exports/` remain unchanged.
  All 15 previously loose bounds have tighter v2 replacements, visually checked;
  zero boxes exceed the 40 px review heuristic. Full independent semantic
  completeness is not established. No repeat of those corrections is requested.
- Old `data/ml/proposals_pilot_v2/preview.html` contains attributed published
  EDX proposals, not new model results or human ground truth. Do not prelabel
  Val/Test from it. Its selected IDs predate the split revision: reconcile IDs
  with the active manifest before any further proposal import.
- Training environment `pipeline/.venv/`: Python 3.12.14, torch 2.14.1,
  torchvision 0.29.1, ultralytics 8.4.185, numpy 2.5.4, direct/full lock files.
  Root `.venv/` stays Python 3.9.6 for map preparation/auditing.
- Pinned pretrained YOLO11n weights are in `data/ml/weights/`. Full 1024 px
  loss/backward on one real Train image (271 boxes) passed on MPS with finite
  gradients in 5.976 s. No optimizer step or trained weights saved.
  Batch 2/full epochs and rendering remain untested.
- `pipeline.train_detector` checks missing Val, changed labels/images, wrong
  frozen partitions, overlapping Train/Val, extra unaudited images, and weight
  identity. A fresh recorded run is created only after preflight passes.

## Exact next action

Emir: create a **separate Object Detection project** `dowser-kern-validation`
and upload **`data/ml/kern_1024_v2/annotation_import/val.zip` (15 PNGs)**.
Use the same single class `well_symbol`, native 1024 px, unchanged filenames.
A separate project avoids duplicate handling: two newly reserved Val tiles
already exist unannotated in the original project's old 84-image Train queue.
Preserve the five-image project and its labels.

Independently review whole images, box all recognizable targets, explicitly
mark empty only after confirming no targets, and leave ambiguous work unfinished.
Keep the new batch in Validation, with no random reassignment.
See [annotation instructions](ANNOTATION.md#active-validation-handoff).
**Do not use the old 13-image val.zip or label the old 79-image queue wholesale.**
Only 67 of that queue still belong to active Train; two are Val and ten buffer.
Extra Train labeling is not the immediate task.

Save the untouched YOLOv8 Validation export in `data/ml/reviewed_exports/`.
Audit with `--split val --dataset data/ml/kern_1024_v2 --output
data/ml/reviewed_validation_v1`. Reviewed negatives need explicit empty label
files; never interpret unreviewed images as negatives.
Then follow [TRAINING_PLAN.md](TRAINING_PLAN.md): preflight, five diagnostic
epochs, prediction preview, then a separately configured baseline up to 50
epochs/patience 10. If all Val is negative, only diagnostics/false positives are
assessable; recall/mAP and quality checkpoint selection are unavailable.
The full baseline requires independent positive Val examples. No random split
of the five overlapping Train images or use of protected Test for tuning.

## Verification and integration

- 33 ML tests pass: geometry/splits, proposal restrictions, Train/Val archive
  auditing including explicit negatives, split revision, training guards.
- Actual new ZIP: 15 PNGs, integrity/content checked; Test IDs and all native PNG
  identities preserved. Five-image import and both source archive hashes pass.
- Real `--check-only` exits 2, `Missing reviewed val import`, as expected.
  No training run is created. Raw probe/data identities: [EXPERIMENTS.md](EXPERIMENTS.md).
- Main through `558a00b` is incorporated. Incoming brief/evidence-URL loading,
  CalGEM layer, impact/replay and UI changes were source-inspected; see
  [main review](../MAIN_REVIEW.md). Team files are unchanged by ML. No deployment,
  external pulls, replay, Claude API generation or UI end-to-end validation.
- Kunjal works directly on main. Fetch/review incoming changes before the next
  code task or merge; PR #3 still needs team review. Preserve this checkout:
  ignored datasets, labels, weights and environments are not restored by Git.

Remaining after first training: independent Test labels/evaluation, actual-map
control points, 10+ known-well offsets, detection/fallback export, crops and Ryann
handoff. Fallback must use explicit `source=ground_truth`, numeric 1.0 and the
hand-labeled UI tag; this is not model confidence.
