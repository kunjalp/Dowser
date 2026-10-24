# Team workflow

## Branches and ownership

The default branch is `main` in `kunjalp/Dowser`. Keep it
usable for integration and demos. Create a short-lived branch per task and merge
small PRs frequently. Proposed names: `ml/<task>`, `backend/<task>`, `web/<task>`,
`hardware/<task>`, `docs/<task>`. These prefixes describe work, not permanent silos.

ML owns map preparation, labels/splits, detection, pixel-to-geo conversion, and
evaluation. Backend owns record matching, proximity/ranking, and persistence.
Frontend owns map presentation; hardware owns firmware and reading delivery.
The Master Plan fixes names: Emir (ML), Ryann (backend/data and dedup), Kunjal
(Command Map/Field View), Murad (hardware). Python belongs under `pipeline/`.
Coordinate changes to root dependencies, shared schemas, CI, and repository-wide
instructions with their owners. Backend should review the detection interface.

Suggested ML increments:

1. `docs/ml-workflow`: documentation and proposed contract.
2. `ml/tile-georeferencing`: one sheet, manifest, coordinate checks.
3. `ml/ground-truth-export`: labeled fixture through the backend interface.
4. `ml/dataset-split`: labeling guide and leakage-safe split manifest.
5. `ml/detector-baseline`: training config, weights reference, inference.
6. `ml/evaluation`: metrics, threshold selection, errors, handoff evidence.

Create independent branches from current `main`. If a task requires an unmerged
PR, either merge that dependency first or explicitly target the dependent PR at
its parent branch and retarget after merge. Avoid a single long-running ML branch.

## Local commands

Run inside the verified repository, after inspecting status. Examples assume
`origin/main` exists and the new branch name is unused.

```sh
git status --short --branch
git fetch origin
git switch -c ml/tile-georeferencing origin/main
```

Before committing, inspect the diff and stage explicit paths. Include relevant
documentation with the code. Use descriptive commits, for example
`feat(ml): preserve tile geotransforms (FR-1.3, FR-3.1)`.

To integrate newer default-branch changes into your task branch, commit the work
first, fetch, then merge `origin/main`. Resolve conflicts deliberately and repeat
the relevant checks. Avoid rewriting shared history with rebase/force push.

For parallel AI sessions editing different tasks, use separate worktrees. Example:

```sh
git fetch origin
git worktree add -b ml/evaluation ../dowser-ml-evaluation origin/main
```

Each person needs their own clone; worktrees are for isolation within one clone.
Do not run agents that change branches in the same working directory concurrently.

## Synchronizing with main

At the start of each task, inspect status, fetch, and read incoming changes before
editing. Record the reviewed main SHA in the task handoff when it changes.

```sh
git status --short --branch
git fetch origin
git rev-parse origin/main
git log --oneline HEAD..origin/main
git diff --name-status HEAD...origin/main
```

If incoming commits exist, save the current work in a commit first, then merge
`origin/main` into the task branch. Resolve conflicts and recheck the affected
behavior. When main is already an ancestor, no merge commit is needed.
Re-read changed instructions, schema, APIs, and their consumers; update the
contract/status when interface behavior changes. Fetch again before pushing to
notice teammate changes made during the task.

The [main review](docs/MAIN_REVIEW.md) records the fully read baseline. Future
reviews can focus on changed files and dependencies, but must state the exact
revision and coverage. Distinguish source inspection from deployment validation.
Do not merge an unreviewed task PR into `main` merely to make the branches equal.

## Pull requests and integration

Use a draft PR early for shared interfaces. Each PR describes behavior, PRD IDs,
checks and evidence, artifact references, and remaining limitations. Request one
teammate's review; interface changes need the consuming teammate's review.
Merge after review and passing relevant checks; squash merge is a proposed team
default. After merge, start the next branch from the updated default branch.

Proposed GitHub settings: require PRs and one approval for `main`, block force
pushes and deletion, require the CI checks that actually exist. Configure only
after confirming the repository's existing rules and team agreement. These
settings have not been applied by this starter.

## Documentation and verification

Before code: identify requirement IDs and acceptance behavior. During code: add
docstrings and comments for units, assumptions, and reasoning. Before PR: run
relevant checks and update status/requirements/contract/experiments as applicable.
No separate documentation sprint is needed.

Existing loader checks: `python3 pipeline/test_load_calgem.py` or
`npm run test:calgem`. Offline ML checks:
`.venv/bin/python -m unittest discover -s pipeline/tests -v`.
Backend `npm test` needs its generated files; do not provision/deploy a service
just to run ML checks. Preserve Convex instructions for backend work.

Useful ML checks include synthetic/control-point coordinate checks, overlapping
tile deduplication, split leakage checks, detection serialization, explicit
fallback provenance, and held-out evaluation. Add CI after the actual language,
dependencies, paths, and test commands are known. CI should run lightweight
checks; full training belongs in a recorded experiment, not every PR.

Track manifests and small fixtures in Git. Store large raw maps, labels/images,
weights, and training outputs in agreed artifact storage with versions and
checksums. Reconcile `.gitignore` with actual paths before downloading assets;
avoid blanket image exclusions that hide demo fixtures. Preserve dependency lock
files. The PRD repository-size target is under 100 MB.

Official references: [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow),
[worktrees](https://git-scm.com/docs/git-worktree), and
[branch protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).
