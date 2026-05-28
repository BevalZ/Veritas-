# Move final risk scoring into rules

## What to build

Move final risk level and evidence risk score into a versioned rule engine. LLM output may explain findings but does not decide final level.

## Acceptance criteria

- [x] Final risk levels are limited to low, medium, high, and severe evidence conflict equivalents.
- [x] User-visible score is `证据风险分`, not fraud probability.
- [x] Rule output includes score breakdown.
- [x] imagedetector high score alone cannot produce the highest risk level.
- [x] Rule version is recorded in reports and cache-relevant metadata.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- Direct risk-rule smoke: LLM high risk with no findings is downgraded by rules; imagedetector high score alone stays below highest risk.
- Added tests for rule-version recording, LLM-risk override, imagedetector cap, and severe evidence conflict.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-strict-evidence-schema`
