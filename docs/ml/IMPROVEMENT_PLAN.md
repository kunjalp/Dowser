# Improving baseline text/lookalike false positives

Decision/review date: 2026-10-24. Applies Master Plan section 6: complete labels,
diverse map examples, negatives with lookalikes, and held-out precision/recall.
This is a next-experiment plan, not evidence that a new model is better.

User update: Emir subsequently explicitly requested autonomous assistant annotation
and training. The first local assistant review/mix is now prepared; see current
STATUS.md. This supersedes the human-export dependency below for that experiment,
while preserving its source/provenance restrictions. Assistant annotations remain
separate from the original human labels and from human Val/Test truth.

## Evidence and working hypothesis

The baseline has 568 boxes, but only five Train images, no explicitly empty Train
images, four neighboring old-era examples and one 1992 example. The 300-symbol
Master Plan target is a minimum delivery milestone, not a guarantee of model
quality or diverse training data. Existing positive images do contain letters
and background; do not claim the model has never seen background.

`data/ml/error_review_v1/unmatched_predictions.png` shows native neighborhoods
with high-score detections unmatched to existing labels (score >=.70, maximum
IoU with any current GT <.10). Visual inspection confirms examples on O, 9, 4,
8, e, rectangular structures and contour marks. Some unmatched boxes may reflect
missing/ambiguous labels: this gallery is a diagnostic, not automatic new GT.

At .40 the baseline Val has TP48/FP215/FN1; .70 gives TP31/FP23/FN18.
Raising the cutoff already discards true wells. Limited background/context
diversity and potential annotation inconsistencies are the first hypotheses to
test. Five images also limit generalization; more epochs alone are not a reliable
fix. We have not established that model size is the main cause.

## Concrete review package

`pipeline.mine_training_batch` inferred on **55 full-content, unreviewed Train
tiles only**, excluding the five existing human Train IDs, Val/Test/buffers and
12 remaining Train tiles with valid_fraction <.95. It proposed a small batch
with moderate predicted density and disjoint coverage across editions. Selection
uses scores/counts, not OCR or proof that a tile is negative.

Current package: `data/ml/hard_negative_review_v2/`:

- `preview.html`: whole native images with toggleable, explicitly unreviewed model
  proposals. This is a labeling queue, not a new trained model's result.
- `review_train_images.zip`: **five PNGs only**, no labels/empty negatives.
- `proposals.json`: all 55 inferred Train IDs, source/image/checkpoint hashes,
  selected IDs, code identity and unreviewed status.

| Tile | Review purpose, based on visual inspection (not human GT) |
| --- | --- |
| usgs_293661_x01330_y05277 | Text, contours and urban revision patterns |
| usgs_102321_x02888_y05289 | Numbers, contour loops and sparse map features |
| usgs_293664_x03776_y03637 | OIL/COUNTY/AIRPORT lettering, reservoirs, water-tank context |
| usgs_102321_x04526_y05289 | Sparse real-looking wells mixed with contours/numbers |
| usgs_293664_x02138_y05275 | Sparse repeated symbols and text/buildings |

All five originals were visually inspected; completeness still needs human review.
Do not promise a true object count from the proposal count. Preliminary local
v1 selected one 207-prediction image; it is retained as superseded. V2 excludes
zero-proposal or >35-at-.70 cases from this small workload and returns five
rather than forcing a sixth dense image. That cap is a workload heuristic, not
proof of image completeness or a guarantee of few real wells.

For Roboflow, use a separate Object Detection additions project, e.g.
`dowser-kern-train-additions`, because these images already exist unreviewed in
the original project's old Train queue. Upload the five-image ZIP; one class
`well_symbol`; all images remain **Train**. Alternatively locate these exact IDs
in the original project without duplicate uploading. Do not label the old queue
wholesale: some of it became Val/buffer in the split revision.

Review each entire image. Label only recognizable target symbols; letters,
digits, tanks and buildings are background, not new object classes. Mark Null
only after confirming the entire tile has no target. Resolve ambiguous symbols
instead of forcing empty labels. Keep native 1024 px geometry, no preprocessing/
augmentation/random split. Export YOLOv8 ZIP into `data/ml/reviewed_exports/`.

No human labels were added by mining. No new training has run on this package.

## Next controlled experiment

1. Audit the reviewed additions against active v2 Train IDs. Check semantic
   consistency and full-image coverage, including any missed wells; preserve
   original five-image import and both source ZIPs.
2. Combine selected reviewed additions with the existing 568 boxes in a new
   versioned Train import, keeping per-image label/source provenance. The import
   combiner/new training config are pending the human export, not implemented
   training artifacts yet. Do not turn unmatched detections into negative labels.
3. Initially add a small amount of verified background, plus sparse/mixed positive
   examples, rather than letting numerous empty images dominate the tiny dataset.
   If all three background-looking tiles are confirmed empty, start with one in
   the first ablation and retain the others as reviewed Train candidates. Record
   actual positive/negative image counts and per-era instances.
4. Keep model family, native imgsz, optimizer, augmentation policy and original
   pretrained start unchanged first; freeze the same 15-image Val/30-image Test
   membership. Record epochs, actual optimizer updates and time. Compare both
   models at fixed .70/IoU .50 and with the same Val-only F1 threshold-selection
   procedure. Record TP/FP/FN and examples, not only a favorable percentage.
5. Look for fewer text/lookalike FP without a large loss of recall; target remains
   P/R >=.60, with actual failures reported. Improvement is unproven until this
   comparison. Only then consider a separate conservative augmentation or larger
   YOLO11s experiment, changing one major factor at a time.

Validation remains tuning data. Never move its 11 negatives into Train to get a
better apparent score. Test stays untouched; broad 1992 recall still cannot be
measured because current Val has no positive 1992 labels. An OCR blanket removal
rule could discard wells near labels and is not the first fix.

## Primary references checked

- [Ultralytics training-data guidance](https://docs.ultralytics.com/yolov5/tutorials/tips-for-best-training-results/):
  diversity, complete/consistent labels, split discipline and background examples
  for reducing false positives. This is a general YOLOv5 guide, not a guarantee
  for our YOLO11 detector. Its background-ratio advice is a starting heuristic,
  not a hard requirement or a reason to invent empty annotations.
- [Ultralytics fine-tuning guide](https://docs.ultralytics.com/guides/finetuning-guide/):
  pretrained feature transfer and data requirements; current examples use newer
  architectures, while our pinned SDK/model stay unchanged for the next ablation.
