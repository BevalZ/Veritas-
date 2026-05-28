# Review third-party-first implementation checkpoint

## What to build

Human review checkpoint for the third-party-first behavior before the deeper package split and evaluation expansion.

## Acceptance criteria

- [x] Review complete vs limited vs failed report behavior.
- [x] Review strict blocking behavior for MinerU, text LLM, references, image semantic analysis, and imagedetector.
- [x] Review full reference/image coverage semantics.
- [x] Review evidence risk language and risk levels.
- [x] Capture any changes as ADR updates before continuing.

## Verification

- `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct renderer version metadata smoke.
- Direct `veritas.evaluation.run_replay_suite()` smoke.
- Review artifacts: `docs/reviews/third-party-first-implementation-checkpoint.md` and `.json`.
- ADR updates: `docs/adr/ADR-0001-third-party-first-critical-service-gating.md` and `docs/adr/ADR-0004-risk-rules-versioned-cache-and-evaluation.md`.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in this environment.

## Blocked by

- `05-28-fake-adapter-e2e-tests`
- `05-28-rule-based-risk-scoring`
