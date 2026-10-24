# ML experiments

No training or evaluation run has been performed in this workspace. Do not fill
results from expectations. Add one record per meaningful run; link larger reports
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

## Run template

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
