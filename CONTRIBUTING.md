# Contributing

Keep this template generic enough to adopt in a new project without importing
another workspace's names, paths, data or assumptions. Preserve the short root
index, project-owned contracts, main-only delegation and explicit role boundaries.
Model and effort choices belong in TOML; documentation should point to that source.

Use Python 3.11+ and the standard library for the optional tools. Prefer focused
changes and synthetic filesystem/Git fixtures. Do not make tests call a model,
change a user's global configuration, start services or require credentials.

From the repository root, run:

```sh
python3 scripts/validate_template.py
python3 -m unittest discover -s tests -v
```

For a tool change, add meaningful regression coverage and report the exact
validation. For instruction changes, inspect affected links, ownership boundaries
and byte budgets. Do not repeat passing suites without a new change or unresolved
concern. CI runs the same standard-library checks with read-only repository access.

Before submitting, inspect the diff for credentials, real user/organization/project
names, private paths, session/task data and machine-specific results. Automated
privacy patterns are a guardrail, not a guarantee. Do not include private logs in
issues or pull requests. State the problem, resulting behavior, checks and any
material limits in the pull request. Contributions use the repository's MIT license.
