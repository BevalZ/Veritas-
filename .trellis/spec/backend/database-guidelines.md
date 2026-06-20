# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

This project currently has no database, ORM, migrations, or persistent server
storage. Durable state is file-based: report artifacts, per-run workspaces,
shared resume caches, evaluation fixtures, and JSON/Markdown review artifacts.

---

## Query Patterns

- Use structured JSON files for machine-readable run state and review records.
- Use Markdown for human-readable formal artifacts.
- Treat `eval/replay/**` records as fixtures, not mutable runtime state.
- For repeated filesystem lookups, prefer `pathlib.Path` and explicit glob
  patterns over shelling out from Python code.

---

## Migrations

There are no database migrations. Schema-like changes should be handled through
versioned JSON payloads and explicit compatibility code where needed.

Examples:

- Evaluation records include `record_version`, `prompt_version`,
  `schema_version`, and `risk_rule_version`.
- Risk rules use `RISK_RULE_VERSION`.
- Image semantic caches use `IMAGE_SEMANTIC_CACHE_VERSION`.

---

## Naming Conventions

- Run workspaces live under `.paper_audit_runs/<run_id>/`.
- Formal report suffixes are `.audit.*`, `.limited.*`, and `.failed.*`.
- JSON fixture directories distinguish cases from replay records:
  `eval/cases/synthetic`, `eval/replay/synthetic`, and `eval/cases/public`.
- Local paper workbench directories such as `Test_paper/`, `Test_paper2/`,
  and `.veritas_web/` are runtime/user data and must stay ignored unless a
  reviewed fixture is intentionally moved into `eval/` or `tests/fixtures/`.

---

## Common Mistakes

- Do not treat resume caches as formal evidence artifacts.
- Do not overwrite replay fixtures during default evaluation.
- Do not write only Markdown when downstream code needs structured JSON.
- Do not commit user-provided manuscripts, generated reports, hidden resume
  caches, or local Web Runner state from ad hoc audit runs.
