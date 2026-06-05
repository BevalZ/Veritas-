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

## Scenario: HTML Follow-up Draft Workflow

### 1. Scope / Trigger

- Trigger: HTML reports generate PubPeer comments or journal letters through
  the local report action service.
- This applies to article identity confirmation, selected evidence, custom
  user concerns, prompt construction, and persisted `followups/` artifacts.

### 2. Signatures

- `build_followup_generation_context(context, identity=None, selected_issues=None, custom_concerns=None, tone="conservative") -> dict`
- `build_followup_prompt(kind, context, language="zh", tone=None) -> list[dict]`
- `generate_and_save_followup_draft(kind, context, language="zh", identity=None, selected_issues=None, custom_concerns=None, tone="conservative", disclaimer_confirmed=False, timeout=None) -> dict`
- `load_existing_followups(context, language="zh") -> dict`
- Report action service routes:
  - `POST /generate`
  - `POST /followups`

### 3. Contracts

- HTML must require confirmation of title, journal, authors, DOI, year,
  selected evidence, tone, language, and manual-review disclaimer before
  generation.
- Follow-up generation must persist:
  - `followups/article_identity.json`
  - `followups/pubpeer_comment.<zh|en>.md`
  - `followups/journal_letter.<zh|en>.md`
  - `followups/followup_generation_log.json`
- `article_identity.json` must record `source: "html_confirmed"` and must not
  contain LLM API keys.
- Custom concerns must use `source: "user_added"` so they are not confused with
  automated findings.
- Prompt context must include article identity, selected evidence, custom
  concerns, language, tone, artifact type, and limited reasons when present.
- Existing drafts must be loadable through `POST /followups` when reopening an
  old HTML report while the local service is running.

### 4. Validation & Error Matrix

- Missing manual-review confirmation -> `manual_review_confirmation_required`.
- `artifact_type == "failed"` -> `failed_report_followup_blocked`.
- Unsupported kind -> `unsupported action kind`.
- Local action service unavailable from HTML -> show service URL and
  `python paper_audit.py --serve-report-actions --report-actions-port <port>`.
- Limited report -> generation allowed, but prompt must request a scope
  limitation statement.

### 5. Good/Base/Bad Cases

- Good: User confirms identity, selects red-flag evidence, generates a Chinese
  PubPeer draft, and `followups/pubpeer_comment.zh.md` plus log metadata are
  written.
- Base: User reopens an old HTML report, starts the action service, and the page
  loads existing drafts from `followups/`.
- Bad: A failed diagnostic report generates a journal letter or a draft is shown
  only in browser state without a Markdown artifact.

### 6. Tests Required

- HTML renderer test asserts identity fields, tone selector, evidence picker,
  manual confirmation, follow-up load URL, and startup command are present.
- Unit test blocks failed reports.
- Unit test requires manual-review confirmation.
- Unit test persists draft Markdown, article identity JSON, and generation log.
- Unit test prompt payload includes confirmed identity, selected evidence,
  `source=user_added` concerns, tone, and limited scope.
- Unit test loads existing follow-up artifacts.

### 7. Wrong vs Correct

#### Wrong

```python
text = generate_followup_draft(kind, context, language=language)
return {"ok": True, "text": text}
```

#### Correct

```python
result = generate_and_save_followup_draft(
    kind,
    context,
    language=language,
    identity=payload.get("identity"),
    selected_issues=payload.get("selected_issues"),
    custom_concerns=payload.get("custom_concerns"),
    tone=payload.get("tone"),
    disclaimer_confirmed=bool(payload.get("disclaimer_confirmed")),
)
```

## Scenario: Local Web Runner Service Contract

### 1. Scope / Trigger

- Trigger: A local browser workbench starts real audit runs through the existing
  CLI and exposes run state, logs, config status, and recorded artifacts over
  localhost HTTP.
- Applies to `python paper_audit.py --serve-web`, not to cloud hosting or
  arbitrary filesystem browsing.

### 2. Signatures

- CLI:
  - `python paper_audit.py --serve-web [--web-port PORT] [--no-open]`
  - Audit subprocess command:
    `python paper_audit.py <input_path> --json --no-open [-o output] [--fresh]`
- HTTP routes:
  - `GET /`
  - `GET /health`
  - `GET /api/config`
  - `GET /api/runs`
  - `POST /api/runs`
  - `GET /api/runs/<run_id>`
  - `GET /api/runs/<run_id>/logs?offset=N`
  - `GET /api/runs/<run_id>/artifacts`
  - `POST /api/runs/<run_id>/cancel`
  - `POST /api/pick-path`
  - `GET /artifact/<run_id>/<kind>`
  - Shared report actions: `POST /generate`, `POST /followups`

### 3. Contracts

- Server must bind to `127.0.0.1` by default; do not add a public host option
  without a separate security review.
- `POST /api/runs` accepts only `input_path`, optional `output`, and `fresh`.
  The server always adds `--json --no-open`.
- When `output` is omitted, the Web Runner must derive an output stem in the
  input's parent directory as `<project_name>_<YYYYMMDD-HHMMSS>/audit_report`
  and pass it through `-o`.
- The workbench may support client-side file/directory drag-and-drop, but it
  must only populate the existing `input_path` field; do not upload bytes or add
  a backend filesystem browser for this interaction.
- Drag-and-drop path extraction must prefer full local `file://` values from
  `text/uri-list` or `text/plain` before falling back to browser `File.name`,
  because `File.name` is not a usable audit path when the file is outside the
  repository working directory.
- The workbench may expose local picker buttons through `POST /api/pick-path`
  modes `input_file`, `input_directory`, and `output_directory`; this endpoint
  opens a native picker when available and returns one selected path, not a
  browsable directory listing.
- Primary input/output fields should be readonly display fields; users select
  with buttons or drag-and-drop.
- The current-run panel should surface the selected/running output path and
  render allowlisted artifact actions after completion.
- Failed and canceled runs may expose a retry action, but retry must call the
  same `POST /api/runs` path with the previous run's `input_path`, `output`,
  and `fresh` values; it must not bypass the single-active-run guard.
- Only one audit run may be active. Extra starts return HTTP 409 with
  `error: "busy"`.
- History is a convenience index at `.veritas_web/runs.json`; audit artifacts
  remain in the existing CLI output locations.
- Config status may report booleans such as `api_key_configured`; it must not
  include raw API keys or secret values.
- Artifact serving must be allowlisted by recorded run metadata. Valid kinds
  are `html`, `markdown`, `json`, and `folder`.

### 4. Validation & Error Matrix

- Empty `input_path` -> HTTP 400 `input_path_required`.
- Active run exists -> HTTP 409 `busy`.
- Subprocess spawn failure -> HTTP 500 `start_failed`.
- Output directory creation failure -> HTTP 500 `output_prepare_failed`.
- Unsupported picker mode -> HTTP 400 `unsupported_picker_mode`.
- Picker canceled -> HTTP 400 `canceled`.
- Native picker unavailable -> HTTP 400 `picker_unavailable`.
- Unknown run id -> HTTP 404 `not_found`.
- Unknown artifact kind -> HTTP 404 `unknown_artifact`.
- Recorded artifact path missing -> HTTP 404 `missing`.
- Port conflict -> process exits non-zero with guidance to use `--web-port`.

### 5. Good/Base/Bad Cases

- Good: User opens `/`, starts one directory audit, watches log polling, then
  opens recorded HTML/Markdown/JSON artifacts.
- Base: User cancels a run; the run becomes `canceled` and explains that rerun
  can reuse resume caches.
- Bad: Web API accepts an arbitrary file path under `/artifact` and returns its
  contents without being attached to a recorded run.

### 6. Tests Required

- CLI help exposes `--serve-web` and `--web-port`.
- Service mode loads runtime config and respects `--no-open`.
- Workbench HTML contains path input, output input, fresh checkbox, start,
  cancel, logs, config, and recent-runs regions.
- Workbench drag-and-drop tests assert the drop target, path extraction helper,
  directory-entry support, and `preventDefault()` navigation guard.
- Unit tests assert `file://` URI-list payloads decode to full local paths.
- Unit tests assert default output stem mapping and picker helper behavior.
- Workbench tests assert current-run output/actions and retry helpers are
  rendered.
- Config API/status does not serialize secret key values.
- Starting a run calls `subprocess.Popen` with the existing CLI plus
  `--json --no-open`, optional `-o`, and optional `--fresh`.
- A second active run is rejected; cancel calls `terminate()` and records
  `canceled`.
- Log polling returns cursor/offset-based lines.
- Artifact lookup rejects unknown or unrecorded kinds.

### 7. Wrong vs Correct

#### Wrong

```python
return Path(request.query["path"]).read_bytes()
```

#### Correct

```python
target, error = state.artifact_target(run_id, kind)
if error:
    return {"ok": False, "error": error}, 404
return Path(target).read_bytes()
```

## Scenario: Direct Single-File Text Extraction

### 1. Scope / Trigger

- Trigger: A user passes a single file path rather than a directory.
- This applies to PDF, `.docx`, Excel, CSV, TXT, and Markdown direct inputs.

### 2. Signatures

- `SUPPORTED_TEXT_FILE_EXTENSIONS: set[str]`
- `extract_text_from_file(file_path, max_chars_per_file=None, use_mineru=False, mineru_lang="ch", output_dir=None) -> str`
- `run_audit(run_request, args) -> RunResult`

### 3. Contracts

- Direct `.pdf` input keeps the existing PDF/MinerU behavior.
- Direct non-PDF supported text inputs must use `extract_text_from_file()`, not
  `extract_pdf_text()`.
- Direct `.docx` input requires `python-docx`; direct `.xlsx`/`.xlsm` input
  requires `openpyxl`.
- Direct legacy binary `.doc` input is unsupported unless a real extraction
  dependency is added; it must fail clearly rather than being treated as PDF.
- Successful direct non-PDF extraction metadata must include:
  - `input_type: "file"`
  - `extractor: "single_file_multi_format"`
  - `extraction_method: "<suffix>_text"`
  - `total_chars`
  - `size_mb`

### 4. Validation & Error Matrix

- `.docx` with `python-docx` available -> complete extraction path.
- `.docx` without `python-docx` -> `missing_optional_dependency`.
- `.xlsx`/`.xlsm` without `openpyxl` -> `missing_optional_dependency`.
- `.doc` -> `unsupported_legacy_doc`, with hints to convert to `.docx` or PDF.
- Unsupported extension -> `unsupported_file_type`.
- Empty extracted body -> `no_extractable_text`.

### 5. Good/Base/Bad Cases

- Good: `python paper_audit.py manuscript.docx --json` extracts Word text and
  continues to the normal audit pipeline.
- Base: `python paper_audit.py paper.pdf` still uses the PDF/MinerU path.
- Bad: `manuscript.docx` reaches `extract_pdf_text()` or a `.doc` file produces
  a misleading PDF extraction failure.

### 6. Tests Required

- Unit/integration test that direct `.docx` uses `extract_text_from_file()` and
  does not call `extract_pdf_text()`.
- Unit/integration test that direct `.doc` fails with `unsupported_legacy_doc`.
- Full core test suite after changing input routing.

### 7. Wrong vs Correct

#### Wrong

```python
full_text, meta, raw_pdf = extract_pdf_text(str(input_path), max_chars=999999)
```

#### Correct

```python
full_text = extract_text_from_file(input_path, max_chars_per_file=None, use_mineru=False)
```

## Scenario: Cross-file Consistency Audit

### 1. Scope / Trigger

- Trigger: Directory audit has extracted text from the main paper plus
  supplements, data files, or other non-reference paper materials.
- This applies to deterministic cross-file checks for sample sizes, group
  labels, and supplementary figure/table references.

### 2. Signatures

- `build_cross_file_consistency_audit(file_entries, root_path=None) -> dict`
- `format_cross_file_consistency_markdown(audit) -> list[str]`
- `format_cross_file_consistency_html(audit) -> str`

### 3. Contracts

- The audit must not call third-party services, local LLMs, or OCR services.
- Results must be stored in `meta["cross_file_consistency_audit"]` and rendered
  in Markdown, HTML, and JSON artifacts.
- Single-file inputs or directories without cross-file material must return
  `status: "skipped"` instead of failing the run.
- Findings must include conflict type, severity, both source categories/files,
  both source excerpts, reason, and manual-check guidance.
- Wording must describe evidence conflicts or review needs, not misconduct
  conclusions.

### 4. Tests Required

- Sample-size mismatch across main text and supplement -> strong finding.
- Matching sample sizes -> no false positive.
- Noisy table/OCR mismatch -> weak finding, not strong.
- Control-group vs vehicle-group label inconsistency -> medium finding.
- Markdown, HTML, JSON/action context expose the audit.

## Scenario: Evidence Chain Audit

### 1. Scope / Trigger

- Trigger: A successful audit has extracted text plus any combination of LLM
  checks, local statistic results, reference/resource/image audits, or
  cross-file consistency findings.
- The deterministic evidence-chain audit must aggregate these signals into
  reviewable evidence clusters and check Methods -> Results ->
  Abstract/Conclusion support.

### 2. Signatures

- `build_evidence_chain_audit(full_text, file_entries, report, meta, stat_result) -> dict`
- `format_evidence_chain_audit_markdown(audit) -> list[str]`
- `format_evidence_chain_audit_html(audit) -> str`

### 3. Contracts

- Store the result in `meta["evidence_chain_audit"]`.
- Result fields:
  - `status`
  - `checked_files`
  - `cluster_count`
  - `finding_count`
  - `strong_count`
  - `medium_count`
  - `weak_count`
  - `clusters`
  - `claim_chain_findings`
  - `note`
- Do not call third-party services, text/image LLMs, OCR services, or
  imagedetector from this audit.
- Do not change LLM prompt/schema or risk-rule scoring for this audit; it is an
  ordering and evidence-selection layer.
- Wording must describe support gaps, review needs, or cross-paragraph
  inconsistencies, not misconduct conclusions.
- Markdown, HTML, JSON, action summary, and follow-up context must expose the
  audit. Strong evidence clusters should be selected by default in the HTML
  follow-up evidence picker.

### 4. Validation & Error Matrix

- Methods and Results sample sizes conflict in a shared experimental context ->
  strong finding.
- Methods and Results group labels conflict -> medium finding.
- Abstract/Conclusion strong wording lacks nearby Results support -> medium
  finding.
- Directory input with cross-file/LLM/image signals mentioning the same
  figure/table/sample context -> one evidence cluster.
- Single-file input -> run the narrower chain audit and explain the limited
  scope in `note`.
- No text and no aggregate signals -> `status: "skipped"`.

### 5. Good/Base/Bad Cases

- Good: Methods says `n=42`, Results says the same experiment has `n=24`, and
  the report lists a strong Methods -> Results chain finding.
- Base: Matching Methods and Results sample sizes produce no finding.
- Bad: A weak isolated signal is upgraded to a misconduct conclusion or changes
  the final risk score.

### 6. Tests Required

- Unit test Methods/Results sample-size mismatch.
- Unit test strong Abstract/Conclusion claim without Results support.
- Unit test same figure/table evidence from cross-file audit and LLM checks
  clusters together.
- Unit test consistent Methods/Results/Conclusion produces no finding.
- Renderer/action-context tests for Markdown, HTML, JSON-equivalent metadata,
  follow-up context, and default evidence selection.

### 7. Wrong vs Correct

#### Wrong

```python
report = apply_risk_rules(report, stat_result=stat_result, image_audit=meta.get("image_audit"))
report["risk_level"] = "严重证据冲突" if evidence_chain_audit["strong_count"] else report["risk_level"]
```

#### Correct

```python
report = apply_risk_rules(report, stat_result=stat_result, image_audit=meta.get("image_audit"))
meta["evidence_chain_audit"] = build_evidence_chain_audit(full_text, file_entries, report, meta, stat_result)
```
