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
- Default synthetic replay must include both a clean low-risk case and at least
  one high-risk red-flag case so rule demotion/promotion regressions are visible.
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
- If `input_path` is only a basename and does not exist in the service current
  working directory, the server may resolve it before spawning the CLI by doing
  a bounded local basename search. Search roots are the current working
  directory tree, the home directory itself without recursion, and common home
  subdirectories (`Desktop`, `Documents`, `Downloads`, `Videos`, `Pictures`)
  recursively. Do not add full-disk search or a browsable filesystem API.
- Basename resolution must happen before default output calculation so omitted
  output paths are derived from the resolved input's real parent directory.
- Explicit paths, including absolute missing paths and relative paths with a
  parent component, must be preserved unchanged and passed to the CLI.
- Only pure basename inputs may use the fallback search. Inputs containing
  `./`, `../`, `/`, or `\\` keep their explicit path meaning even when the path
  does not exist.
- Recursive fallback search must match filename literals, not glob patterns.
  Legal filenames containing `[`, `]`, `?`, or `*` must resolve only to exact
  same-name files.
- When `output` is omitted, the Web Runner must derive an output stem in the
  input's parent directory as `<project_name>_<YYYYMMDD-HHMMSS>/audit_report`
  and pass it through `-o`.
- The UI may show a client-side default output preview, but it must omit
  `output` from `POST /api/runs` unless the user explicitly selected an output
  directory. This keeps basename fallback authoritative: the backend resolves
  the input first, then derives the default output from the resolved input's
  real parent directory.
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
- Run records may include a `summary` object derived from the recorded JSON
  artifact. Complete/limited artifacts read `llm_report.summary`,
  `llm_report.risk_level`, and `report_type`; failed artifacts read
  `failure.message`, `failure.capability`, `failure.error_class`, and
  `complete_report_generated`. Summary extraction must not add any new artifact
  file reads beyond the recorded complete/limited/failed JSON candidates.
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
- Basename cannot be resolved -> HTTP 400 `input_path_not_found`, without
  spawning a subprocess.
- Basename resolves to multiple candidates -> HTTP 409 `ambiguous_input_path`
  with a small `candidates` list, without spawning a subprocess.
- Explicit relative missing paths such as `./paper.docx` -> preserve the path
  and let the CLI return its normal missing-path failure; do not convert the
  request into basename search.
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
- Workbench tests assert auto-previewed output is not submitted as an explicit
  output override; only user-selected output directories set the explicit
  output flag.
- Unit tests assert basename-only inputs resolve when there is exactly one
  match, reject missing basenames with `input_path_not_found`, reject duplicate
  basenames with `ambiguous_input_path`, preserve explicit paths, and pass the
  resolved path to the subprocess command.
- Unit tests assert `./paper.docx` remains an explicit path and filenames with
  glob metacharacters are matched literally during fallback search.
- Workbench tests assert current-run output/actions and retry helpers are
  rendered.
- Artifact discovery tests assert complete/limited JSON summaries are extracted
  from the formal `llm_report` payload and failed JSON summaries are extracted
  from the formal `failure` diagnostic payload.
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
command = [sys.executable, "paper_audit.py", input_path, "--json", "--no-open"]
```

#### Correct

```python
resolved = resolve_web_runner_input_path(input_path)
if not resolved["ok"]:
    return resolved, 409 if resolved["error"] == "ambiguous_input_path" else 400
command = [sys.executable, "paper_audit.py", resolved["path"], "--json", "--no-open"]
```

## Scenario: Local Desktop GUI Contract

### 1. Scope / Trigger

- Trigger: A native desktop window starts real audit runs and exposes generated
  report outputs without requiring the user to open a browser.
- Applies to `python paper_audit.py --gui` and the installed `veritas-gui`
  console script.

### 2. Signatures

- CLI:
  - `python paper_audit.py --gui`
  - `veritas-gui`
- Entry points:
  - `gui_main() -> int`
  - `run_desktop_gui(history_path=None) -> int`
  - `desktop_gui_start_run(state, input_path, output="", fresh=False)`
  - `desktop_gui_run_summary(run) -> dict`
  - `desktop_gui_followup_context(run) -> dict`
  - `desktop_gui_generate_followup_draft(kind, run, language="zh", tone="conservative", timeout=None) -> dict`

### 3. Contracts

- The desktop GUI must be a native window, not a localhost browser page.
- The desktop GUI must reuse `WebRunnerState` for run start, cancellation,
  log polling, artifact discovery, summary extraction, and single-active-run
  behavior.
- The GUI may use `tkinter` because it is already a stdlib dependency used by
  path pickers; do not add Qt/Electron/Tauri/PyWebView without a separate
  dependency and packaging review.
- The GUI may use `tkinterdnd2` only for native file/directory drag-and-drop.
  If drag-and-drop registration fails, click-to-select controls must continue
  to work normally.
- Input and output path controls should be compact picker buttons, not editable
  text entry fields. Internal `StringVar` values still hold the exact paths for
  `WebRunnerState`.
- Empty output means "let `WebRunnerState` derive the output stem"; user-selected
  output directories should pass an explicit `<directory>/audit_report` stem.
- Dropping an input path sets the audit input. Dropping an output directory
  sets `<dropped-directory>/audit_report`; dropping an output file uses the
  file parent as the output directory.
- GUI config status may show readiness booleans and missing field names, but
  must not show raw API keys or secret values.
- Desktop GUI config status should be rendered as compact readonly status rows,
  not an editable log-style text box. If the row list grows, render it as
  compact chips so every capability remains visible in the sidebar.
- Desktop GUI may provide a local LLM settings dialog for `LLM_API_KEY`,
  `LLM_API_URL`, and `LLM_MODEL`. Saving must write those values to the
  existing local `config.py` format while preserving unrelated settings, apply
  them to the current GUI process, and rely on the normal runtime config loader
  so reopening the GUI loads the saved values by default.
- Desktop GUI chrome and dashboard labels should use short, consistent Chinese
  product labels such as `审计工作台`, `需处理`, `诊断报告`, and `暂无评分`;
  do not translate the primary GUI into English merely to match a visual
  reference. Raw logs and generated report content may keep their original
  audit language.
- Desktop GUI sidebar should avoid redundant section labels when the picker
  buttons are self-explanatory. Boolean run options should sit inline when
  space permits, and their checked indicator should use the app accent color
  rather than the platform default gray.
- Report actions exposed by the GUI are limited to recorded `html`,
  `markdown`, `json`, and `folder` artifact paths. In the desktop GUI these
  actions should sit with the report summary card, not as a separate verbose
  instruction area.
- Desktop GUI follow-up actions may generate PubPeer comments and journal
  letters directly from a completed report. They must read the recorded JSON
  artifact, build the same formal report action context used by HTML reports,
  call `generate_and_save_followup_draft(...)`, and persist drafts under the
  normal `followups/` directory. Do not add a second prompt/save path.
- Desktop GUI follow-up actions must be enabled only for successful complete or
  limited reports with a recorded JSON artifact. Failed diagnostic reports must
  remain blocked by `failed_report_followup_blocked`.
- Successful runs may auto-open the recorded HTML artifact by default. This
  must be user-disableable, must happen at most once per run id, and must use
  only the allowlisted artifact path discovered through `WebRunnerState`.
- The run log text widget must be read-only to the user; code may temporarily
  enable it only while appending log lines, then must restore disabled state.
- The desktop dashboard should parse existing `progress_bar(...)` log lines
  into a visible progress bar and current-stage label. This is presentation
  state only; it must not alter audit orchestration or subprocess output.

### 4. Validation & Error Matrix

- `tkinter` import failure -> return non-zero and print a concise
  `tkinter 不可用` message.
- No display server (`TclError: no display name`) -> return non-zero and print
  a concise GUI startup failure.
- Empty input path from GUI -> show an in-window error and do not call
  `start_run`.
- Drag-and-drop dependency unavailable -> no startup failure; picker buttons
  remain the fallback.
- `WebRunnerState.start_run` returns validation or busy errors -> surface the
  backend message in the GUI.
- Successful run with recorded HTML artifact and auto-open enabled -> open the
  HTML artifact once after terminal artifact discovery.
- Failed or canceled run -> do not auto-open HTML automatically; leave the
  recorded artifact buttons available when artifacts exist.
- Successful complete/limited run with recorded JSON artifact -> enable
  `写 PubPeer` and `写 Letter`.
- Failed diagnostic report -> keep `写 PubPeer` and `写 Letter` disabled; direct
  helper calls must still raise `failed_report_followup_blocked`.
- Artifact open failure -> show an in-window error.
- Malformed or unrelated log line -> do not update progress state.

### 5. Good/Base/Bad Cases

- Good: User runs `python paper_audit.py --gui`, selects a PDF, starts an
  audit, watches logs, and the successful HTML report opens automatically.
- Base: User runs the command on a headless machine; it exits cleanly with a
  display-related message instead of crashing.
- Base: User disables auto-open, then opens `HTML`, `Markdown`, `JSON`, or the
  output folder manually through allowlisted artifact buttons.
- Base: User clicks `写 PubPeer` after a successful report; the draft is saved
  to `followups/pubpeer_comment.zh.md` and previewed in the GUI log pane.
- Base: User drags a paper file onto the input picker and drags a folder onto
  the output picker; the GUI updates paths without exposing editable text boxes.
- Bad: GUI creates a second subprocess orchestration path or exposes arbitrary
  filesystem paths unrelated to recorded artifacts.
- Bad: GUI sends a separate ad hoc prompt for PubPeer/Letter or only displays a
  draft in memory without writing formal `followups/` artifacts.

### 6. Tests Required

- CLI help exposes `--gui`.
- `--gui` loads runtime config and routes through `gui_main` /
  `run_desktop_gui` without requiring a real window in tests.
- `pyproject.toml` declares `veritas-gui = "veritas.legacy:gui_main"`.
- `pyproject.toml` and `requirements.txt` include `tkinterdnd2`.
- Desktop helper tests assert blank output becomes `None` before calling
  `WebRunnerState.start_run`.
- Desktop helper tests assert path picker buttons update compact display text
  and drag-drop handlers update input/output paths.
- Desktop helper tests assert run logs return to read-only state after append.
- Desktop helper tests assert config status is compacted without leaking
  capability secrets and can render readonly status rows.
- Desktop helper tests assert local LLM settings persistence creates/updates
  `config.py` without deleting unrelated capability settings.
- Desktop helper tests assert progress log lines update the progress bar and
  stage label while unrelated log lines are ignored.
- Desktop helper tests assert only `html`, `markdown`, `json`, and `folder`
  artifacts are surfaced from run summaries.
- Desktop helper tests assert successful HTML auto-open happens once, can be
  disabled, and does not trigger for failed runs.
- Desktop helper tests assert follow-up context is built from recorded JSON
  artifacts, follow-up generation reuses `generate_and_save_followup_draft`,
  and PubPeer/Letter buttons enable only for successful JSON-backed reports.
- Full `tests/test_core.py` must still pass without opening a real window.

### 7. Wrong vs Correct

#### Wrong

```python
subprocess.Popen([sys.executable, "paper_audit.py", input_path])
```

#### Correct

```python
result, status = desktop_gui_start_run(self.state, input_path, output, fresh)
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

## Scenario: Audit Run Request/Result Seam

### 1. Scope / Trigger

- Trigger: CLI, Web Runner, or desktop GUI code needs to start a formal audit
  run and interpret the outcome.
- This applies to the stable request/result objects that cross entry-point seams
  before and after entering the legacy audit engine.

### 2. Signatures

- `veritas.run_types.RunRequest`
- `veritas.run_types.RunResult`
- `RunRequest.from_args(args) -> RunRequest`
- `RunRequest.to_args() -> argparse.Namespace`
- `run_audit(run_request: RunRequest, args=None) -> RunResult`

### 3. Contracts

- `RunRequest` and `RunResult` live in `veritas/run_types.py`, not inside
  `veritas/legacy.py`.
- `paper_audit.RunRequest`, `veritas.run.RunRequest`, and
  `veritas.run_types.RunRequest` must remain the same class object.
- `paper_audit.RunResult`, `veritas.run.RunResult`, and
  `veritas.run_types.RunResult` must remain the same class object.
- `RunRequest` must carry every option needed by the current engine, including
  output path, JSON output, resume/fresh flags, all reference/resource/image
  limits, LLM timeout/retry flags, and report action port.
- `run_audit(request)` must work without callers passing an argparse namespace.
  The temporary legacy namespace is created only inside the run seam.
- `RunResult.failed(...)` must copy failure fields without importing legacy
  rendering or failed-artifact helpers, so `run_types.py` stays dependency-light.

### 4. Validation & Error Matrix

- Missing `pdf_path` in `from_args` -> caller/parser error before constructing
  a formal run request.
- Unknown optional argparse fields -> use safe defaults matching CLI defaults.
- Omitted `args` in `run_audit` -> use `RunRequest.to_args()`.
- Existing callers passing both `run_request` and `args` -> still supported
  during legacy migration.
- Failed run result -> `outcome == "failed"`, `exit_code == 1`,
  `artifact_type == "failed"`, and structured `failure` fields are populated.

### 5. Good/Base/Bad Cases

- Good: Web Runner resolves a dropped file, builds a `RunRequest`, and starts
  `run_audit(request)` without knowing the legacy namespace shape.
- Good: GUI/Web code can inspect `RunResult.artifact_paths` and
  `RunResult.failure` without importing failed-artifact renderers.
- Base: CLI parses arguments, builds `RunRequest.from_args(args)`, and existing
  behavior is unchanged.
- Bad: A new GUI option is added only to argparse and not to `RunRequest`, so
  GUI/Web runs silently ignore it.

### 6. Tests Required

- Unit test `RunRequest.from_args()` maps every current CLI/Web/GUI run option.
- Unit test `RunRequest.to_args()` preserves legacy field names such as `json`.
- Integration-style unit test calls `run_audit(RunRequest.from_args(args))`
  without passing `args`.
- Package-boundary test asserts all compatibility exports refer to the same
  `RunRequest` and `RunResult` class objects.

### 7. Wrong vs Correct

#### Wrong

```python
result = run_audit(RunRequest.from_args(args), args)
```

#### Correct

```python
request = RunRequest.from_args(args)
result = run_audit(request)
```
