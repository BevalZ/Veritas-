# Add fake-adapter end-to-end tests

## What to build

Add end-to-end tests that use fake adapters to prove complete and failed outcomes without real network calls.

## Acceptance criteria

- [x] A fake-adapter complete run produces complete Markdown and JSON artifacts.
- [x] LLM chunk failure produces failed diagnostics.
- [x] Reference lookup service-wide failure produces failed diagnostics when references exist.
- [x] Input with detectable images and imagedetector failure produces failed diagnostics.
- [x] Tests do not require real API keys, network, MinerU, GLM, imagedetector, Crossref, OpenAlex, or PubMed.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- Direct fake-adapter E2E smoke for one complete outcome and one text LLM failed outcome
- Added tests for complete, text LLM failure, reference lookup failure, and imagedetector failure using fake adapters only.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in the current environment.

## Blocked by

- `05-28-adapter-interfaces-and-fakes`
