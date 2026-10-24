# ML status and handoff

Last verified: 2026-10-24, America/Los_Angeles.
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
The v2 archive check fetched newer main `558a00b` (UI/brief/replay changes).
Those commits have not yet been inspected/incorporated; review them before the
next code/training task. This task used the unchanged, committed archive auditor.

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
`manual_5_images_v2` is the current export in `data/ml/reviewed_exports/`;
the earlier v1 ZIP/import are retained unchanged.
All filenames map to the frozen Train manifest, dimensions remain 1024×1024,
and the export JPEGs align with the source PNGs. Original PNGs are restored in
ignored `data/ml/reviewed_v2/`; both ZIPs are retained byte-for-byte.

Structural validation passed again. Two edge overflows <=0.005 px were clipped
only in the derived v2 copy and logged. All four 1954 label sets are unchanged.
On the 1992 tile, 230 boxes retain exactly the same geometry; 41 old/new boxes
remain after multiset cancellation. Geometric pairing and visual inspection show
that all 15 formerly large boxes have tighter bounds; no box now exceeds the
40 px review heuristic. `changes_review.png` shows old red/new green rectangles.
Roboflow reordered annotation rows: compare coordinates, not row positions.
Full-image completeness and independent accuracy remain unestablished;
no Dowser model trained or ran. No further redraw of this five-image batch is
currently requested; use v2 for the first training setup and retain limitations.
Emir created the Roboflow project `dowser-kern-well-symbols`; its Object Detection
type and class creation are confirmed by his screenshots. This agent has no
logged-in Roboflow access and has not uploaded images or changed cloud labels.
Preserve the original project and manual work; the identified large-box issue
has been addressed in the newly supplied export.
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
- Six annotation-audit tests pass (21 ML tests total). V1 export: 568 valid
  rows, matched frozen Train IDs, no image resizing/offset, three logged tiny
  edge-rounding corrections. Copied original PNG hashes and resulting label
  counts were independently rechecked. The large-box figure was visually inspected.
- The unchanged auditor successfully reprocessed v2: same 5 frozen Train IDs,
  568 boxes, 1024 px original-image alignment and 0 large-box flags. V1/v2 box
  coordinate multisets and all 15 before/after neighborhoods were compared.
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

Follow [TRAINING_PLAN.md](TRAINING_PLAN.md): selected baseline is pretrained
YOLO11n at imgsz 1024 on the local Apple M5 (24 GiB), using MPS. A small GPU
forward/backward and NumPy transfer passed with Python 3.12.14 / PyTorch 2.14.1
in ignored `pipeline/.venv/`. The full YOLO SDK/runner/weights are not installed
or tested yet, and no detector training has started.

Inspect pending main, finish the training environment/runner, and import reviewed
annotations for the 13 frozen Validation images before the normal training run.
Then do 5 diagnostic epochs and a baseline of up to 50 epochs with patience 10,
recording actual config, weights, timing, device and data identities. Test remains
30 protected images for final evaluation; its independent labels are also pending.
All 15 requested boundary corrections have been checked; do not ask Emir to
repeat the same corrections based on the obsolete v1 figures.

Only training labels have been supplied: validation/test directories referenced
by the exported YAML are absent. Annotate the frozen validation/test images
independently before reporting metrics; no re-splitting these five images or
using the 79 unreviewed Train images as negatives. The audit writes a YAML
template only. Model family/size is selected; weights acquisition, full-model
compatibility, validation annotations and the first run remain pending.

The assisted pilot remains available if more training examples are needed;
keep its unreviewed proposals separate from these human-drawn labels. Use future
validation errors to guide additional training examples/negatives. The symbol
count and two-era coverage targets are met; full quality acceptance and independent
evaluation remain pending. Preserve reserved test images and inference provenance
for the later handoff to Ryann.

Remaining: actual-map control points, 10+ known-well offsets, detector training,
independent evaluation, fallback export, crop publication. Main's manual fallback
now uses numeric 1.0 with a hand-labeled indicator; preserve explicit provenance.
