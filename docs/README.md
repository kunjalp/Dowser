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

The ML branch incorporates main `b0bd0bc`. The contract reflects the inspected
backend interfaces; deployment was not validated by ML. Raw artifacts are ignored:
maps/tiling are reproducible, but preserve human label ZIPs separately because Git
cannot restore them. Current annotation, split and training readiness are in
[ML status](ml/STATUS.md); no trained detector quality is claimed.
