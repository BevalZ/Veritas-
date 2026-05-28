# Add evaluation record replay harness

## What to build

Add an evaluation harness that supports stable replay by default and explicit record mode for real third-party calls.

## Acceptance criteria

- [x] Synthetic evaluation cases can run without network.
- [x] Optional public-paper evaluations are separate from default tests.
- [x] Replay mode is the default evaluation mode.
- [x] Record mode stores adapter, model, prompt version, schema version, and input hash.
- [x] Prompt/schema/risk rule changes have a documented eval path.

## Verification

- `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py`
- `python3 - <<'PY' ... run_replay_suite() ... PY`
- `python3 paper_audit.py --help`
- Added tests for replay suite payloads and record metadata.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in this environment.

## Artifacts

- `veritas/evaluation.py`
- `eval/cases/synthetic/clean-low-risk.json`
- `eval/replay/synthetic/clean-low-risk.json`
- `eval/cases/public/README.md`
- `docs/evaluation/record-replay.md`

## Blocked by

- `05-28-strict-evidence-schema`
- `05-28-rule-based-risk-scoring`
