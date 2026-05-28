# Enforce strict evidence schema

## What to build

Introduce stable evidence/report models and reject malformed LLM findings from complete reports.

## Acceptance criteria

- [x] Models exist for findings, audit report, reference audit, image audit, run metadata, and coverage.
- [x] LLM output schema has required fields for evidence, source, reason, recommendation, verdict, and confidence.
- [x] Missing required LLM fields trigger retry.
- [x] Retry exhaustion produces failed diagnostics instead of partial complete reports.
- [x] Raw LLM responses are preserved separately from normalized report findings.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- Direct parse smoke for valid strict findings and invalid missing-field findings
- Direct fake-adapter E2E smoke: invalid LLM schema writes failed diagnostics with `schema_error`
- Added tests for strict parse validation, truncated JSON rejection, and fake-adapter schema failure.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-audit-run-module`
