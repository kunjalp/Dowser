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

For Emir's independent Cursor improvement experiment, open the separate
`/Users/emirtg/Desktop/dowser-cursor` worktree on `ml/cursor-improvements` and
follow [CURSOR_EXPERIMENT.md](ml/CURSOR_EXPERIMENT.md). It has copied local data
and environments; leave the original checkout/reference artifacts intact.
Cursor wrote `docs/ml/CURSOR_RESULTS.md`; no candidate beat data_v2 Val F1.

Raw maps, prepared images/ZIPs, and `.venv` are deliberately outside Git. They
remain available in this local checkout, but do not appear in a fresh clone.
For another machine, follow [annotation setup](ml/ANNOTATION.md). Preserve any
existing annotations and manifests; a Git clone cannot restore ignored labels.

There are two Python environments: root `.venv/` for preparation/auditing and
`pipeline/.venv/` for YOLO/MPS training. Their NumPy pins differ intentionally;
see [training setup](ml/TRAINING_PLAN.md). Active splits are in `kern_1024_v2`,
while human Train labels are in `reviewed_v2`. Preserve original v1 artifacts.
The 15-image Validation export is imported. The baseline and two subsequent
assistant-authorized data experiments are trained; data_v2 is currently selected.
Keep assistant training annotations distinct from human GT; preflight requires
explicit mixed-supervision opt-in and always retains human Validation labels.
Current paired preview, checkpoint, counts, metric limitations and next action
are in ML status; do not ask the user to repeat finished annotations. Additional
runs must still pass `pipeline.train_detector --check-only`.

## Read before editing

1. [Root agent instructions](../AGENTS.md) and [contribution guide](../CONTRIBUTING.md).
2. [ML agent instructions](../pipeline/AGENTS.md).
3. [Full Master Plan](master-plan/source.txt), the current requirements baseline.
4. [ML status](ml/STATUS.md): actual progress, verification, limitations, next action.
5. [Requirements](ml/REQUIREMENTS.md) and [backend contract](ml/CONTRACT.md).
6. [Annotation instructions](ml/ANNOTATION.md) and the latest record in
   [experiments](ml/EXPERIMENTS.md).
7. [Training plan](ml/TRAINING_PLAN.md): selected model/device and missing
   prerequisites. Backend availability is not a completed model-training run.

For the regional decision and source evidence, read
[region research](research/REGION_SELECTION.md) and
[canonical map configuration](../pipeline/config/region.json).
The old PRD and the full-main review are historical references; neither overrides
the Master Plan or current code. Confirm current remote changes before claiming
the recorded main revision is still the latest.

## Resume and document

Continue the exact next action in ML status. Distinguish implemented preparation
from human annotation, model training, and measured evaluation. Do not invent
labels or metrics, randomize frozen geographic splits, or merge a draft without
the agreed review. The user withdrew the earlier zero-spend ban on 2026-10-23;
follow current root instructions and record material resource usage/costs.

Before edits, identify the affected Master Plan acceptance and inspect the code.
After edits, run relevant checks, update status and affected requirements or
contracts, and record meaningful data/model runs in experiments with identities
and limitations. Preserve teammates' changes and keep ML work in its task branch.
Commit and push the intended files so another machine can resume.

For an editor agent, explicitly ask it to read `AGENTS.md` and this file first;
the handoff does not rely on an editor automatically importing this chat.
