# Separate audit limited and failed artifact names

## What to build

Separate complete, limited, and failed audit outputs so users cannot mistake a partial or failed run for a complete audit.

## Acceptance criteria

- [x] Complete report artifacts use `audit_report.audit.*`.
- [x] User-limited artifacts use `audit_report.limited.*`.
- [x] Critical-failure artifacts use `audit_report.failed.*`.
- [x] Report headers state whether the artifact is complete, limited, or failed.
- [x] Existing single-file output behavior is mapped into the same three outcome types.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- Direct helper smoke for `audit_artifact_paths(...)`, `audit_limited_reasons(...)`, and `apply_audit_artifact_type(...)`
- Direct renderer smoke for complete/limited Markdown and HTML report headers
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-failed-audit-diagnostics`
