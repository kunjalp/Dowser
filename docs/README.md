# Dowser documentation

Start with [ML status](ml/STATUS.md), then read the requirements and contract.

| Document | Purpose | Update trigger |
| --- | --- | --- |
| [Full PRD](prd/source.txt) | Unmodified user-supplied product requirements | New PRD revision; preserve revision history |
| [Reviewed main snapshot](MAIN_REVIEW.md) | Full-file coverage, actual backend flows, integration gaps | Review of changed upstream files |
| [Region research](research/REGION_SELECTION.md) | Why Kern/Oil Center, exact maps, comparisons, limitations | Region/map decision or source recheck |
| [Region config](../ml/config/region.json) | Canonical study/query bounds and exact map identities | Approved region/map change |
| [ML requirements](ml/REQUIREMENTS.md) | Requirement IDs, acceptance checks, evidence | Milestone, verification, or approved deviation |
| [ML status](ml/STATUS.md) | Current state and next action | Meaningful task completion or handoff |
| [ML contract](ml/CONTRACT.md) | Proposed tile/detection boundary with backend | Jointly agreed interface change |
| [Experiments](ml/EXPERIMENTS.md) | Reproducible training and evaluation records | Each meaningful run |
| [Contribution guide](../CONTRIBUTING.md) | Branches, review, ownership, integration | Team workflow change |
| [Agent instructions](../AGENTS.md) | Persistent instructions for AI sessions | Engineering policy change |
| [ML agent instructions](../ml/AGENTS.md) | ML-specific code, data, and evaluation rules | ML engineering policy change |

The pasted PRD dated October 23, 2026 is the current requirements baseline. The
original local `DOWL_lost_wells_project_brief.docx` gives context and is not part
of the committed documentation. Explicit later user
decisions override the baseline; document the decision and affected IDs. Contracts
and this starter are implementation proposals, not approvals to amend the PRD.

Documentation is stored with code and reviewed in the same PR. Prefer English for
shared technical files and code identifiers; chat can remain in Russian. Do not
copy mutable statuses across several documents. Link to evidence instead.

This documentation is integrated with `kunjalp/Dowser` on the
`docs/ml-workflow` task branch. The existing backend schema is documented in the
contract. Branch/review conventions are proposed for team review; they are not
enforced GitHub settings. No ML model or training result has been produced yet.
