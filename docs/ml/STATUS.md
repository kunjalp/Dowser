# ML status and handoff

Last verified: 2026-10-23, America/Los_Angeles.
Task branch: `ml/tile-georeferencing`; includes inspected main `84335ce`.
Incoming dedup/matching/enrichment/scoring/loading, manual-fallback UI, overlay
quality option, and preservation of field decisions on reload are incorporated.
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

During export auditing, the previously pending upstream pipeline changes and
newer main through `84335ce` were inspected and merged. Team backend/frontend
and existing pipeline files are unchanged relative to that revision. Source
inspection and merge do not establish that external data pulls or deployment work.

## Source of truth and scope

[Master Plan](../master-plan/source.txt) supersedes the old PRD. Emir owns ML;
Ryann owns matching/dedup/scoring and historical overlay conversion; Kunjal owns
the UI map. Python code/config/research now live under `pipeline/`.
On 2026-10-23 the user explicitly withdrew the earlier zero-cost constraint,
saying it was written by mistake. Current root instructions reflect this:
paid resources/credits are no longer categorically banned. Record material costs.
Earlier run records stating no paid services were used remain historical facts.

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
  converter. Those team files are unchanged relative to `84335ce`.
  See [current contract](CONTRACT.md).

## Data preparation run

Active output: `data/ml/kern_1024_v1/` (ignored, reproducible locally).
Its summary/manifest contain exact artifact identities and code hashes.
Geometry pass: **189 windows; 84 train / 13 validation / 30 test / 62 buffer**.
Test is 23.6% of 127 retained images because at least 30 are required. Both
1954 and 1992 appear in each retained partition.

**Imported human-drawn labels: 5 Train images, 568 boxes**, class `well_symbol`:
297 boxes across four 1954 tiles, 271 on one 1992 tile. Version
`manual_5_images_v1` was downloaded and saved in `data/ml/reviewed_exports/`.
All filenames map to the frozen Train manifest, dimensions remain 1024×1024,
and the export JPEGs align with the source PNGs. Original PNGs are restored in
ignored `data/ml/reviewed_v1/`; the ZIP is retained byte-for-byte.

Structural validation passed. Three edge overflows <=0.005 px were clipped only
in the imported copy, with before/after values recorded. Fifteen large boxes
on the 1992 tile are flagged in `large_boxes_review.png`; inspecting them shows
excess background around the target symbols. Correct these boundaries before
treating the labels as quality-approved. Full-image completeness and independent
accuracy are not established; no Dowser model trained or ran.
Emir created the Roboflow project `dowser-kern-well-symbols`; its Object Detection
type and class creation are confirmed by his screenshots. This agent has no
logged-in Roboflow access and has not uploaded images or changed cloud labels.
Preserve the original project and manual work; inspect/fix identified boundaries.
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
- Six annotation-audit tests pass (21 ML tests total). Actual export: 568 valid
  rows, matched frozen Train IDs, no image resizing/offset, three logged tiny
  edge-rounding corrections. Copied original PNG hashes and resulting label
  counts were independently rechecked. The large-box figure was visually inspected.
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

Review `data/ml/reviewed_v1/large_boxes_review.png` (1992 export rows
11, 12, 18, 20, 23, 24, 26, 27, 30, 31, 32, 35, 36, 38, 39) and tighten loose
boundaries in the original Roboflow image `usgs_102321_x01250_y03651.png`.
Retain v1, export the revision, and re-audit into a new directory. Row numbers
refer to this export, not persistent Roboflow annotation IDs. Complete a full
label review; size flags are an aid, not an exhaustive list of possible issues.

Only training labels have been supplied: validation/test directories referenced
by the exported YAML are absent. Annotate the frozen validation/test images
independently before reporting metrics; no re-splitting these five images or
using the 79 unreviewed Train images as negatives. The audit writes a YAML
template only. Training setup/weights selection and the first run remain pending.

The assisted pilot can replace drawing every box from scratch for 1954 examples.
Preview its four train images, then review/correct them
in a separate annotation project without overwriting Emir's current work.
Retain original splits; use only fully reviewed images for training. Agree on
symbol/box policy before splitting work across helpers. Add examples from 1992
and hard negatives; the count target is met, while label-quality acceptance and
independent evaluation remain pending;
annotate reserved test images independently. Then implement YOLO training,
evaluation, and reviewed inference export for Ryann.

Remaining: actual-map control points, 10+ known-well offsets, detector training,
independent evaluation, fallback export, crop publication. Main's manual fallback
now uses numeric 1.0 with a hand-labeled indicator; preserve explicit provenance.
