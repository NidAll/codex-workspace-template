# Instruction and agent workflow

## Instruction ownership

- Root `AGENTS.md`: shared working rules and an index of owning projects/areas.
- Project `AGENTS.md`: real setup commands, file/layer boundaries, compatibility
  contracts and relevant checks. Read it before editing the project.
- Narrow guides: instructions needed only for a specific subsystem or task.
  Link them from the owner instead of copying their bodies into every parent.
- Task state: temporary objective/progress/next action, separate from durable rules.
- History: dated evidence and decisions, searched only when the task needs them.

Use `AGENTS.md` consistently. Instruction discovery is tied to the active project
and directory; a link in an index is a route to read, not automatic file loading.
Do not read all sibling project guides at task startup. Project-specific exceptions
stay with their owning guide; shared policies should have one maintained source.

## Delegation

Main owns planning, architecture, decomposition, integration, review and final
acceptance. Do simple work directly. Delegate only a bounded specialist question
or independent implementation that adds value; do not create every role by default
or repeat an exploration whose answer is already established.

| Role | Responsibility | Boundary |
| --- | --- | --- |
| Main | Plan, integrate, review, verify acceptance | Only role that delegates |
| Explorer | Trace source, callers, dependencies and contracts | Read-only, focused evidence |
| Researcher | Resolve documentation/version/compatibility questions | Read-only, authoritative sources |
| Worker | Implement and validate an assigned change | Explicit file/behavior ownership |

The role TOMLs and config own models, effort and configured concurrency/depth.
Do not duplicate their definitions in project instructions. Preserve the main-only
delegation topology: children must not spawn or delegate. Parent sandbox and
service/tool permissions apply to children; a read-only instruction is not a
separate sandbox. Session overrides can affect defaults, so inspect actual
runtime metadata before claiming which model/effort ran.

Prefer named roles and `fork_turns="none"` where supported. A fresh-context brief
must stand on its own: objective, necessary paths/versions/evidence, constraints,
exclusive file ownership, acceptance checks and expected handoff. Use
[the brief template](templates/delegation.md). Do not forward whole histories,
inventories or unrelated logs. If a client uses different delegation controls,
map the same scope/ownership rules to its supported interface.

Explore and research concurrently only when their questions are independent.
Give each editing agent exclusive files; serialize shared-file edits. Main handles
integration dependencies. A child that needs additional shared files reports the
dependency before editing. Other agents' changes must not be overwritten.

A failed test-fix cycle is an attempted fix followed by validation that still fails
for the same issue. After two consecutive failed cycles for that issue, worker
stops and escalates to main with the command, concise error, both attempted fixes,
current diff and diagnosis. Treat unavailable tools/services/permissions separately;
do not repeatedly retry an unchanged environment blocker.

Handoffs contain findings or changed paths, exact checks/results, risks/unknowns
and the smallest remaining step. Keep them concise without omitting material
failure evidence. Main reviews the actual diff and performs the necessary
independent acceptance check; an agent's success claim is not proof.

## Task context and resume

For sustained or interruptible work, keep one local `.codex/tasks/<slug>.md` file
per task using [the task-state format](templates/task-state.md). Save the objective,
constraints, decisions, changed paths, exact checks/results, unresolved issues and
next step at milestones and before handing off. Do not record secrets or private
inputs just to make a checkpoint complete. Simple edits need no checkpoint.

After compaction or resuming, locate the matching task note, read only its required
project guidance, and inspect current Git diff and relevant transient state.
Continue the original objective; do not start another whole-workspace audit.
A new message normally steers the active task unless the user clearly cancels or
replaces it. Verify stale assumptions instead of treating a checkpoint as live state.

A checkpoint is maintained task state, not a conversation transcript or a replay
of reasoning. Independent tasks must not share a mutable catch-all progress file.
Mark completed work accurately and retain unfinished requirements when handing off.

## Maintenance

Update an owning guide when its contracts change and the root index when routing
or shared rules change. Put detailed logs and dated evidence outside always-loaded
instructions. If the project has a history/change-record convention, record the
purpose, paths, actual validation, limits and follow-up there. Do not force every
project to create the same journal or copy private history into a reusable template.

Use targeted searches and bounded outputs. Do not rerun passing checks without a
new change or unresolved concern. Separate static support, fixtures, runtime
execution and measured performance in reports. Keep task checkpoints and local
runtime/configuration state out of Git and exports.
