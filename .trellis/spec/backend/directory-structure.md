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
├── failed_diagnostics.py # Stable failed-audit payload and conversion helpers
├── html_utils.py       # HTML escaping and script-safe JSON helpers
├── models.py           # Stable dataclass/report models and model conversion
├── preflight.py        # Critical capability preflight boundary
├── renderers.py        # Markdown/HTML renderer boundary
├── risk_rule_helpers.py # Shared risk scoring/merge helpers for rules/rendering
├── risk_rules.py       # Versioned final risk scoring boundary
├── run.py              # Run request/result and orchestration boundary
├── text_utils.py       # Shared text shortening and token similarity helpers
├── versions.py         # Prompt/schema/adapter/risk-rule version constants
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
  config, preflight, run, workspace, models, risk_rules, adapters, artifacts,
  failed_diagnostics, or renderers.
- Thin boundary modules that still delegate to `veritas.legacy` should import
  legacy inside the delegating function, not at module import time, unless a
  tested compatibility contract requires object identity.
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
- `veritas/failed_diagnostics.py` owns stable failed-audit JSON payload and
  failure-to-`AuditFailure` conversion helpers; Markdown/HTML formatting can
  remain in `veritas.legacy` until renderer dependencies are untangled.
- `veritas/html_utils.py` owns HTML escaping and script-safe JSON helpers used
  by renderers; these remain re-exported through `paper_audit` for
  compatibility while renderer extraction continues.
- `veritas/text_utils.py` owns shared text shortening and token similarity
  helpers used by follow-up generation, risk rules, references, and renderers.
- `veritas/versions.py` owns prompt, schema, adapter, and risk-rule version
  constants; compatibility modules should import these constants rather than
  redefining them.
- `veritas/config.py` owns runtime configuration loading/application helpers.
  Namespace-aware helpers let `veritas.legacy` preserve historical global
  monkeypatch behavior without making `veritas.config` import legacy.
- `veritas/risk_rule_helpers.py` owns extraction-limited classification,
  OCR/table red-flag downgrade, check similarity/merge, and merged
  summary/conclusion helpers shared by risk scoring and renderers. Runtime-year
  future-publication checks also live there; legacy callers pass the current
  runtime year explicitly to preserve compatibility with existing monkeypatches.
- `veritas/risk_rules.py` owns `apply_risk_rules` and `merge_chunk_reports`;
  `veritas.legacy` re-exports the same function objects for `paper_audit`
  compatibility.
- `veritas/renderers.py` accepts `AuditReportModel` / `EvidenceFinding` and
  converts them before lazily delegating to the existing Markdown and HTML
  renderers.
- `veritas/run.py` exposes the run orchestration boundary without requiring
  callers to import the legacy module directly; the legacy run engine is loaded
  only when `run_audit(...)` is called.
