# Continue in another editor or AI session

Use this entry point when moving from this chat to Cursor or another agent.
The chat is not required project memory. Current outcomes and next actions live
in [ML status](ml/STATUS.md); update that file after meaningful work.

## Open the correct checkout

On Emir's current machine, open `/Users/emirtg/Desktop/dowser`. Inspect the branch
and working tree before changing files. Opening the same directory preserves
local ignored data and the Python environment; do not recreate or overwrite them.

```sh
git status --short --branch
git rev-parse HEAD
git fetch origin
git log --oneline HEAD..origin/main
```

The active ML branch and review link are in [ML status](ml/STATUS.md). These ML
docs and implementation are not yet merged into main. A fresh clone must check
out the ML branch to see them. If there are uncommitted changes, inspect and
preserve them before switching branches or integrating upstream changes.

Raw maps, prepared images/ZIPs, and `.venv` are deliberately outside Git. They
remain available in this local checkout, but do not appear in a fresh clone.
For another machine, follow [annotation setup](ml/ANNOTATION.md). Preserve any
existing annotations and manifests; a Git clone cannot restore ignored labels.

## Read before editing

1. [Root agent instructions](../AGENTS.md) and [contribution guide](../CONTRIBUTING.md).
2. [ML agent instructions](../pipeline/AGENTS.md).
3. [Full Master Plan](master-plan/source.txt), the current requirements baseline.
4. [ML status](ml/STATUS.md): actual progress, verification, limitations, next action.
5. [Requirements](ml/REQUIREMENTS.md) and [backend contract](ml/CONTRACT.md).
6. [Annotation instructions](ml/ANNOTATION.md) and the latest record in
   [experiments](ml/EXPERIMENTS.md).

For the regional decision and source evidence, read
[region research](research/REGION_SELECTION.md) and
[canonical map configuration](../pipeline/config/region.json).
The old PRD and the full-main review are historical references; neither overrides
the Master Plan or current code. Confirm current remote changes before claiming
the recorded main revision is still the latest.

## Resume and document

Continue the exact next action in ML status. Distinguish implemented preparation
from human annotation, model training, and measured evaluation. Do not invent
labels or metrics, randomize frozen geographic splits, provision paid resources,
or merge a draft without the agreed review.

Before edits, identify the affected Master Plan acceptance and inspect the code.
After edits, run relevant checks, update status and affected requirements or
contracts, and record meaningful data/model runs in experiments with identities
and limitations. Preserve teammates' changes and keep ML work in its task branch.
Commit and push the intended files so another machine can resume.

For an editor agent, explicitly ask it to read `AGENTS.md` and this file first;
the handoff does not rely on an editor automatically importing this chat.
