# Introduce audit adapter interfaces and fakes

## What to build

Define seams for external audit capabilities and provide fake adapters for deterministic tests.

## Acceptance criteria

- [x] Interfaces exist for MinerU, text LLM, reference lookup, image semantic analysis, and imagedetector.
- [x] Production adapters can wrap current implementation functions without a full rewrite.
- [x] Fake adapters can simulate success, auth failure, network failure, rate limit, schema error, and unsupported content.
- [x] Adapter results use structured success/failure/skip values.
- [x] No production code path depends on monkeypatching global service functions for new tests.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- Direct adapter smoke for `fake_audit_adapters(...)` and injected `ProductionMinerUAdapter(...)`
- Added unit tests covering `AdapterResult`, fake scenarios, and production wrapper injection.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-critical-capability-preflight`
- `05-28-run-workspace-skeleton`
