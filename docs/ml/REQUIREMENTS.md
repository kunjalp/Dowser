# ML requirements and acceptance evidence

Baseline: [full PRD](../prd/source.txt), 2026-10-23. All implementation statuses
below are `not started`; this file describes acceptance, not delivered behavior.
Replace status and add evidence paths/commands when work is verified.

| PRD ID | Acceptance to preserve | Expected evidence |
| --- | --- | --- |
| FR-1.1 | One region and bounding box | Repository README/config |
| FR-1.2 | At least 3 georeferenced sheets across at least 2 eras | Source manifest and local artifact references |
| FR-1.3 | Fixed-size overlapping tiles; per-tile transform; corner reconstruction within 1 pixel | Manifest and transform checks |
| FR-1.4 | Upload/CLI to stored detections under 30 s on demo hardware | Timed integration run with backend |
| FR-1.5 | Raw sheets outside Git; repo under 100 MB | Ignore rules and repo size evidence |
| FR-2.1 | Labels from at least 2 eras, target at least 300 boxes, YOLO export | Dataset version, counts, labeling guide |
| FR-2.2 | About 20% labeled tiles held out, never trained on | Versioned split manifest, group assignment, overlap check |
| FR-2.3 | Fine-tune pretrained YOLO; save weights and commit config | Run record, config, weights URI/checksum |
| FR-2.4 | Box, confidence, class, source tile ID per detection | Agreed contract and serialized fixture |
| FR-2.5 | Actual precision/recall and confusion examples on validation | Evaluation report with maps/eras and metric protocol |
| FR-2.6 | Document threshold selected on validation PR curve | Curve/report and inference config |
| FR-2.7 | Config switch from inference to labeled ground truth | Both paths produce agreed records with explicit provenance |
| FR-3.1 | Tile ID and box center to WGS84 lat/lon | Coordinate function and checks |
| FR-3.2 | Correct CRS handling; at least 3 known control points | Independent reference coordinates and error report |
| FR-3.3 | At least 10 detections checked against CalGEM; median offset reported, target under 50 m | Match table with sample selection and offsets |
| FR-3.4 | Merge adjacent-tile duplicates within about 15 m | Dedup check; configurable distance; retained evidence |

PRD metrics are targets: precision and recall aim at 0.60+; report actual values,
map coverage, and sample counts even when targets are missed. CalGEM offsets
combine map, detection, and record-location error; do not claim they independently
prove absolute georeferencing accuracy.

## Evaluation policy (engineering proposal)

Assign splits by geographic/source groups before augmentation; overlapping tiles
and overlapping multi-year coverage must not cross splits. Approximately 20% of
tiles is a target, not a reason to violate grouping. Record deviations caused by
a small number of sheets. Three sheets may give unstable estimates; state that.

Record IoU/matching rule, confidence threshold, one-to-one matching, duplicate
handling, sample counts, and metrics per era. A validation set used for threshold
selection is a tuning set. Use a separate untouched test set if possible; otherwise
explicitly report validation results and their limitation.

## Open PRD issues / deviations

- No approved ML deviations yet. Restricting to one era requires an explicit
  scope decision: FR-1.2 and FR-2.1 currently call for at least two.
- Ranking formula is missing from the pasted PRD following its introduction.
  Backend must resolve this; ML confidence must retain its original meaning.
- Sensor confirmation wording and MQ-4 measurement limits need alignment by the
  hardware/backend owners. Model detections alone confirm neither wells nor leaks.
- Factory Droid/Apify track requirements are conditional on pursuing those tracks;
  do not silently mark their P0 requirements complete if a track is dropped.

For each future deviation record: date, affected IDs, reason, decision owner,
replacement acceptance criteria, and evidence. Do not rewrite the PRD silently.
