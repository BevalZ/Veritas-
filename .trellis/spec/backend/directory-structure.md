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
├── cli.py              # CLI entry point boundary
├── config.py           # Runtime configuration boundary
├── models.py           # Stable dataclass/report models and model conversion
├── preflight.py        # Critical capability preflight boundary
├── renderers.py        # Markdown/HTML renderer boundary
├── risk_rules.py       # Versioned final risk scoring boundary
├── run.py              # Run request/result and orchestration boundary
└── workspace.py        # Per-run workspace boundary
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
- `veritas/renderers.py` accepts `AuditReportModel` / `EvidenceFinding` and
  converts them before delegating to the existing Markdown and HTML renderers.
- `veritas/run.py` exposes the run orchestration boundary without requiring
  callers to import the legacy module directly.
