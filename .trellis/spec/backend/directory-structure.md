# Directory Structure

> How backend code is organized in this project.

---

## Overview

The project is migrating from a single historical script into a package while
preserving the public `paper_audit.py` command and import surface. New backend
boundaries should live under `veritas/`; the compatibility script should stay
thin.

---

## Directory Layout

```
paper_audit.py          # Thin compatibility entry point for CLI/import users
veritas/
├── legacy.py           # Current implementation during incremental migration
├── adapters.py         # External provider adapter exports
├── artifacts.py        # Formal artifact path and outcome helpers
├── cli.py              # CLI entry point boundary
├── config.py           # Runtime configuration boundary
├── models.py           # Stable dataclass/report models and model conversion
├── preflight.py        # Critical capability preflight boundary
├── renderers.py        # Markdown/HTML renderer boundary
├── risk_rules.py       # Versioned final risk scoring boundary
├── run.py              # Run request/result and orchestration boundary
└── workspace.py        # Per-run workspace boundary
└── file_utils.py       # Shared safe-name and JSON file helpers
└── report_schema.py    # Strict LLM evidence schema parser
└── retry_commands.py   # Retry command builders for failed diagnostics
└── runtime_metadata.py # Runtime clock metadata for reports/rules
tests/
└── test_core.py        # Core unit and smoke coverage
```

---

## Module Organization

- Keep `paper_audit.py` as a compatibility entry point only.
- During migration, `veritas/legacy.py` may hold the full implementation so old
  tests and monkeypatches keep working.
- Add new code to the narrow `veritas/*` boundary that owns the concept:
  config, preflight, run, workspace, models, risk_rules, adapters, or renderers.
- Renderer-facing code should accept stable dataclass models or dictionaries and
  normalize at the renderer boundary.
- Avoid adding new orchestration logic directly to `paper_audit.py`.

---

## Naming Conventions

- Package modules use lowercase snake_case filenames.
- Boundary modules should expose a small `__all__` list.
- Compatibility exports should re-export existing implementation symbols rather
  than duplicating behavior.

---

## Examples

- `paper_audit.py` aliases `veritas.legacy` for historical `import paper_audit`
  compatibility while still running `veritas.legacy.main()` as a script.
- `veritas/models.py` owns `AuditFailure`, `AuditReportModel`,
  `EvidenceFinding`, and related lightweight dataclasses; `paper_audit` keeps
  compatibility by re-exporting the same class objects through `veritas.legacy`.
- `veritas/file_utils.py` owns `_safe_name`, `_json_load`, `_json_save`, and
  `_load_merged_json_dicts`; these remain re-exported through `paper_audit` for
  compatibility with existing tests and local scripts.
- `veritas/report_schema.py` owns strict LLM evidence schema parsing and
  normalization; `paper_audit` keeps compatibility by re-exporting the same
  parser function objects through `veritas.legacy`.
- `veritas/retry_commands.py` owns retry command builders used by failed
  diagnostics; `paper_audit` keeps compatibility by re-exporting the same
  function objects through `veritas.legacy`.
- `veritas/runtime_metadata.py` owns runtime clock metadata helpers used by
  reports and deterministic date checks; `paper_audit` keeps compatibility by
  re-exporting the same function objects through `veritas.legacy`.
- `veritas/artifacts.py` owns formal audit artifact path, limited-outcome, and
  coverage-blocking helpers; `paper_audit` keeps compatibility by re-exporting
  the same function objects through `veritas.legacy`.
- `veritas/renderers.py` accepts `AuditReportModel` / `EvidenceFinding` and
  converts them before delegating to the existing Markdown and HTML renderers.
- `veritas/run.py` exposes the run orchestration boundary without requiring
  callers to import the legacy module directly.
