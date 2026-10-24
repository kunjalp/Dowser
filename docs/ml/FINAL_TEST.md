# Final Test: frozen protocol and annotation handoff

Prepared 2026-10-24 in `/Users/emirtg/Desktop/dowser-cursor`. No model Test
inference was performed. Human imports now cover 27/30 unique Test images
(725 boxes, three explicit negatives), without conflicts. Original checkout,
canonical data_v2 pin and frozen split IDs remain unchanged. Master Plan
sections 3/6: reserve at least 30 Test tiles before training and report actual
precision/recall with checked map/era coverage.

Coverage-only verification on 2026-10-24 still requires human labels for
`usgs_293661_x02149_y01182`, `usgs_293661_x04606_y00363`, and
`usgs_293664_x04595_y00361`. Imports are `data/ml/reviewed_test_emir_v1` and
`data/ml/reviewed_test_teammate_v1`. Structural validity is not semantic approval.
The frozen-protocol evaluator is implemented in `pipeline/evaluate_final_test.py`.
Current model/release decision and integration plan:
[INTEGRATION_QUALITY_PLAN.md](../INTEGRATION_QUALITY_PLAN.md).

## Ready files

- `data/ml/final_test_cursor_v1/test_images.zip`: 30 original native PNGs,
  no labels/predictions, 59,135,745 bytes. SHA-256
  `b6440e90621a8be4f5c8fb63dd530dc1f6d1cdfdd367be0db1f5b7f94cf15d86`.
- `pipeline/config/final_test_cursor_translate_v1.json`: checkpoint/settings,
  manifest/image hashes, exact 30 IDs, annotation requirements and scoring rules.
- Local `README.txt` / `SHA256SUMS` beside the ZIP.

### Annotation work assigned to a teammate

At Emir's request, `/Users/emirtg/Desktop/Dowser_Test_second_half_16-30.zip`
contains only the 15 PNGs at positions **16–30 in the original ZIP member order**,
without re-sorting names. It starts with `usgs_293664_x02957_y00361.png` and ends
with `usgs_102321_x05345_y01194.png`. This is a work assignment, not a new dataset
partition: all images remain Test. Emir can label the original first 15 images.

The original 30-image ZIP is unchanged (same SHA above). All 15 output image
bytes and ZIP CRCs were verified. Full membership for both halves is recorded in
`data/ml/final_test_cursor_v1/second_half_16-30_receipt.json`. Preserve original
filenames when the two human annotation exports are combined; do not use an
annotation UI's display order to reconstruct this ZIP-based assignment.

Emir later requested a custom ZIP from 15 screenshot filenames:
`/Users/emirtg/Desktop/Dowser_Test_selected_15.zip` (26,785,177 bytes). It contains
exactly those original PNGs, in screenshot order, with no additional files.
Membership/hash receipt:
`data/ml/final_test_cursor_v1/selected_15_screenshots_receipt.json`.
This custom set overlaps the earlier halves; do not assume it is the complement
of the earlier teammate ZIP. Combine annotation exports by original tile IDs.
All earlier archives, including the full 30-image Test ZIP, remain unchanged.

The old v1 Test ZIP was checked against every current v2 Test PNG and copied
unchanged. All 30 IDs/file hashes match the active manifest. Test has 19 images
dated 1954 (Oil Center 12, Oildale 7) and 11 Oil Center 1992 images. Positive
symbol counts are unknown until review. No semantic inspection or model output
was used to select images during this preparation.

## Human annotation needed

The earlier Emir screenshot showed **12 annotated / 18 unannotated** in the original
30-image job. A partial export is allowed. In "Add Images to Dataset", choose
**Add All Images to Testing Set**, rather than the displayed 70/20/10 split.
Unannotated images remain pending; do not mark them negative to finish a batch.
Create `manual_test_emir_partial_v1` with no preprocessing (remove Resize and
Auto-Orient) or augmentation. Export YOLOv8 / "Download zip to computer".

Prepared intake folders are `data/ml/reviewed_exports/test_emir_v1/` and
`data/ml/reviewed_exports/test_teammate_v1/`. Keep downloaded ZIPs unchanged.
Two incoming archives have since been imported; no model Test was evaluated. Reconcile original
tile IDs: the custom 15-image assignment overlaps both original halves, so
adding batch counts does not establish coverage. Require all 30 unique Test
IDs and resolve duplicate-label disagreements before final evaluation.
These exports are evaluation-only; training repair uses separate frozen Train
IDs. See [the next-agent brief](NEXT_AGENT_TRAINING.md).

For the teammate's 15-image website workflow, use the English
[click-by-click Roboflow tutorial](TEAMMATE_LABELING.md), including export steps.

Use a separate Object Detection project, such as `dowser-kern-test`. Upload the
ZIP; one class `well_symbol`, same hollow oil/gas symbol policy as Train/Val.
Follow the [annotation guide](ANNOTATION.md). Review each whole image and draw
tight per-symbol boxes. Do not use AI/model pre-labeling or look at predictions.
Emir or teammates can label; splitting work among people does not change the
dataset partition. A second human review is preferable.

Negative images require full review confirming no targets; retain an explicit
empty TXT in the export. Keep all 30 in Test, original names and 1024 px geometry.
No resize, augmentation or random redistribution. Export YOLOv8 ZIP with all
30 images and matching TXT files, including reviewed negatives. Preserve the
archive under `data/ml/reviewed_exports/`; do not overwrite earlier exports.
Label counts/format checks alone do not certify semantic quality.

## Frozen evaluation decision

Candidate `cursor_translate_mps`, SHA
`d417cf36430485eb534fd1197be6cf15b4cad11c967083654fc3388e5a226b2e`.
Confidence .71, NMS .70, input 1024, max_det 1000, MPS/batch 2. Match IoU .50,
descending-confidence one-to-one native matching per tile; no geographic dedup.
Report aggregate/per-era TP, FP, FN, precision, recall, F1, FP on reviewed
negatives, representative errors and timed inference with hardware/timing scope.
Recall is undefined for a slice with no positive GT.

Do not tune thresholds/checkpoints/training/GT using Test results. A changed
model measured on an already inspected Test no longer has a fresh independent
claim. Preserve the failed cases in the fixed model's report.

## Remaining work after the human ZIP arrives

1. Import with the existing Test-capable auditor:

   ```sh
   .venv/bin/python -m pipeline.audit_annotations \
     data/ml/reviewed_exports/TEST_EXPORT.yolov8.zip \
     --dataset data/ml/kern_1024_v2 --split test \
     --output data/ml/reviewed_test_v1
   ```

2. Verify all 30 IDs, original hashes, label geometry, explicit negative decisions
   and human annotation attestation. Review labels without predictions.
3. Use the implemented `pipeline.evaluate_final_test` entry point governed by
   the frozen protocol. Current preview/evaluate helpers intentionally admit
   only Train/Val; do not rename Test to Val to bypass them. The final evaluator
   rejects missing/extra IDs, assistant GT and changed model/settings. Keep the
   old model protocol; freeze a separate one for the chosen repaired pipeline
   before its first Test inference. Two-stage verifier protocols are unsupported.
4. Run the fixed checkpoint on Test and issue the final measured report.

Partial imports and the evaluator are complete. Three human labels, semantic
completeness review, final model/protocol selection and the measured report
remain pending. Training repair proceeds independently on Train; these Test
labels must not be used to improve the model.

## Update: repair_v2 candidate protocol and intake (2026-10-24)

A second, separate protocol freezes the selected repair_v2 candidate before
any of its Test inference: `pipeline/config/final_test_repair_v2_e4_mixed_s42.json`
(`kern_e4_mixed_s42`, cutoff .67, NMS .70, 1024, max_det 1000; same 30 IDs,
annotation and scoring rules copied from v1). The v1 protocol is unchanged.

Intake: `reviewed_test_emir_v1` (12 images / 407 boxes) and
`reviewed_test_teammate_v1` (15 / 318, three empty) are structurally audited,
27/30 unique, no overlap. Missing: `usgs_293661_x02149_y01182`,
`usgs_293661_x04606_y00363`, `usgs_293664_x04595_y00361`.

`pipeline/evaluate_final_test.py` is the Test entry point: `--coverage-only`
validates protocol and imports without inference; the full run requires all
30 tiles, identical duplicates only, human-only labels, unchanged pixels and
checkpoint, and a written `--attestation`; it has no cutoff option or sweep and
refuses to overwrite its output. Evaluate each protocol at most once.

## Interpretation

The result measures this checkpoint on these 30 tiles. Overlapping instances
are not independent geographic wells; retain coverage/era limitations and raw
counts. It does not guarantee accuracy on every new map, establish surviving
wells/undocumented status or verify leaks. Passing software tests are
separate from this model-quality evaluation.
