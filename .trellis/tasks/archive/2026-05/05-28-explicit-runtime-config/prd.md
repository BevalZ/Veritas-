# Make configuration loading explicit

## What to build

Introduce explicit runtime configuration loading and validation so third-party services are configured deliberately instead of through import-time side effects.

## Acceptance criteria

- [x] A runtime config shape exists for MinerU, text LLM, reference lookup, image semantic LLM, and imagedetector.
- [x] Importing project modules does not automatically search parent directories for `mykey.py`.
- [x] Missing required config can be represented as structured validation errors.
- [x] Existing CLI behavior is preserved where possible, except for deprecated local fallback messaging.
- [x] Tests can provide fake config without developer-machine private files.

## Verification

- `python -m py_compile paper_audit.py`
- `python paper_audit.py --help`
- Import smoke test confirmed `paper_audit.LLM_API_KEY == ""` before explicit config loading.
- `python -m pytest -q` could not run in the current environment because `pytest` is not installed.

## Blocked by

- `05-28-align-user-visible-semantics`
