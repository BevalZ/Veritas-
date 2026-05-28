# Add critical capability preflight tracer bullet

## What to build

Add the first end-to-end preflight path for critical services, proving that failures stop complete report generation and write failed diagnostics.

## Acceptance criteria

- [x] MinerU preflight failure stops before formal extraction and writes failed diagnostics.
- [x] Text LLM preflight failure stops before chunk review and writes failed diagnostics.
- [x] Preflight performs a real lightweight call in production adapters.
- [x] Preflight success is reused only within the same run.
- [x] Preflight results are captured in the run metadata or diagnostics.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct helper smoke for `run_preflight_once(...)` and `preflight_text_llm(...)`
- CLI smoke: PDF input with failing MinerU preflight exits 1, writes `sample.failed.md` and `sample.failed.json`, and does not write `sample.audit.md`.
- CLI smoke: directory text input with failing text LLM preflight exits 1, writes `audit_report.failed.md` and `audit_report.failed.json`, and does not write `audit_report.audit.md`.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-explicit-runtime-config`
- `05-28-failed-audit-diagnostics`
