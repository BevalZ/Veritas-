# Split package and layer report renderers

## What to build

Move toward a package layout and separate report rendering from audit orchestration and evidence normalization.

## Acceptance criteria

- [x] `paper_audit.py` remains a thin compatible entry point.
- [x] Package modules exist for config, preflight, run orchestration, workspace, models, risk rules, adapters, and renderers.
- [x] Renderers consume stable models rather than free-form upstream dicts.
- [x] Existing report fixture assertions still pass or are intentionally updated.
- [x] CLI help remains available.

## Verification

- `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct package-boundary smoke for `veritas.config`, `veritas.preflight`, `veritas.run`, `veritas.workspace`, `veritas.risk_rules`, `veritas.adapters`, and renderer model consumption.
- Direct compatibility smoke confirmed `import paper_audit` resolves to the legacy implementation module so existing monkeypatch-based tests keep working during migration.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in this environment.

## Blocked by

- `05-28-audit-run-module`
- `05-28-strict-evidence-schema`
- `05-28-rule-based-risk-scoring`
