# Third-party-first refactor

## What to build

Parent task for the Paper Audit / Veritas third-party-first refactor.

The implementation source of truth is [docs/refactor-plan-third-party-first.md](../../../docs/refactor-plan-third-party-first.md), constrained by:

- [ADR-0001](../../../docs/adr/ADR-0001-third-party-first-critical-service-gating.md)
- [ADR-0002](../../../docs/adr/ADR-0002-remove-local-llm-and-ocr-formal-paths.md)
- [ADR-0003](../../../docs/adr/ADR-0003-adapter-capabilities-and-configuration.md)
- [ADR-0004](../../../docs/adr/ADR-0004-risk-rules-versioned-cache-and-evaluation.md)

## Acceptance criteria

- [x] Child tasks are completed in dependency order.
- [x] The final system defaults to third-party service coverage, not local LLM/OCR fallback.
- [x] Complete, limited, and failed reports are clearly distinct.
- [x] Critical service failure produces failed diagnostics, not a misleading complete report.
- [x] The CLI remains available through `paper_audit.py`.

## Verification

- `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct full-reference/image coverage smoke.
- Direct package-boundary and renderer version smoke.
- Direct `veritas.evaluation.run_replay_suite()` smoke.
- Review artifacts: `docs/reviews/third-party-first-implementation-checkpoint.md` and `.json`.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in this environment.

## Blocked by

None - can start immediately.
