# Require full reference and image coverage by default

## What to build

Make default complete reports require all parseable references and all detectable images to be covered by their critical third-party capabilities.

## Acceptance criteria

- [x] All parseable references are queued for online lookup by default.
- [x] All detectable images are queued for image semantic analysis and imagedetector by default.
- [x] User-provided limits produce limited reports, not complete reports.
- [x] No references found does not block a complete report.
- [x] No detectable images found does not block a complete report.
- [x] Service-wide lookup/detection failure blocks complete reports when relevant content exists.

## Verification

- `python3 -m py_compile paper_audit.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct smoke script for default all-reference lookup, default all-image semantic/imagedetector coverage, user limit limited reasons, no-content non-blocking behavior, and service-wide reference/imagedetector failure blocking.
- `python3 -m pytest tests/test_core.py -q` could not run because `pytest` is not installed in this environment.

## Blocked by

- `05-28-adapter-interfaces-and-fakes`
- `05-28-rule-based-risk-scoring`
