# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

The project relies on lightweight command-line verification plus deterministic
fake/replay fixtures because critical production capabilities call third-party
services. Default tests must not require API keys or network access.

---

## Forbidden Patterns

- Default tests must not call Crossref, OpenAlex, PubMed, MinerU, text LLMs,
  image semantic LLMs, or imagedetector.
- Do not promote new record-mode evaluation output into replay fixtures without
  reviewing the adapter, model, prompt version, schema version, risk rule
  version, input hash, and response payload.
- Do not render malformed LLM findings into complete reports.

---

## Required Patterns

- Use fake adapters or replay fixtures for deterministic tests.
- Evaluation records must include adapter, model, prompt version, schema
  version, risk rule version, input hash, timestamp, and response.
- Prompt, schema, or risk-rule changes must run the synthetic replay suite or
  document why evaluation was not run.
- Keep optional public-paper evaluation cases separate from default synthetic
  replay cases.

---

## Testing Requirements

- Run `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py`
  after backend edits.
- Run `python3 paper_audit.py --help` after CLI or entry-point edits.
- Run `veritas.evaluation.run_replay_suite()` after prompt/schema/risk-rule
  changes.
- Run `python3 -m pytest tests/test_core.py -q` when `pytest` is installed.

---

## Code Review Checklist

- Did the change preserve complete/limited/failed artifact distinctions?
- Did new tests avoid real third-party calls?
- Did changed prompt/schema/risk-rule behavior include replay evidence or an
  explicit note that evaluation was unavailable?
- Are new package boundaries added under `veritas/` rather than expanding the
  compatibility entry point?
