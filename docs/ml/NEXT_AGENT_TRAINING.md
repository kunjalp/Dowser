# Next agent: repair training while Test labels arrive

Handoff: 2026-10-24. Work in `/Users/emirtg/Desktop/dowser-cursor`, branch
`ml/cursor-improvements`. User forbids modifying `/Users/emirtg/Desktop/dowser`.
Preserve dirty changes, datasets, environments, archives and pins. Read root and
pipeline AGENTS, CONTRIBUTING, docs/CONTINUE.md, STATUS.md, REQUIREMENTS.md,
CONTRACT.md, ROLLOUT_REPAIR.md and FINAL_TEST.md. Master Plan sections 3/6 require
native 1024 detection, lookalike negatives, frozen splits and held-out metrics.

## Current outcome

Delivered detector: `cursor_translate_mps`, config
`pipeline/config/inference_cursor_translate.json`, imgsz 1024, confidence .71,
NMS .70, max_det 1000. Weights:
`data/ml/runs/cursor_translate_mps/training/weights/best.pt`, SHA-256
`d417cf36430485eb534fd1197be6cf15b4cad11c967083654fc3388e5a226b2e`.
Human Val: TP46 / FP4 / FN3, P .92 / R .9388 / F1 .9293. This is repeatedly
tuned Val, not Test. All 49 positives are on four overlapping Oildale 1954
tiles; 1992 Val frames are negative-only. Other seeds were unstable.

Ryann used our unchanged 3,116-row CSV. Downstream reproduction: 1,657 dedup
groups, 64 unmatched candidates; human review confirms 62 false symbols.
Overall Val precision / CalGEM proximity is not post-matching candidate quality.
Canonical `inference_selected.json` still pins data_v2 at .24; neither pin nor
the delivered archives was replaced.

Three `kern_rollout_repair_{control,hardneg,pretrained}_v1` YOLO fits were worse
and rejected. Experimental `kern_symbol_verifier_v3` gives Val 46/2/3 at YOLO
.71 + verifier .059, but leaves 22 known false groups among 24 unmatched
candidates. Config `inference_symbol_verifier_v3.json` is explicitly not
promoted. It needs a separate verifier checkpoint and crop processing; old
best.pt alone does not include it. Last recorded software checks: 67 passing
tests. No independent Test measurement has been performed.

## Authorized next training work

1. Preserve `data/ml/kern_1024_v2/manifest.jsonl`, human Train `reviewed_v2`,
   human Val `reviewed_validation_v1`, and all frozen split IDs.
2. Read `data/ml/rollout_diagnosis_v1/train_error_sources_human_confirmed.json`:
   24 Train frames, 20 needing full annotations, two with existing full labels,
   two new assistant-reviewed negatives. Human feedback is in
   `ryann_confirmed_false_reviews.json` / `.csv` in the same directory:
   58 false Train crops / four false Val crops. Do not fit on Val cases.
3. Review native Train images, annotate every true target, and retain buildings,
   text, filled tanks, blue water wells and dotted landmarks as background.
   A false crop does not imply an empty source tile. Especially
   `usgs_293664_x03776_y05275` contains real circles and many false buildings.
   Preserve human labels. Create new annotation/mix versions; assistant labels
   need provenance and `human_verified=false`. Unknown images must not become
   empty negatives. Do not reuse Cursor's separate additions with two known
   label errors until fixed in a new version (CODEX_REVIEW.md).
4. Root `.venv` is for audit/data/geo; `pipeline/.venv` is for local MPS/Torch.
   Follow existing SDK initialization, configs and mixed-supervision opt-in.
   Run `pipeline.train_detector --check-only` before training; do not reinstall
   environments. Use new configs/run directories and record actual input,
   model and code hashes, optimizer steps, duration and settings.
5. Train and compare against Cursor using unchanged human Val, native 1024 /
   IoU .50. Record thresholds, TP/FP/FN, precision/recall, errors and map/era
   coverage. Evaluate after dedup/CalGEM too. The 62 feedback cases are regression
   checks, not independent accuracy. Reject solutions that remove true wells
   just to reduce candidate counts.
6. Produce side-by-side previews and evidence before proposing promotion. Keep
   reference pins until review. Coordinate CSV/crop contract changes with Ryann;
   do not deploy or change field statuses. Update STATUS.md, EXPERIMENTS.md and
   affected docs with outcomes and next action. Continue authorized preparation,
   annotation and training without repeated permission for routine steps.

## Test export and evaluation rules

Screenshot: 12 of 30 Test tiles annotated. No Test ZIP has arrived locally.
Intake: `data/ml/reviewed_exports/test_emir_v1/` and `test_teammate_v1/`.
Keep ZIPs unchanged. Export 100% Test, YOLOv8, native 1024, no preprocessing or
augmentation. Reviewed negatives need explicit empty labels; unknown images
are not negatives.

Use `pipeline.audit_annotations --split test` for separate partial imports into
fresh output folders. Merge by original tile ID, reject conflicting duplicate
labels, and require all 30 unique frozen IDs for the final report. The custom
15-image assignment overlaps the earlier half ZIP. Structural audit alone is
not semantic certification. Retain native source images and use the existing
audited matching/reconstruction flow if Roboflow recompresses export images.

Never use Test images/labels/predictions for training, mining, selecting epochs
or tuning cutoffs. Final-Test evaluation and partial-import merge entry points
are still pending. Current preview helpers exclude Test; do not rename Test to
Val to bypass guards. Existing
`pipeline/config/final_test_cursor_translate_v1.json` freezes the old detector.
For a repaired pipeline, freeze a separate explicit protocol before its first
Test inference; preserve the original protocol. Keep Test labeling blind to
predictions. Evaluate only after complete labels and fixed model/settings.
If Test results guide changes, later results on it cannot support a fresh
independent claim.
