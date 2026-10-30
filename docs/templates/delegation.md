# Delegation brief: <task>/<subtask>

Role: `<explorer | researcher | worker>`
Context mode: `fresh / fork_turns="none"` where supported.

## Objective and necessary context

<One independently answerable question or bounded implementation outcome.>
<Only relevant paths, versions, source evidence and decisions.>

## Scope and ownership

- Allowed paths: `<explicit files or read-only scope>`
- Do not edit: `<shared or neighboring paths>`
- Dependencies to report before editing: `<known shared owners>`
- Do not spawn or delegate to other agents.

## Constraints and acceptance

- <Relevant contracts and task-specific boundaries>
- <Exact meaningful checks and expected behavior>
- <State/runtime actions that are or are not authorized>

## Handoff

Return findings/changed paths, exact commands/results, risks, unknowns and the
next useful action. After two failed test-fix cycles for the same issue, worker
stops and reports both fixes, errors, diff and diagnosis. Report unchanged
environment blockers without repeated retries. Main reviews actual evidence
before accepting the result.
