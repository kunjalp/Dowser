# ML status and handoff

Last verified: 2026-10-23, America/Los_Angeles.
Task branch: `ml/tile-georeferencing`; includes reviewed main `7f04aad`
(`.gitignore` additions only since the `f7e5eeb` implementation review).
For a new editor/AI session, use [continuation instructions](../CONTINUE.md).

## Integration handoff

Kunjal currently works directly on main, per Emir. ML work stays in the separate
task branch. [Draft PR #3](https://github.com/kunjalp/Dowser/pull/3) is the current
proposal into main and includes all work from earlier drafts #1 and #2. Those
older drafts are superseded; retain their branches/history and do not merge them
separately. No PR has been merged by the ML agent.

Fetch and incorporate incoming main changes again immediately before any merge,
review the actual diff with the relevant teammates, and recheck affected behavior.
The suggested PR-only team workflow is not yet an enforced rule for Kunjal.

## Source of truth and scope

[Master Plan](../master-plan/source.txt) supersedes the old PRD. Emir owns ML;
Ryann owns matching/dedup/scoring and historical overlay conversion; Kunjal owns
the UI map. Python code/config/research now live under `pipeline/`.
The user's zero-cost constraint is recorded in root agent instructions.

## Verified behavior

- Three pinned Kern rasters: Oil Center 293661 (base 1954, revised 1968,
  imprint 1970), Oildale 293664 (1954, imprint 1956), Oil Center 102321 (1992,
  edit/imprint 1995). The 1978 orthophotomap is excluded.
- `pipeline.download_sources` verifies hashes and acquires a pinned public
  NADCON grid; processing then runs offline.
- `pipeline.prepare_dataset` creates native 1024 px PNGs, 819 px stride,
  collar masks, transforms, source/date provenance, and backend-compatible tile
  rows. Geographic boundaries are shared across years.
- Crossing tiles are excluded as buffer; cross-split envelope overlap is checked
  explicitly. Every retained tile starts `unlabeled`.
- A validation set exists; at least 30 tiles are protected for test.
- Import ZIPs contain images only; no fabricated negative/ground-truth labels.
- `pipeline.geo` converts xywh centers to WGS84 and preserves rotation/shear.
  Numerical checks are not field-accuracy measurements.
- `pipeline.propose_annotations` creates a separate train-only review pilot
  from attributed published EDX point outputs. Four 1954 images have 973
  unreviewed box proposals representing 889 distinct published point IDs.
  `data/ml/proposals_pilot_v2/preview.html` toggles boxes; a separate Roboflow
  import ZIP is available. Box sizes are heuristic; not ground truth or new
  Dowser model inference. No validation/test tiles are prelabelled.
- Backend changes were merged from main. Current schema includes `mapYear`,
  optional `cropUrl`, candidate loading, field status changes, and pairing.
  Main now also contains auto-confirmation, Command Map/Field View, and an overlay
  converter. Those team files are unchanged relative to `f7e5eeb`.
  See [current contract](CONTRACT.md).

## Data preparation run

Active output: `data/ml/kern_1024_v1/` (ignored, reproducible locally).
Its summary/manifest contain exact artifact identities and code hashes.
Geometry pass: **189 windows; 84 train / 13 validation / 30 test / 62 buffer**.
Test is 23.6% of 127 retained images because at least 30 are required. Both
1954 and 1992 appear in each retained partition.

**Latest verified local human labels: 0 tiles, 0 boxes.** Remote annotation
progress is not verified. No Dowser model trained or ran.
Emir created the Roboflow project `dowser-kern-well-symbols`; its Object Detection
type is confirmed by his screenshot. Class creation and annotation have not yet
been verified. This agent has no logged-in Roboflow access and has not uploaded
images. Local import archives are ready; human annotation remains next.
No precision/recall or known-well accuracy is claimed. Published outputs remain
attributed research, not labels. An earlier local `data/ml/labeling_v1/` run is
preliminary; use the active path above.

## Verification

- 11 offline unit tests cover independent synthetic projection references,
  pixel-edge convention, rotation/shear, invalid boxes, deterministic splits,
  cross-year leakage rejection, minimum test size, and overwrite refusal.
- Four additional proposal tests pass (15 ML tests total): exact-source
  restrictions, held-out rejection, projection/clipping, distance semantics,
  and deterministic selection. All 973 normalized boxes, four unchanged source
  images, and import ZIP integrity were checked; original dataset remains unlabeled.
- All 127 PNG dimensions/modes and all three ZIP contents verified. Frozen
  counts, manifest hash, environment, and transform limitations are in the
  [preparation record](EXPERIMENTS.md#preparation-kern_1024_v1--2026-10-23).
- Actual source-corner residual is in summary; initial maximum approximately
  `2.33e-10` pixels. Cross-split overlap pairs: zero.
- Five existing loader checks pass: `python3 pipeline/test_load_calgem.py`.
- Backend behavior was not deployed or exercised by this ML task. Its generated
  files now exist in main, but local Node dependencies are not installed; backend
  and frontend test/build checks were not run for this Python-only change.

## Next action

Follow [ANNOTATION.md](ANNOTATION.md): the assisted pilot can replace drawing
every box from scratch. Preview its four train images, then review/correct them
in a separate annotation project without overwriting Emir's current work.
Retain original splits; use only fully reviewed images for training. Agree on
symbol/box policy before splitting work across helpers. Add examples from 1992
and hard negatives; reach 300+ human-reviewed symbols, reporting train counts;
annotate reserved test images independently. Then implement YOLO training,
evaluation, and reviewed inference export for Ryann.

Remaining: actual-map control points, 10+ known-well offsets, fallback confidence
semantics, crop publication. Ryann's OSM ingestion is not an ML blocker.
