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

## Scenario: Image Semantic Cache Resume Contract

### 1. Scope / Trigger

- Trigger: Image semantic analysis writes or reads resume/cache artifacts.
- This applies to hidden resume caches and user-visible `image_semantic_cache.json`.

### 2. Signatures

- `_image_semantic_cache_key(image_path, api_url=None, model=None, cache_version=None) -> str`
- `_load_merged_json_dicts(*paths) -> dict`
- `build_image_audit(..., semantic_cache=None, semantic_cache_save=None, ...) -> dict`

### 3. Contracts

- Cache keys must include the image fingerprint plus image semantic API endpoint,
  model, and `IMAGE_SEMANTIC_CACHE_VERSION`.
- Cache keys must not include raw API keys or secrets.
- Hidden resume cache and visible cache must be merged before image semantic
  analysis starts; hidden resume cache wins on key conflicts.
- Successful image semantic results must flush through `semantic_cache_save`
  immediately after each image so interrupted runs keep completed work.
- Provider error results must not be cached as successful semantic evidence.

### 4. Validation & Error Matrix

- Same image and same service context -> reuse cached result.
- Same image but changed endpoint/model/cache version -> call image semantic
  service again.
- Malformed or non-dict cache file -> ignore that file and continue with other
  cache sources.
- Cached result with `status == "error"` -> remove it and retry.

### 5. Good/Base/Bad Cases

- Good: A run interrupted after image 1 writes `image_semantic_cache.json`; the
  next run loads that entry and continues from image 2.
- Base: Visible cache has one key and hidden cache has another; both are used.
- Bad: Switching from one image semantic model to another reuses the old
  model's summary for the same image.

### 6. Tests Required

- Regression test that a model, endpoint, or cache-version change causes a fresh
  semantic call.
- Regression test that visible and hidden caches merge, with hidden cache taking
  conflict priority.
- Regression test that completed semantic results are flushed after each success.

### 7. Wrong vs Correct

#### Wrong

```python
cache_key = _image_file_fingerprint(image_path)
semantic_result = semantic_cache.get(cache_key)
```

#### Correct

```python
cache_key = _image_semantic_cache_key(image_path)
semantic_result = semantic_cache.get(cache_key)
```
