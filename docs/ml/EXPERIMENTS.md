# ML experiments

No training or evaluation run has been performed in this workspace. Do not fill
results from expectations. Add one record per meaningful run; link larger reports
and artifacts instead of committing generated directories.

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
