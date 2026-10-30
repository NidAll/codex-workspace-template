# Project instructions example

Copy this guide into an owning project and replace placeholders with real local
contracts. In this example the [workspace guide](../../AGENTS.md) is two levels
up; adjust that relative link after copying. An independent Git root may not load
outer instructions, so read the workspace guide explicitly if it should apply.
Every new project needs this concise, versionable guide and Git coverage before
implementation; use the workspace's new-project baseline when setting it up.

## Project map

| Area | Path or first reference |
| --- | --- |
| Main source and owning layer | `<source path>` |
| Tests and validation | `<test path or documented command>` |
| Runtime/deployment ownership | `<owner documentation>` |
| Task-specific detailed guidance | `<guide path, when relevant>` |

## Project contracts

- Runtime/toolchain: `<required versions and environment>`.
- Setup: `<documented command; do not install merely to inspect>`.
- Required checks: `<exact relevant commands and working directory>`.
- Compatibility: `<public interfaces, data formats and behavior to preserve>`.
- Boundaries: `<paths/layers owned here and dependencies requiring coordination>`.
- Change records: `<existing project convention, if any>`.

Keep shared rules in the workspace guide and role/model definitions in `.codex/`.
Read current source/status before relying on history, preserve unrelated edits,
and run the narrowest meaningful checks required by this project. If a dependency
needs edits outside the assigned scope, report it before changing shared files.
Use the workspace's task-state format for sustained work and keep actual notes local.
