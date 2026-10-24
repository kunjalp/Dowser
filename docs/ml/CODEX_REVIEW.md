# Independent review of Cursor's ML results

Reviewed on 2026-10-24, America/Los_Angeles, at commit
`0d476cf24d7b37110c4a5905f6312e596371c5a7`, branch
`ml/cursor-improvements`, checkout `/Users/emirtg/Desktop/dowser-cursor`.
The original `/Users/emirtg/Desktop/dowser` checkout was not modified.
This review does not promote a model or merge a branch.

## Verdict

The best candidate's reported predictions and numerical improvement are real
and reproducible. Fresh MPS inference on the same 15 human-Val images reproduced
every native box and score exactly for data_v2 and all three translate seeds.
The translate seed-42 candidate is suitable for the next controlled evaluation
and geographic integration trial. Its F1 .9293 is a repeatedly tuned Validation
result, not independent Test accuracy or proof of reliable performance on new maps.

Two concrete errors were found in Cursor's additional assistant annotations.
Those additions are absent from the winning candidate's Train import, so they
do not invalidate its measured result. Correct and version those annotations
before using the new Cursor mixes again; do not silently edit the old artifacts.

## Findings

### P2: additional assistant labels contain a wrong positive and a missed symbol

In `data/ml/cursor_assistant_review_v1/annotations.json`, image
`usgs_102321_x03707_y05289`, annotation 17 / proposal `M29` has box
`x=904.384, y=303.371, w=14, h=14`. Its center `(911.384, 310.371)` is a
solid black circle, contradicting the stated hollow-circle-only policy and the
report's claim that filled marks were rejected. This is not an ambiguous faded
hollow circle in the enlarged source pixels.

On `usgs_102321_x04526_y04470`, an unmistakable hollow circle at approximately
`(139, 583)` has no annotation. The neighboring circle around `(103, 576)` is
labeled, so one box does not cover both. A missing positive inside an otherwise
fully labeled detection image becomes background supervision.

Evidence: [raw pixels and Cursor boxes](../../data/ml/codex_review_cursor_v1/annotation_findings.png),
[coordinates](../../data/ml/codex_review_cursor_v1/annotation_findings.json).
All 43 added positive boxes, the five full overlays and the remaining-error
gallery were inspected; this is an assistant visual review, not independent
human certification of the complete new annotation set.

The wrong positive propagates into `train_mixed_cursor_v1` and
`train_mixed_cursor_v2`. The missed symbol is also in those two imports.
`train_mixed_cursor_v3` includes only the new 1954 positive tile, not these
two 1992 additions. Crucially, `cursor_translate_mps` uses the unchanged
`train_mixed_v1`, not any `train_mixed_cursor_*` import.

### P2: the seed results do not establish a robust recipe improvement

| Recipe / seed | Selected cutoff | TP / FP / FN | Precision | Recall | F1 |
| --- | ---: | --- | ---: | ---: | ---: |
| data_v2 / 42, reference | .24 | 44 / 17 / 5 | .7213 | .8980 | .8000 |
| translate=.1 / 42 | .71 | 46 / 4 / 3 | .9200 | .9388 | .9293 |
| translate=.1 / 43 | .58 | 43 / 14 / 6 | .7544 | .8776 | .8113 |
| translate=.1 / 7 | .95 | 38 / 164 / 11 | .1881 | .7755 | .3028 |

Each cutoff was selected on the same Val F1 sweep, not on Test. All counts above
were independently recomputed and reproduced by fresh inference.
"Two of three beat the reference" describes these artifacts correctly, but the
reference has only seed 42. Matched reference runs for 43 and 7 would be needed
to attribute stability differences to translation. The failed seed must remain
in the record. Seed 7 completed 12 epochs / 48 updates; "stopped immediately"
in CURSOR_RESULTS.md should read "early-stopped after 12 epochs, best epoch 2."

The best run is a useful fixed checkpoint; a poor other seed does not change its
bytes. Conversely, its good score does not guarantee that retraining the recipe
will reliably reproduce the gain. Full training was not repeated in this review.

### P2: evaluation coverage is narrow and heavily reused

The 15 Val images comprise 11 from 1954 and four from 1992. The 49 positive
instances occur on four overlapping 1954 Oildale strips; they are not necessarily
49 distinct geographic wells. Eleven Val images are reviewed negatives. All four
1992 images are negative, so 1992 recall cannot be measured. The sentence
"15 overlapping 1954 tiles" in CURSOR_RESULTS.md is inaccurate.

At .71 the new candidate has zero FP on those four 1992 negatives, as claimed.
Its four remaining FP look like squares/structures, and its three FN are hollow
marks near canal features. The observed `399`/`460` false alarms are gone on
this Val slice; that does not establish the absence of text errors on other maps.

Choosing checkpoints, recipes, seeds and thresholds repeatedly on this same
small Val set introduces selection optimism. Preserve the final 30 Test IDs and
freeze the chosen model/cutoff before an independent evaluation. Do not present
92% precision / 93.9% recall as final Test or region-wide accuracy.

### P3: copy-paste and erasing were ineffective controls, not failed active methods

In the installed Ultralytics 8.4.185 source, `CopyPaste.__call__` returns unchanged
labels when instance segments are empty. These data contain detection boxes,
not segmentation masks. That is the direct reason this copy-paste experiment
does nothing; `mosaic=0` is not the general explanation.
See local `ultralytics/data/augment.py:1982` in `pipeline/.venv/`.

`erasing` is used by the classification augmentation function, not the detection
transform chain (`augment.py:2871` and `:3064`). Changing it here does not test
an active detection augmentation. Their identical native counts are consistent
with these no-ops; they should not be cited as evidence that working copy-paste
or image erasing cannot help this task.

## Verified claims and boundaries

- All supplied frozen manifest / human Train audit / human Val audit hashes,
  candidate and reference checkpoint hashes match. In total 36 explicitly
  claimed artifact hashes were checked, including the per-run results table.
  Original reference prediction and threshold-selection bytes also match the
  preserved handoff identities, despite the disclosed earlier helper overwrite.
- Selected pin `inference_selected.json` remains byte-identical to the handoff
  version: data_v2 at .24. The separate candidate pin has the correct checkpoint
  hash, manifest, .71 cutoff, 1024 input, .7 NMS and max_det=1000.
- Candidate config, recorded run config, actual SDK args and checkpoint training
  args agree. Apart from purpose and output/input-path relocation, the only
  training-parameter difference from data_v2 is `translate: 0 -> 0.1`.
  Architecture is the same 2,604,883-parameter single-class detector, seed 42,
  same pretrained-weight hash and 8-image / 617-box Train import.
- Translation randomly shifts Train images by up to 10% of width/height while
  transforming labels. It does not add new manually labeled source images.
  The best run completed 34 epochs / 136 updates / recorded 80.904 s, compared
  with reference 24 / 96 / 52.689 s. Early stopping therefore changes actual
  compute; this is not an equal-update causal experiment.
- All 12 Cursor training configs pass the existing integrity preflight. The
  five original human PNGs and label files are byte-identical in every mixed
  import. Native label geometry matches each audit, provenance remains explicit,
  and no assistant labels were promoted to human Validation ground truth.
- Frozen split counts are 72 Train / 15 Val / 30 Test / 72 buffer. Checking all
  manifest envelopes found zero overlap across Train/Val/Test. No Test label
  files were found in the versioned local import label folders. No Test images
  were opened by this review. The recorded configs/predictions exclude Test;
  static artifacts cannot prove the absence of every historical manual access.
- Independently implemented confidence-first one-to-one IoU=.50 matching and
  .05..95 / .01 F1 sweep agree for all 13 comparable saved prediction sets
  (reference plus 12 MPS Cursor runs). All 20 saved fixed-cutoff evaluation
  reports agree numerically. Failed runs were retained, not omitted.
- Candidate .70 gives TP46 / FP5 / FN3, F1 .9200, as claimed. Reference .70
  gives TP0 / FP0 / FN49. Compare each selected operating point as well:
  model scores are not calibrated probabilities or interchangeable cutoffs.
- Fresh MPS inference on all 15 Val images reproduced exact boxes/scores for
  reference, candidate, seed 43 and seed 7. This independently connects the
  current weight files to the claimed metrics instead of trusting saved JSON.
- All 54 ML tests pass. Python implementation and evaluation code have no diff
  from the Cursor handoff; changes at the reviewed commit are docs and configs.
  Training records disclose dirty working trees. They retain config snapshots,
  but not complete dirty source patches; full training provenance is less strong
  than a clean committed run. Fresh inference verifies the delivered checkpoints.
- Review is local; no training, deployment, external API calls, model adoption,
  main merge or geographic candidate load was performed. One SDK metadata
  unpickle created default global settings; that new file was removed afterward.

## Review evidence and next action

Review script and receipts are local ignored artifacts under
`data/ml/codex_review_cursor_v1/`:

- `audit.py`: independent matcher, hash/data checks, preflights and fresh inference.
- `static_audit.json`: per-run counts, cutoffs, hashes, versions and integrity checks.
- `fresh_inference.json` and `*_fresh_predictions.json`: repeated native predictions.
- `additional_checks.json`, `annotation_findings.json` / `.png`, and
  `all_43_cursor_positive_labels.png`: supplementary checks and visual evidence.

The script refuses to overwrite its JSON receipts. To repeat it, preserve this
receipt directory and use a fresh output directory; do not overwrite the Cursor
or reference previews. Run tests with
`.venv/bin/python -m unittest discover -s pipeline/tests -q`.
Artifacts are not stored in Git; transfer them and the named checkpoint if
resuming on another machine. This Markdown report is the durable review summary.

Recommend freezing `cursor_translate_mps` / .71 as the candidate for independent
Test evaluation and a geographic smoke test, retaining data_v2 as the reference.
Have an independent reviewer label the protected Test set without predictions;
evaluate the frozen checkpoint once and report era coverage. Correct the new
assistant annotations in a new version before any further data experiment.
Do not spend the remaining integration window on an open-ended Val search.

The Master Plan's next ML deliverable remains native detection boxes plus real
coordinates, source year, confidence and evidence crops for Ryann. Verify actual
map control points and 10+ known CalGEM offsets before claiming geographic
accuracy. Neither this review nor a high Val F1 completes that handoff.
