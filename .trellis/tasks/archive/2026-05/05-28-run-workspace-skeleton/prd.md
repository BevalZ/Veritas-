# Create per-run audit workspace

## What to build

Create a per-run workspace that keeps raw and intermediate artifacts traceable while preserving root-level latest report shortcuts.

## Acceptance criteria

- [x] Each run gets a unique workspace under a stable runs directory.
- [x] Workspace records preflight, input manifest, report outcome, and artifact paths.
- [x] Root-level report shortcuts point to the latest complete/limited/failed artifact.
- [x] Multiple runs do not overwrite each other's workspace data.
- [x] Shared cache use is recorded in the current run workspace.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- CLI smoke: failing MinerU preflight creates `.paper_audit_runs/<run_id>/`, records `input_manifest.json`, `preflight.json`, `cache_use.json`, and `report_outcome.json`, copies failed artifacts into the workspace, and preserves root-level failed artifacts.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-audit-artifact-types`
