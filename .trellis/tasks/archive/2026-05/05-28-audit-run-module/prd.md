# Extract Audit Run module

## What to build

Extract the audit orchestration into a module that accepts a request and returns a structured result. Keep `paper_audit.py` as the compatible CLI entry.

## Acceptance criteria

- [x] `RunRequest` and `RunResult` exist.
- [x] CLI maps argparse values into `RunRequest`.
- [x] Critical failures, limited outcomes, and complete outcomes are represented in `RunResult`.
- [x] `main()` no longer directly owns all extraction, LLM, reference, image, and rendering stage logic.
- [x] `python paper_audit.py --help` still works.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct smoke for `RunRequest.from_args(...)` and `RunResult.complete/limited(...)`
- CLI smoke through `main()` into `run_audit(...)`: failing MinerU preflight exits 1 and writes failed diagnostics.
- Added tests for argparse mapping and complete/limited/failed `RunResult` representation.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-fake-adapter-e2e-tests`
