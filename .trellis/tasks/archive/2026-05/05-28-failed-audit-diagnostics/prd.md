# Generate failed audit diagnostics

## What to build

Create a minimal failed-report path that writes formal diagnostic artifacts when a critical capability fails.

## Acceptance criteria

- [x] A structured failure result can be rendered to `audit_report.failed.md`.
- [x] The same failure result can be serialized to `audit_report.failed.json`.
- [x] Failed diagnostics include capability, error class, user-facing fix hints, completed stages, and retry command guidance.
- [x] Failed diagnostics explicitly state that no complete audit report was generated.
- [x] Existing successful report generation remains unchanged in this slice.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct smoke test for `save_failed_audit_diagnostics(...)` writing `.failed.md` and `.failed.json`
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-explicit-runtime-config`
