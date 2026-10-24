# ML contributor and agent instructions

Read the root `AGENTS.md` and `CONTRIBUTING.md`, then `docs/ml/STATUS.md`,
`docs/ml/REQUIREMENTS.md`, and `docs/ml/CONTRACT.md`. Paths here are repo-relative.

## Scope

Keep Python implementation under `pipeline/`, as required by the Master Plan.
ML owns map tiling, labels/splits, symbol detection,
pixel-to-geo conversion, and evaluation. Backend owns matching and ranking.
Use the existing backend interface documented in the contract; coordinate changes.
Ryann owns deduplication (20 m), matching, enrichment, and ranking. Kunjal owns
the interactive map; Ryann prepares historical overlays. ML supplies detections,
georeferencing, evidence crops, and metrics. Live tile upload is could-have.

Use 1024 px tiles, approximately 20% overlap, and train at imgsz 1024. Freeze
approximately 20% and at least 30 test tiles before training. Use a separate
validation partition for tuning. Never call assistant/published predictions
human-reviewed ground truth or label unknown tiles as negative examples.

## Implementation and documentation

- Identify relevant PRD IDs and inspect existing code before edits. Implement a
  small reviewable increment with checks appropriate to the behavior affected.
- Add docstrings to public functions with inputs, outputs, coordinate conventions,
  units, and important errors. Comment CRS choices, transform order, assumptions,
  and non-obvious edge cases rather than repeating code.
- Update setup docs for command changes, the contract for agreed interfaces, the
  experiment log for runs, and requirements evidence for completed milestones.
- After a meaningful task, update `docs/ml/STATUS.md` with actual outcomes,
  verification evidence, blockers, and the exact next action. Do not duplicate
  mutable status across other docs or mark plans as completed behavior.

## Data integrity and evaluation

- Preserve sheet provenance, years, tile offsets, source CRS, affine transforms,
  evidence crops, and artifact identities. Use each tile's own transform.
- Undo inference resize/letterboxing before coordinate conversion. Calculate
  distances in a meter-based CRS; export WGS84 latitude and longitude.
- Assign reproducible geographic/source groups before augmenting or splitting
  overlapping tiles. Keep overlapping coverage across years in one split to
  avoid training/validation leakage; document unavoidable dataset limitations.
- Never train on validation samples. Label metrics used for model or threshold
  selection as validation/tuning results. Reserve an untouched test set when
  possible; do not claim independent test performance without one.
- Record data/split identity, exact config/commands, code version (including dirty
  changes), software environment, hardware, weights/checksums, thresholds, actual
  metrics, and limitations in the experiment log.
- Keep ground-truth fallback distinguishable from inference. The current backend
  requires numeric confidence; its annotation semantics are unresolved. Do not
  invent a probability or silently change the schema to work around this.
- Keep raw maps, full datasets, weights, caches, and secrets outside normal Git.
  Track manifests, configs, small fixtures, and artifact references/checksums.

## Handoff

State outcome, changed files, PRD IDs, verification evidence, limitations, and
next action. A teammate must be able to resume without access to this chat.
