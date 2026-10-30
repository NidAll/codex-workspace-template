# Workspace instructions

This file owns the project index and shared rules. Project `AGENTS.md` files own
local setup, boundaries and validation commands. Use the plural `AGENTS.md` name.
Read only the owning guide and references needed for the current task.

## Project index

Replace or extend these entries for the workspace. For a single repository,
point the index at its source areas instead of inventing nested projects.

| Project or area | First reference |
| --- | --- |
| Example nested project | [examples/project/AGENTS.md](examples/project/AGENTS.md) |
| Delegation and context workflow | [docs/workflow.md](docs/workflow.md), only when needed |

## Shared rules

- Confirm the working directory, owning repository and Git status. Preserve
  unrelated local edits; make the smallest complete change in the owning layer.
- Inspect current source and transient state before relying on notes. Use targeted
  searches and focused reads; skip dependencies, generated output and whole logs
  unless needed. Do not start services, install dependencies or download artifacts
  merely to inspect a workspace.
- Run checks relevant to changed behavior and the owning project's requirements.
  Do not repeat passing suites without a new change or unresolved concern.
  Report actual commands/results and separate observed facts from assumptions.
- Handle simple tasks directly. For independent specialist work, follow
  [the delegation contract](docs/workflow.md#delegation). Only main delegates;
  child agents do not spawn children. Respect configured concurrency/depth limits,
  use fresh-context briefs and give editing agents exclusive file ownership.
- Model/effort settings belong in `.codex/config.toml` and `agents/*.toml`, not
  duplicated project guides. Read-only role instructions do not create a separate
  sandbox. Main reviews the diff and verifies acceptance.
- Never commit credentials, private inputs, user/workstation identifiers, task
  state or generated runtime data. Use synthetic fixtures and neutral examples.

## Context and history

- For sustained work, keep one `.codex/tasks/<slug>.md` checkpoint per task using
  [the task-state format](docs/templates/task-state.md). Record objective,
  constraints, decisions, changed paths, checks/results, remaining work and next
  step at milestones or before a handoff. Simple edits need no checkpoint.
- After compaction or resuming, read only the matching checkpoint and necessary
  project guide, inspect current diff/state, then continue the original objective.
  A new message steers active work unless the user clearly replaces or cancels it.
- Keep historical evidence separate from current rules. Search only the matching
  topic/date when history matters. If a project keeps a change log, record actual
  validation and limits there. Update guides only when rules or routing change.
- Link to detailed instructions rather than copying them into every layer.
  Keep task notes local and concurrent task checkpoints separate.

Independent nested Git roots may omit outer instructions/config. Follow
[the setup guide](README.md#choose-a-layout) and verify discovery from the actual
project directory. Do not assume files were loaded or change trust, permissions,
context limits or global settings to hide a discovery problem.
