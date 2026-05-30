# Error Handling

> How errors are handled in this project.

---

## Overview

<!--
Document your project's error handling conventions here.

Questions to answer:
- What error types do you define?
- How are errors propagated?
- How are errors logged?
- How are errors returned to clients?
-->

(To be filled by the team)

---

## Error Types

<!-- Custom error classes/types -->

(To be filled by the team)

---

## Error Handling Patterns

<!-- Try-catch patterns, error propagation -->

(To be filled by the team)

---

## API Error Responses

<!-- Standard error response format -->

(To be filled by the team)

---

## Common Mistakes

<!-- Error handling mistakes your team has made -->

## Scenario: Critical Capability Preflight Failure

### 1. Scope / Trigger

- Trigger: A formal audit depends on a critical third-party capability before producing a complete report.
- Critical capabilities currently include `mineru` for PDF extraction and `text_llm` for semantic review.
- Failure must stop the complete audit path and write failed diagnostics instead of silently degrading into a misleading complete report.

### 2. Signatures

- `preflight_mineru(timeout=10) -> PreflightResult`
- `preflight_text_llm(timeout=10) -> PreflightResult`
- `run_preflight_once(preflight_state, capability, runner) -> PreflightResult`
- `save_failed_audit_diagnostics(failure, input_path, meta=None) -> (Path, Path)`

### 3. Contracts

- `PreflightResult` fields:
  - `capability: str`
  - `ok: bool`
  - `error_class: str`
  - `message: str`
  - `details: dict`
  - `created_at: str`
- Failed artifact JSON fields:
  - `report_type: "failed"`
  - `complete_report_generated: false`
  - `failure.capability`
  - `failure.error_class`
  - `failure.fix_hints`
  - `failure.completed_stages`
  - `failure.retry_command`
- Preflight success can be reused only through the in-memory `preflight_state` for the current process run. Do not persist preflight success into resume caches.

### 4. Validation & Error Matrix

- Missing token/API URL/model -> `missing_required_config`
- HTTP 401/403 from provider -> `provider_auth_failed`
- HTTP 5xx or network exception -> `provider_unavailable`
- HTTP 4xx from text LLM preflight -> `preflight_http_error`
- 2xx text LLM response without `choices` -> `preflight_invalid_response`

### 5. Good/Base/Bad Cases

- Good: PDF input with MinerU enabled runs MinerU preflight before extraction; failure writes `.failed.md` and `.failed.json`, then exits non-zero.
- Base: Text input directory completes extraction and local statistics, then runs text LLM preflight before chunk review.
- Bad: Provider failure produces `*.audit.md`, partial complete reports, or silently falls back to local extraction for a formal audit.

### 6. Tests Required

- Unit test `run_preflight_once` reuses the result within one state object and does not reuse across a fresh state object.
- Unit test provider authentication failure maps to the expected `error_class`.
- CLI smoke for MinerU preflight failure asserts no `*.audit.md` exists.
- CLI smoke for text LLM preflight failure asserts failed diagnostics include completed stages through `stage2_stat_check`.

### 7. Wrong vs Correct

#### Wrong

```python
if mineru_failed:
    full_text, meta, raw_pdf = extract_pdf_text(...)
    write_audit_report(...)
```

#### Correct

```python
result = run_preflight_once(preflight_state, "mineru", preflight_mineru)
if not result.ok:
    failure = preflight_failure_to_audit_failure(result, retry_command, completed_stages)
    save_failed_audit_diagnostics(failure, input_path, meta={"preflight_results": [result.to_dict()]})
    return 1
```

## Scenario: Audit Artifact Outcome Types

### 1. Scope / Trigger

- Trigger: Any audit run writes user-visible formal artifacts.
- Complete, limited, and failed outcomes must be impossible to confuse by filename or report header.

### 2. Signatures

- `audit_artifact_paths(input_path, artifact_type="complete", output_path=None) -> (Path, Path, Path)`
- `audit_limited_reasons(args, meta, has_pdf_input=False) -> list[str]`
- `apply_audit_artifact_type(meta, limited_reasons) -> dict`
- `failed_audit_artifact_paths(input_path, output_dir=None, output_stem=None) -> (Path, Path)`

### 3. Contracts

- Complete successful directory artifacts:
  - `audit_report.audit.md`
  - `audit_report.audit.html`
  - `audit_report.audit.json`
- Limited successful directory artifacts:
  - `audit_report.limited.md`
  - `audit_report.limited.html`
  - `audit_report.limited.json`
- Failed directory artifacts:
  - `audit_report.failed.md`
  - `audit_report.failed.json`
- Single-file input maps to the same suffixes, for example `paper.audit.md`, `paper.limited.md`, or `paper.failed.md`.
- Report headers must include `完整审查 (complete)`, `范围受限审查 (limited)`, or failed diagnostic language that states no complete audit report was generated.

### 4. Validation & Error Matrix

- User disabled MinerU for PDF input -> limited artifact.
- User disabled reference online verification when references exist -> limited artifact.
- User disabled image semantic analysis or imagedetector when images exist -> limited artifact.
- User set any reference/image coverage limit when relevant content exists -> limited artifact, even when the explicit limit is higher than the current document count.
- User enabled LLM cache-only mode -> limited artifact.
- LLM chunk coverage is partial -> limited artifact.
- Critical preflight failure -> failed artifact, not limited and not complete.

### 5. Good/Base/Bad Cases

- Good: A directory run with all required services writes `audit_report.audit.md`.
- Base: A directory run with `--no-reference-online` and parsed references writes `audit_report.limited.md`.
- Bad: A limited run writes `audit_report.audit.md` with only a warning in the body.

### 6. Tests Required

- Unit test complete and limited directory path mapping.
- Unit test single-file path mapping.
- Unit test explicit `--output` normalization strips existing `.audit`, `.limited`, or `.failed` suffix before applying the final outcome suffix.
- Renderer test asserts complete and limited headers are visible in Markdown and HTML.
- Unit test explicit reference/image limits are recorded as limited reasons.

### 7. Wrong vs Correct

#### Wrong

```python
output_path = input_path / "audit_report.audit.md"
```

#### Correct

```python
limited_reasons = audit_limited_reasons(args, meta, has_pdf_input=has_pdf_input)
apply_audit_artifact_type(meta, limited_reasons)
output_path, html_output_path, json_path = audit_artifact_paths(input_path, meta["artifact_type"])
```

## Scenario: Full Reference and Image Coverage Defaults

### 1. Scope / Trigger

- Trigger: A successful audit contains parseable references or detectable images.
- Complete reports require full default coverage for reference online lookup, image semantic analysis, and imagedetector.
- User-selected caps are allowed for debugging or constrained runs, but they produce limited artifacts.

### 2. Signatures

- `audit_references(references_text, online=False, online_limit=None, timeout=10, cache=None) -> dict`
- `build_image_audit(input_path, ..., limit=None, semantic_limit=None, detector_limit=None, ...) -> dict`
- `audit_limited_reasons(args, meta, has_pdf_input=False) -> list[str]`
- `coverage_blocking_failure(meta) -> (capability, message, details)`

### 3. Contracts

- `None` coverage limits mean "all available items"; integer limits are explicit user caps.
- All parseable references are queued for online lookup by default when reference online verification is enabled.
- All detectable images are queued for image semantic analysis and imagedetector by default when those capabilities are enabled.
- No references found must not make a run limited or failed.
- No detectable images found must not make a run limited or failed.
- User-provided caps for reference lookup, local image audit, image semantic analysis, or imagedetector must be visible in `limited_reasons`.
- If relevant content exists and every attempted result for a critical lookup/detection service fails with provider errors, the run must write failed diagnostics instead of a complete or limited report.

### 4. Validation & Error Matrix

- References exist, default online lookup succeeds for all -> eligible for complete.
- References exist, `--reference-online-limit N` was provided -> limited artifact.
- Images exist, default semantic and imagedetector calls cover all images -> eligible for complete.
- Images exist, any image audit/semantic/detector limit was provided -> limited artifact.
- References exist, all online lookup attempts return `online_status: "error"` -> failed artifact with `capability == "reference_lookup"`.
- Images exist, all semantic attempts return `status: "error"` -> failed artifact with `capability == "image_semantic"`.
- Images exist, all imagedetector attempts return `status: "error"` -> failed artifact with `capability == "image_detector"`.

### 5. Good/Base/Bad Cases

- Good: A paper with 120 references and no explicit cap queues all 120 references for online lookup.
- Good: A paper with 40 detectable images and no explicit cap queues all 40 images for semantic analysis and imagedetector.
- Base: A run with no parsed references and no images can still produce a complete artifact if the remaining complete criteria pass.
- Bad: A default run silently checks only the first 50 references or first 12 images and labels the report complete.
- Bad: All reference provider calls fail, but the audit still writes `*.audit.md`.

### 6. Tests Required

- Unit test default reference online lookup checks every parsed reference.
- Unit test default image audit checks every detected image for semantic analysis and imagedetector.
- Unit test explicit limits produce limited reasons even when the cap is above the current content count.
- Unit test no references and no images do not create coverage blocking failures.
- Unit test service-wide reference, image semantic, and imagedetector failures return failed capabilities.

## Scenario: Reference Official-Site Fallback

### 1. Scope / Trigger

- Trigger: `verify_reference_online` cannot verify a parsed reference through the primary scholarly sources.
- The verifier must try DOI landing pages and publisher/official journal search pages before returning `not_found`, `weak`, or `error`.
- This is especially important for references without DOI text, conference abstracts, and OCR-damaged titles.

### 2. Signatures

- `lookup_official_site_reference(ref, timeout=10) -> list[dict]`
- `_official_site_search_urls(ref) -> list[(label, url)]`
- `_official_page_matches_reference(ref, page_text) -> bool`

### 3. Contracts

- The primary source order remains Crossref, OpenAlex, and PubMed.
- When no primary match reaches `verified`, the verifier tries:
  - DOI landing page for references with DOI text.
  - Known publisher or official journal search pages inferred from `container_hint`, title, and raw reference text.
  - OCR-tolerant title variants, including the title tail without the first word for long titles.
- Official-site matches must be scored only when the page text contains enough title tokens and a compatible year when available.
- A DOI landing page with an exact DOI match can verify the DOI even if metadata APIs fail.
- If all primary sources fail with provider errors, do not mask the outage by silently degrading; keep `online_status == "error"` unless another source returns a real match.

### 4. Validation & Error Matrix

- Title has a damaged first word but an official publisher page contains the intact title -> `verified`.
- Reference lacks DOI but official journal search returns a page containing title tokens and year -> `verified`.
- Official site is unavailable while primary sources returned no match -> `not_found` or partial source error, not a fabricated match.
- All primary sources raise provider errors and no official match exists -> `error`.

### 5. Tests Required

- Unit test official-site fallback verifies a reference when Crossref/OpenAlex/PubMed return no matches.
- Unit test OCR-damaged first title word still searches with a title-tail variant.
- Unit test publisher rule coverage for domain-specific official sites that appear in real fixtures.

## Scenario: Per-Run Workspace

### 1. Scope / Trigger

- Trigger: Each CLI audit run starts after input path validation.
- The root output directory keeps latest report shortcuts, while `.paper_audit_runs/<run_id>/` stores immutable per-run evidence.

### 2. Signatures

- `create_run_workspace(input_path, output_dir, output_stem) -> dict`
- `record_run_workspace_json(workspace, name, payload) -> Path | None`
- `record_run_workspace_artifacts(workspace, outcome, root_paths, meta=None) -> Path | None`

### 3. Contracts

- Workspace layout:
  - `workspace.json`
  - `input_manifest.json`
  - `cache_use.json`
  - `preflight.json`
  - `report_outcome.json`
  - `artifacts/`
  - `raw/`
  - `intermediate/`
- `report_outcome.json` must record:
  - `run_id`
  - `outcome`
  - `root_shortcuts`
  - `workspace_artifacts`
  - `meta`
- Root report files remain the latest shortcuts. Workspace artifact files are copied snapshots and must not be overwritten by later runs.

### 4. Validation & Error Matrix

- Missing workspace dict -> recorder returns `None`.
- Missing root artifact path -> recorder skips it rather than failing the audit.
- Multiple runs with the same input/output stem -> distinct `run_id` values and distinct workspace directories.

### 5. Good/Base/Bad Cases

- Good: Failed preflight writes root `paper.failed.*` and copies both files into `.paper_audit_runs/<run_id>/artifacts/`.
- Base: Successful audit writes root latest `audit_report.audit.*` or `audit_report.limited.*` and records those root shortcuts in `report_outcome.json`.
- Bad: Writing run-specific intermediate metadata only into the shared resume cache.

### 6. Tests Required

- Unit test two workspaces for the same input have different `run_id` values.
- Unit test artifact recording copies an existing root report and records both root and workspace paths.
- CLI smoke for a failed preflight verifies workspace manifest and outcome files exist.

### 7. Wrong vs Correct

#### Wrong

```python
_json_save(resume_dir / "report_outcome.json", payload)
```

#### Correct

```python
run_workspace = create_run_workspace(input_path, output_dir, output_stem)
record_run_workspace_artifacts(run_workspace, "failed", [md_path, json_path], meta=meta)
```

## Scenario: External Capability Adapters

### 1. Scope / Trigger

- Trigger: Any code path calls an external audit capability such as MinerU, text LLM, reference lookup, image semantic analysis, or imagedetector.
- New tests should depend on adapter injection or fake adapters, not monkeypatching module-global service functions.

### 2. Signatures

- `AdapterResult.success(value=None, details=None)`
- `AdapterResult.failure(error_class, message, details=None)`
- `AdapterResult.skipped(reason, message, details=None)`
- `default_audit_adapters() -> AuditAdapters`
- `fake_audit_adapters(scenario="success", values=None) -> AuditAdapters`

### 3. Contracts

- `AdapterResult.status` is one of:
  - `success`
  - `failure`
  - `skipped`
- `AdapterResult.error_class` is required for `failure` and `skipped`.
- Fake scenarios:
  - `success`
  - `auth_failure`
  - `network_failure`
  - `rate_limit`
  - `schema_error`
  - `unsupported_content`
- Production adapters wrap existing implementation functions and accept injected callables for deterministic tests.

### 4. Validation & Error Matrix

- Fake `auth_failure` -> `provider_auth_failed`
- Fake `network_failure` -> `provider_unavailable`
- Fake `rate_limit` -> `provider_rate_limited`
- Fake `schema_error` -> `schema_error`
- Fake `unsupported_content` -> `skipped` with `unsupported_content`

### 5. Good/Base/Bad Cases

- Good: A unit test creates `ProductionTextLLMAdapter(review_func=lambda ...)` and asserts adapter behavior without monkeypatching `call_llm`.
- Base: A fake adapter returns deterministic `AdapterResult.failure(...)`.
- Bad: A new test monkeypatches `paper_audit.call_llm` or `paper_audit.call_glm_image_semantics` when an adapter injection point would work.

### 6. Tests Required

- Unit test structured `success` / `failure` / `skipped` serialization.
- Unit test every fake scenario maps to the expected `error_class`.
- Unit test production wrappers accept injected callables and preserve structured results.

### 7. Wrong vs Correct

#### Wrong

```python
monkeypatch.setattr(paper_audit, "call_llm", lambda text: "ok")
```

#### Correct

```python
adapter = ProductionTextLLMAdapter(review_func=lambda text, chunk_info=None: "ok")
assert adapter.review("body").ok
```

## Scenario: Fake Adapter E2E Harness

### 1. Scope / Trigger

- Trigger: A test must prove full artifact behavior without API keys, network, or third-party services.
- Use `run_adapter_e2e_audit(...)` with fake adapters to exercise complete and failed artifact paths.

### 2. Signatures

- `run_adapter_e2e_audit(input_path, adapters, output_dir=None, text=..., references_text="", image_paths=None) -> dict`
- `adapter_failure_to_audit_failure(capability, result, retry_command, completed_stages) -> AuditFailure`

### 3. Contracts

- Complete outcome returns:
  - `outcome: "complete"`
  - `md_path`
  - `html_path`
  - `json_path`
  - `workspace`
- Failed outcome returns:
  - `outcome: "failed"`
  - `capability`
  - `md_path`
  - `json_path`
  - `workspace`
- The harness must use renderers and artifact writers, not ad hoc test-only files.

### 4. Validation & Error Matrix

- Text LLM adapter review failure -> failed diagnostics with `failure.capability == "text_llm"`.
- Reference lookup failure with non-empty references -> failed diagnostics with `failure.capability == "reference_lookup"`.
- imagedetector failure with detectable image paths -> failed diagnostics with `failure.capability == "image_detector"`.
- Invalid LLM report schema -> failed diagnostics with `schema_error`.

### 5. Good/Base/Bad Cases

- Good: A fake complete run writes `audit_report.audit.md`, `audit_report.audit.html`, and `audit_report.audit.json`.
- Base: A fake failed run writes `audit_report.failed.md` and `audit_report.failed.json`.
- Bad: A test reaches out to Crossref, OpenAlex, PubMed, GLM, MinerU, imagedetector, or a real text LLM.

### 6. Tests Required

- Complete fake-adapter E2E artifact test.
- Text LLM failure fake-adapter E2E test.
- Reference lookup service failure fake-adapter E2E test.
- imagedetector failure fake-adapter E2E test.

### 7. Wrong vs Correct

#### Wrong

```python
subprocess.run(["python", "paper_audit.py", "sample.pdf"])
```

#### Correct

```python
result = run_adapter_e2e_audit(tmp_path, fake_audit_adapters())
assert result["outcome"] == "complete"
```

## Scenario: Audit Run Request And Result

### 1. Scope / Trigger

- Trigger: CLI argument values need to cross into orchestration code.
- Use structured request/result objects instead of passing raw `argparse.Namespace` deeper into new orchestration boundaries.

### 2. Signatures

- `RunRequest.from_args(args) -> RunRequest`
- `run_audit(request: RunRequest, args) -> RunResult`
- `RunResult.complete(artifact_paths, workspace=None, meta=None) -> RunResult`
- `RunResult.limited(artifact_paths, workspace=None, meta=None) -> RunResult`
- `RunResult.failed(failure, artifact_paths, workspace=None, meta=None) -> RunResult`

### 3. Contracts

- `RunRequest.input_path` is a `Path`.
- `RunResult.outcome` is one of `complete`, `limited`, or `failed`.
- `RunResult.exit_code` is `0` for complete/limited and `1` for failed.
- `RunResult.artifact_type` matches the final artifact family.

### 4. Validation & Error Matrix

- Missing `args.pdf_path` is still handled by CLI parser before `RunRequest.from_args`.
- Failed critical capability returns `RunResult.failed(...)`.
- Successful but user-limited run returns `RunResult.limited(...)`.

### 5. Good/Base/Bad Cases

- Good: `main()` maps `args` to `RunRequest` once, then returns `run_audit(request, args).exit_code`.
- Base: Existing CLI compatibility remains intact while the orchestration boundary is extracted incrementally.
- Bad: New run-level functions accept raw `argparse.Namespace` instead of `RunRequest`.

### 6. Tests Required

- Unit test `RunRequest.from_args(...)` maps representative CLI values.
- Unit test all three `RunResult` factories set outcome, artifact type, and exit code.

### 7. Wrong vs Correct

#### Wrong

```python
def run_stage(args):
    return Path(args.pdf_path)
```

#### Correct

```python
def run_stage(request: RunRequest):
    return request.input_path
```

## Scenario: Strict Evidence Schema

### 1. Scope / Trigger

- Trigger: Text LLM output is parsed for inclusion in a complete or limited audit report.
- Malformed evidence findings must not enter complete reports.

### 2. Signatures

- `EvidenceFinding`
- `AuditReportModel`
- `ReferenceAuditModel`
- `ImageAuditModel`
- `RunMetadataModel`
- `CoverageModel`
- `normalize_llm_report_schema(report, raw_output="") -> dict`
- `parse_report(content) -> dict`

### 3. Contracts

- Each LLM finding must include:
  - `verdict`
  - `source` or `source_text`
  - `evidence`
  - `reason`
  - `recommendation`
  - `confidence`
- Valid parsed reports contain normalized `checks`.
- Raw LLM responses are stored separately as `raw_content` in chunk caches.
- Valid normalized reports do not embed raw response text as finding evidence.

### 4. Validation & Error Matrix

- `checks` missing -> treated as empty list.
- `checks` not a list -> `parse_error` + `schema_error`.
- Finding missing required field -> `parse_error` + `schema_error`.
- Invalid confidence -> `parse_error` + `schema_error`.
- Truncated JSON with partial top-level fields -> `parse_error` + `schema_error` and `partial_fields`.
- Retry exhaustion -> failed diagnostics, not partial complete report.

### 5. Good/Base/Bad Cases

- Good: A finding with evidence/source/reason/recommendation/verdict/confidence is normalized and can be rendered.
- Base: A report with `checks: []` is valid.
- Bad: A finding with only `verdict` and `evidence` is accepted into `audit_report.audit.md`.

### 6. Tests Required

- Unit test valid strict finding normalizes `source` and numeric `confidence`.
- Unit test missing fields produce schema error.
- Unit test truncated JSON is preserved as diagnostics but rejected from complete reports.
- Fake-adapter E2E test invalid LLM schema writes failed diagnostics.

### 7. Wrong vs Correct

#### Wrong

```python
return json.loads(content)
```

#### Correct

```python
parsed = json.loads(content)
return normalize_llm_report_schema(parsed, raw_output=content)
```

## Scenario: Versioned Risk Rules

### 1. Scope / Trigger

- Trigger: A normalized audit report is about to be rendered or serialized.
- LLM output can explain findings but must not decide final risk level or evidence risk score.

### 2. Signatures

- `RISK_RULE_VERSION`
- `apply_risk_rules(report, stat_result=None, image_audit=None) -> dict`

### 3. Contracts

- Final `risk_level` values are:
  - `低`
  - `中`
  - `高`
  - `严重证据冲突`
- Final user-visible score field is `detection_score`, rendered as `证据风险分`.
- Rule output must include:
  - `rule_version`
  - `score_breakdown.rule_version`
  - `score_breakdown.red_flags`
  - `score_breakdown.evidence_warnings`
  - `score_breakdown.extraction_warnings`
  - `score_breakdown.image_detector_high`
  - `score_breakdown.stat_adjustments`
  - `score_breakdown.raw_score`
- Run metadata records `risk_rule_version`.

### 4. Validation & Error Matrix

- LLM says high but no findings -> rules produce `低`.
- imagedetector high score alone -> rules may produce `中`, never `严重证据冲突`.
- Multiple red flags plus evidence warnings -> rules may produce `严重证据冲突`.
- OCR/table extraction warnings are counted separately from evidence warnings.

### 5. Good/Base/Bad Cases

- Good: Final report records `risk_rules_v1` and a score breakdown.
- Base: No findings and no supporting signals produces score `0` and risk `低`.
- Bad: A raw LLM `risk_level: 高` is rendered directly without rule evaluation.

### 6. Tests Required

- Unit test LLM risk override.
- Unit test imagedetector cap.
- Unit test severe evidence conflict.
- Renderer smoke that rule version appears in Markdown/HTML.

### 7. Wrong vs Correct

#### Wrong

```python
risk = report["risk_level"]
```

#### Correct

```python
report = apply_risk_rules(report, stat_result=stat_result, image_audit=meta.get("image_audit"))
risk = report["risk_level"]
```

## Scenario: Paper Resource Availability Audit

### 1. Scope / Trigger

- Trigger: A formal audit text mentions code repositories, data repositories, deployed calculators, Streamlit apps, or other online paper resources.
- These resources must be extracted from the full paper text and recorded in formal Markdown, HTML, and JSON artifacts.
- Resource availability checking is online by default. Disabling it is allowed only as a range-limited/debug run.

### 2. Signatures

- `extract_paper_resources(text) -> list[dict]`
- `verify_resource_availability(resource, timeout=10) -> dict`
- `audit_resources(text, online=True, timeout=10, cache=None) -> dict`
- `format_resource_audit_markdown(resource_audit) -> list[str]`
- `format_resource_audit_html(resource_audit) -> str`
- CLI:
  - `--no-resource-online`
  - `--resource-timeout <seconds>`

### 3. Contracts

- `resource_audit` fields:
  - `status`: `ok`, `needs_review`, or `error`
  - `resource_count`
  - `online_enabled`
  - `online_checked`
  - `issues`
  - `resources`
  - `note`
- Each resource contains:
  - `url`
  - `type`: `code_repository`, `data_repository`, or `deployed_resource`
  - `context`
  - `availability`
- Each availability result contains:
  - `status`: `available`, `unavailable`, `access_restricted`, `malformed`, `error`, or `skipped`
  - `http_status`
  - `problem`
  - `message`
- Successful JSON payloads must include both `meta.resource_audit` and top-level `resource_audit`.
- Markdown and HTML reports must include a "代码仓库与在线资源可用性校检" section when `resource_audit` exists.

### 4. Validation & Error Matrix

- `https://github.com/...` -> `type == code_repository`
- `https://*.streamlit.app/...` -> `type == deployed_resource`
- GEO/GDC/Zenodo/Figshare/OSF style links -> `type == data_repository`
- `htps://...` or unsupported schemes -> `availability.status == malformed`
- HTTP 401/403 -> `access_restricted`
- HTTP 404/410 -> `unavailable`
- Provider/network exception without HTTP status -> `error`
- All checked resources ending in `error` -> `coverage_blocking_failure(...)` returns `resource_availability`
- User passes `--no-resource-online` with resources present -> limited artifact reason is recorded.

### 5. Good/Base/Bad Cases

- Good: A paper with GitHub and Streamlit links records both in Markdown, HTML, JSON, and checks their availability.
- Base: A paper with no resource links records zero resources and remains eligible for complete if other coverage requirements pass.
- Bad: A malformed Streamlit URL is ignored silently or merged into reference checking only.
- Bad: All resource availability requests fail due provider/network errors but the run still writes `*.audit.*`.

### 6. Tests Required

- Unit test resource extraction classifies GitHub, Streamlit, and malformed URLs.
- Renderer test asserts Markdown and HTML resource sections are present.
- Unit test `--no-resource-online` creates a limited reason when resources exist.
- Unit test service-wide resource provider errors are returned by `coverage_blocking_failure`.

### 7. Wrong vs Correct

#### Wrong

```python
resources = re.findall(r"https?://\S+", text)
# only mention them in prose, no structured report field
```

#### Correct

```python
resource_audit = audit_resources(full_text, online=True, timeout=args.resource_timeout, cache=cache)
meta["resource_audit"] = resource_audit
json_payload["resource_audit"] = resource_audit
```
