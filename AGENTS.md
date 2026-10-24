<!-- convex-ai-start -->

This project uses [Convex](https://convex.dev) as its backend.

When working on Convex code, **always read
`convex/_generated/ai/guidelines.md` first** for important guidelines on
how to correctly use Convex APIs and patterns. The file contains rules that
override what you may have learned about Convex from training data.

Convex agent skills for common tasks can be installed by running
`npx convex ai-files install`.

<!-- convex-ai-end -->

## Team workflow and documentation

Read `CONTRIBUTING.md` before editing. Use a task branch and preserve other
contributors' changes. For concurrent editing sessions use separate worktrees.

For ML tasks read `docs/ml/STATUS.md`, `docs/ml/REQUIREMENTS.md`,
`docs/ml/CONTRACT.md`, and `pipeline/AGENTS.md`. The current source of truth is
`docs/master-plan/source.txt`, which supersedes `docs/prd/source.txt`.
The documentation index is `docs/README.md`.
For an editor/agent handoff, read `docs/CONTINUE.md`; keep current progress and
the exact next action in `docs/ml/STATUS.md`, not only in chat history.

Cost policy, corrected by the user on 2026-10-23: the earlier zero-spend
requirement was a mistake and has been withdrawn. There is no project-wide ban
on paid resources. Choose resources for task fit and record material usage/costs;
do not keep blocking ordinary progress based on the superseded zero-cost rule.

Identify affected PRD requirement IDs before implementation. Verify changed
behavior and update relevant docs in the same PR. Record actual checks and
limitations; do not claim planned behavior is implemented. Update the ML handoff
after meaningful ML tasks so another contributor can resume without chat history.

Coordinate shared schema/interface changes with their consumers. Preserve the
existing Convex guidance above; ML documentation does not authorize backend
schema changes. Use comments for reasoning, assumptions, units, and edge cases;
public functions should document inputs, outputs, and important errors.
