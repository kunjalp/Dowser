# ML status and handoff

Last verified: 2026-10-23 (America/Los_Angeles).

## Verified state

- Repository: `https://github.com/kunjalp/Dowser`, remote `origin`, default `main`.
- Task branch: `ml/region-selection`, based on `docs/ml-workflow` at `43e437c`;
  main baseline is `15f7c8f` (initial backend commit).
- Existing backend: Convex schema, sensor ingest/readings, CalGEM loader and its
  test script. Existing Convex instructions were preserved.
- Research scripts exist under `ml/research/`; nine source raster samples and
  source-response caches are local under ignored `data/research/`.
- No Dowser detector, human-labeled dataset, trained weights, or ML accuracy
  metrics have been produced. Published model outputs are attributed reference data.
- Full PRD was read; its unchanged pasted text is retained under `docs/prd/`.
- Contract matches current detection field names and documents unresolved gaps.
- [Full main review](../MAIN_REVIEW.md) covers all 97 tracked files at
  `15f7c8f13896093935c7e3811e8b28ee10c97ccd` (55 unique content blobs).
- Main has no tile/detection ingestion API, spatial triage, automatic sensor
  confirmation/ranking, or frontend yet. Table definitions are not those features.
- Region selected for ML MVP: Oil Center + Oildale, Kern; WGS84 bbox
  `[-119.125, 35.375, -118.875, 35.5]`. See the
  [canonical config](../../ml/config/region.json) and
  [research report](../research/REGION_SELECTION.md).
- Three selected TIFFs/XML were inspected: Oil Center 293661 (1954/1968 revision),
  Oildale 293664 (1954), Oil Center 102321 (1992). Oil Center 1978 is excluded
  because it is an orthophotomap. Do not select files solely by title/year.
- The default branch was unprotected when inspected. No branch settings changed.
- Documentation is prepared on a task branch for review; team workflow proposals
  remain subject to agreement. Use Git/PR state for current publication status.

## Current task

Begin one native-resolution tile from Oil Center 293661 with collar masking and
coordinate/control-point checks. Backend still needs annotation-confidence,
evidence/provenance, and ingestion decisions before persistent ML integration.
The region research branch depends on the documentation PR; review its separate
PR against `docs/ml-workflow` until that parent is merged.

## Verification of the documentation change

- `python3 scripts/test_load_calgem.py`: all 5 existing tests passed.
- `bash -n scripts/post_reading.sh`: passed; the script was not run against a server.
- Local Markdown links resolved across the documentation files.
- `cmp` confirmed `docs/prd/source.txt` matches the supplied attachment exactly.
- Source SHA-256: `1b373501053c0437f2636a9dedb73f3e1c732a2dff2fc0062c96421e1f4e99d4`.
- `git diff --check`: no whitespace errors in the tracked diff.
- No ML training/evaluation or Convex deployment was run for this docs change.

## Region-research evidence

- USGS catalog and live CalGEM counts queried for five bounded subregions.
- Nine sampled TIFFs/XML opened; three selected raster hashes recorded in config.
- Published baseline contains 1,907 predictions, not human labels. Its five
  candidates were checked against current mapped CalGEM geometry; none has a
  record within 100 m, but visual inspection exposed uncertain/false detections.
- OSM/Overpass probes failed; current school/building proximity is not verified.
- The published U-Net weights were not downloaded/run. Switching from the PRD's
  YOLO requires an explicit requirement decision; it has not been made.

## Next executable milestone

One actual georeferenced map tile produces explicit ground-truth detections with
WGS84 coordinates and evidence crops, consumable by backend. Then train a model
against the same interface. Relevant IDs: FR-1.3, FR-2.4, FR-2.7, FR-3.1, FR-3.2.

## Decisions still needed

- Team agreement on one-review PR workflow and protection of `main`.
- Backend approval of field names, bbox convention, ground-truth confidence,
  manifest format, artifact delivery, and the tile/detection ingestion interface.
- Dataset and weight storage location; compute for training.
- Current school/building source ingestion and independent georeferencing checks.

## Handoff update template

Date / branch / commit:
Completed behavior:
Requirement IDs:
Checks actually run and evidence paths:
Known failures / blockers:
Exact next action:
