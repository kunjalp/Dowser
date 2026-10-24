# Dowser documentation

For a new editor or AI session, start with [continuation instructions](CONTINUE.md).
For a quick progress check, read [ML status](ml/STATUS.md).

| Document | Purpose | Update trigger |
| --- | --- | --- |
| [Continue in another editor](CONTINUE.md) | Checkout, reading order, local artifacts, resumption protocol | Handoff/setup change |
| [Master Plan](master-plan/source.txt) | Current authoritative scope, owners, and contracts | New team decision |
| [Original PRD](prd/source.txt) | Superseded history, retained unmodified | Historical reference only |
| [Reviewed main snapshot](MAIN_REVIEW.md) | Full-file coverage, actual backend flows, integration gaps | Review of changed upstream files |
| [Region research](research/REGION_SELECTION.md) | Why Kern/Oil Center, exact maps, comparisons, limitations | Region/map decision or source recheck |
| [Region config](../pipeline/config/region.json) | Canonical study/query bounds and exact map identities | Approved region/map change |
| [ML requirements](ml/REQUIREMENTS.md) | Requirement IDs, acceptance checks, evidence | Milestone, verification, or approved deviation |
| [ML status](ml/STATUS.md) | Current state and next action | Meaningful task completion or handoff |
| [ML contract](ml/CONTRACT.md) | Proposed tile/detection boundary with backend | Jointly agreed interface change |
| [Experiments](ml/EXPERIMENTS.md) | Reproducible preparation, training and evaluation records | Each meaningful run |
| [First training plan](ml/TRAINING_PLAN.md) | Selected model, local GPU, run settings, remaining data prerequisites | Training decision or measured result |
| [Team update and PR review](ml/INTEGRATION_REVIEW.md) | GeoTIFF/inference coordination, verified gaps, bounded merge recommendation | New integration evidence |
| [Detector improvement plan](ml/IMPROVEMENT_PLAN.md) | Text/lookalike errors, Train-only review batch and controlled comparison | Error analysis or new experiment |
| [Independent Cursor experiment](ml/CURSOR_EXPERIMENT.md) | Separate workspace, frozen reference, comparison protocol and return report | Cursor handoff/review |
| [Cursor results review](ml/CODEX_REVIEW.md) | Independent hashes/inference/metrics checks and annotation findings | Candidate review |
| [Ryann geographic handoff](ml/RYANN_HANDOFF.md) | Ready CSV/crops archive, sanity result, source coverage and receiving instructions | Geographic export/integration |
| [Final Test protocol](ml/FINAL_TEST.md) | Frozen candidate/settings, 30-image labeling ZIP and pending independent evaluation | Test preparation/evaluation |
| [False-candidate repair](ml/ROLLOUT_REPAIR.md) | Reproduced post-CalGEM failure, crop triage and bounded repair trials | Rollout error report/repair |
| [Annotation handoff](ml/ANNOTATION.md) | Local dataset commands, frozen partitions, labeling policy | Preparation/annotation change |
| [Contribution guide](../CONTRIBUTING.md) | Branches, review, ownership, integration | Team workflow change |
| [Agent instructions](../AGENTS.md) | Persistent instructions for AI sessions | Engineering policy change |
| [ML agent instructions](../pipeline/AGENTS.md) | ML-specific code, data, and evaluation rules | ML engineering policy change |

The user-supplied Master Plan is the current requirements baseline and explicitly
replaces the earlier PRD/Build Plan. Preserve original sources verbatim. Explicit
later user decisions override them. The user withdrew the earlier zero-cost
constraint on 2026-10-23; use the current policy in root agent instructions.
Record changes with their affected Master Plan sections.

Documentation is stored with code and reviewed in the same PR. Prefer English for
shared technical files and code identifiers; chat can remain in Russian. Do not
copy mutable statuses across several documents. Link to evidence instead.

The ML branch incorporates main `2b4678a`. The contract reflects the inspected
backend interfaces; deployment was not validated by ML. Raw artifacts are ignored:
maps/tiling are reproducible, but preserve human label ZIPs separately because Git
cannot restore them. Current annotation, split and training readiness are in
[ML status](ml/STATUS.md). Reported detector quality is Validation-only until
independent Test evaluation; geographic exports are not accuracy evaluations.
