# ML status and handoff

Last verified: 2026-10-23 (America/Los_Angeles).

## Verified state

- Repository: `https://github.com/kunjalp/Dowser`, remote `origin`, default `main`.
- Task branch: `docs/ml-workflow`, based on `15f7c8f` (initial backend commit).
- Existing backend: Convex schema, sensor ingest/readings, CalGEM loader and its
  test script. Existing Convex instructions were preserved.
- No ML implementation, dataset, trained model, or ML metrics have been produced.
- Full PRD was read; its unchanged pasted text is retained under `docs/prd/`.
- Contract matches current detection field names and documents unresolved gaps.
- The default branch was unprotected when inspected. No branch settings changed.
- Documentation is prepared on a task branch for review; team workflow proposals
  remain subject to agreement. Use Git/PR state for current publication status.

## Current task

Review the documentation PR with the team. Backend should resolve annotation
confidence and the evidence/provenance delivery boundary before implementing
persistent ML output. Begin region/sheet inspection independently of that choice.

## Verification of the documentation change

- `python3 scripts/test_load_calgem.py`: all 5 existing tests passed.
- Local Markdown links resolved across the documentation files.
- `cmp` confirmed `docs/prd/source.txt` matches the supplied attachment exactly.
- Source SHA-256: `1b373501053c0437f2636a9dedb73f3e1c732a2dff2fc0062c96421e1f4e99d4`.
- `git diff --check`: no whitespace errors in the tracked diff.
- No ML training/evaluation or Convex deployment was run for this docs change.

## Next executable milestone

One actual georeferenced map tile produces explicit ground-truth detections with
WGS84 coordinates and evidence crops, consumable by backend. Then train a model
against the same interface. Relevant IDs: FR-1.3, FR-2.4, FR-2.7, FR-3.1, FR-3.2.

## Decisions still needed

- Team agreement on one-review PR workflow and protection of `main`.
- Region/bounding box and sheets/years, selected after inspecting real maps.
- Backend approval of field names, bbox convention, ground-truth confidence,
  manifest format, and artifact delivery.
- Dataset and weight storage location; compute for training.

## Handoff update template

Date / branch / commit:
Completed behavior:
Requirement IDs:
Checks actually run and evidence paths:
Known failures / blockers:
Exact next action:
