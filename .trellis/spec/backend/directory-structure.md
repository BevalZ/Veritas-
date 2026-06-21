# Directory Structure

> How backend code is organized in this project.

---

## Overview

The project is migrating from a single historical script into a package while
preserving the public `paper_audit.py` command and import surface. New backend
boundaries should live under `veritas/`; the compatibility script should stay
thin.

---

## Directory Layout

```
paper_audit.py          # Thin compatibility entry point for CLI/import users
veritas/
├── legacy.py           # Current implementation during incremental migration
├── adapters.py         # External provider adapter exports
├── artifacts.py        # Formal artifact path and outcome helpers
├── cli.py              # CLI entry point boundary
├── config.py           # Runtime configuration boundary
├── cross_file_consistency.py # Cross-file consistency audit and rendering helpers
├── desktop_gui.py      # Desktop GUI helper boundary
├── evidence_chain.py   # Evidence-chain audit and evidence-cluster helpers
├── evidence_rendering.py # Evidence excerpt/table rendering helpers
├── external_timeout.py # Timeout helpers for external capability calls
├── failed_diagnostics.py # Stable failed-audit payload, rendering, and conversion helpers
├── followups.py       # PubPeer/comment and journal-letter draft workflow helpers
├── html_utils.py       # HTML escaping and script-safe JSON helpers
├── http_client.py      # Shared low-level HTTP request helper
├── image_audit_builder.py # Image audit orchestration across local checks/providers
├── image_cache.py      # Image audit cache key and fingerprint helpers
├── image_collection.py # Local image discovery and MinerU zip image extraction helpers
├── image_detector_provider.py # imagedetector.com provider flow
├── image_local_analysis.py # Local image sanity checks before provider review
├── image_payloads.py   # Local image payload preparation helpers
├── image_reporting.py  # Image audit report and review-manifest rendering helpers
├── image_results.py    # Image provider response normalization helpers
├── image_semantic_provider.py # OpenAI-compatible image semantic provider flow
├── image_selection.py  # Image audit selection and cache-flush helpers
├── limit_utils.py      # Shared item-limit normalization helpers
├── local_analysis.py   # Local statistics and text chunking helpers
├── markdown_utils.py   # Shared Markdown table rendering helpers
├── mineru_text.py      # MinerU structured content-list text formatting helpers
├── models.py           # Stable dataclass/report models and model conversion
├── paper_identity.py   # Best-effort article identity extraction helpers
├── pattern_updates.py  # PubPeer-to-fraud-pattern knowledge-base update helpers
├── preflight.py        # Critical capability preflight boundary
├── project_files.py    # Project file discovery and run metadata helpers
├── reference_audit.py  # Reference plausibility audit orchestration
├── reference_online.py # Crossref/OpenAlex/PubMed/official-site reference lookups
├── reference_parsing.py # Reference section parsing and query-building helpers
├── reference_reporting.py # Reference audit Markdown/HTML rendering helpers
├── renderers.py        # Markdown/HTML renderer boundary
├── report_action_context.py # HTML follow-up/report action context helpers
├── report_action_panel.py # HTML follow-up/report action panel rendering helpers
├── report_action_service.py # Local report action service health/startup helpers
├── report_checks.py    # Deterministic LLM finding scoring/display helpers
├── report_html_fragments.py # Small HTML report status fragment builders
├── report_html_sections.py # HTML report LLM check section builders
├── report_markdown.py  # Top-level Markdown report composition
├── review_overview.py  # Review overview and action-priority rendering helpers
├── resource_availability.py # Online resource availability checks
├── resource_parsing.py # Resource URL extraction and classification helpers
├── resource_reporting.py # Resource audit Markdown/HTML rendering helpers
├── risk_rule_helpers.py # Shared risk scoring/merge helpers for rules/rendering
├── risk_rules.py       # Versioned final risk scoring boundary
├── run.py              # Run request/result and orchestration boundary
├── run_failures.py     # Failed run artifact recording and RunResult helpers
├── run_logging.py      # Run log, progress, resume-event, and MinerU artifact helpers
├── text_extraction.py  # Local standard-library text extraction fallbacks
├── text_utils.py       # Shared text shortening and token similarity helpers
├── versions.py         # Prompt/schema/adapter/risk-rule version constants
├── web_runner.py       # Local Web Runner helper boundary
├── workspace.py        # Per-run workspace boundary
└── zhuque.py           # Tencent Zhuque clipboard/browser helper flow
└── file_utils.py       # Shared safe-name and JSON file helpers
└── report_schema.py    # Strict LLM evidence schema parser
└── retry_commands.py   # Retry command builders for failed diagnostics
└── runtime_metadata.py # Runtime clock metadata for reports/rules
tests/
└── test_core.py        # Core unit and smoke coverage
```

---

## Module Organization

- Keep `paper_audit.py` as a compatibility entry point only.
- During migration, `veritas/legacy.py` may hold the full implementation so old
  tests and monkeypatches keep working.
- Add new code to the narrow `veritas/*` boundary that owns the concept:
  config, preflight, run, workspace, models, risk_rules, adapters, artifacts,
  failed_diagnostics, or renderers.
- Thin boundary modules that still delegate to `veritas.legacy` should import
  legacy inside the delegating function, not at module import time, unless a
  tested compatibility contract requires object identity.
- Production adapters for provider functions that have not moved out of legacy
  should use call-time legacy proxies so constructing `default_audit_adapters()`
  does not import `veritas.legacy`.
- Renderer-facing code should accept stable dataclass models or dictionaries and
  normalize at the renderer boundary.
- Avoid adding new orchestration logic directly to `paper_audit.py`.

---

## Naming Conventions

- Package modules use lowercase snake_case filenames.
- Boundary modules should expose a small `__all__` list.
- Compatibility exports should re-export existing implementation symbols rather
  than duplicating behavior.

---

## Examples

- `paper_audit.py` aliases `veritas.legacy` for historical `import paper_audit`
  compatibility while still running `veritas.legacy.main()` as a script.
- `veritas/models.py` owns `AuditFailure`, `AuditReportModel`,
  `EvidenceFinding`, and related lightweight dataclasses; `paper_audit` keeps
  compatibility by re-exporting the same class objects through `veritas.legacy`.
- `veritas/file_utils.py` owns `_safe_name`, `_json_load`, `_json_save`, and
  `_load_merged_json_dicts`; these remain re-exported through `paper_audit` for
  compatibility with existing tests and local scripts.
- `veritas/report_schema.py` owns strict LLM evidence schema parsing and
  normalization; `paper_audit` keeps compatibility by re-exporting the same
  parser function objects through `veritas.legacy`.
- `veritas/retry_commands.py` owns retry command builders used by failed
  diagnostics; `paper_audit` keeps compatibility by re-exporting the same
  function objects through `veritas.legacy`.
- `veritas/runtime_metadata.py` owns runtime clock metadata helpers used by
  reports and deterministic date checks; `paper_audit` keeps compatibility by
  re-exporting the same function objects through `veritas.legacy`.
- `veritas/artifacts.py` owns formal audit artifact path, explicit-output
  normalization, failed artifact option mapping, limited-outcome, and
  coverage-blocking helpers; `paper_audit` keeps compatibility by re-exporting
  the same function objects through `veritas.legacy`.
- `veritas/failed_diagnostics.py` owns stable failed-audit JSON payload,
  Markdown/HTML diagnostic rendering, failed artifact writes, and
  failure-to-`AuditFailure` conversion helpers.
- `veritas/html_utils.py` owns HTML escaping and script-safe JSON helpers used
  by renderers; these remain re-exported through `paper_audit` for
  compatibility while renderer extraction continues.
- `veritas/http_client.py` owns the shared low-level HTTP request helper and
  default browser-like user agent. Provider-specific request construction,
  polling, retry behavior, and response interpretation remain outside this
  boundary.
- `veritas/image_audit_builder.py` owns image audit orchestration across local
  image checks, image semantic analysis, imagedetector calls, and provider cache
  flushing. It should stay namespace-aware while compatibility wrappers live in
  `veritas.legacy`, so tests and user scripts can still monkeypatch collection,
  local analysis, provider calls, cache keys, and priority ordering.
- `veritas/image_cache.py` owns deterministic image file fingerprints and image
  semantic cache key construction. Namespace-aware helpers let `veritas.legacy`
  preserve historical monkeypatch behavior for image semantic endpoint, model,
  and cache-version globals.
- `veritas/image_collection.py` owns local filesystem image discovery, path
  de-duplication, image output-directory selection, PDF image extraction,
  MinerU ZIP image extraction, newest-per-source MinerU ZIP selection, and
  namespace-aware image collection. It must not call image providers;
  `veritas.legacy` may wrap namespace-aware helpers so historical monkeypatches
  of image size/extension constants and collector hooks continue to affect
  collection.
- `veritas/image_detector_provider.py` owns the imagedetector.com upload and
  detection HTTP flow. It should stay namespace-aware while compatibility
  wrappers live in `veritas.legacy`, so tests and user scripts can still
  monkeypatch `_http_request`, payload preparation, timeout behavior, and
  provider URL constants.
- `veritas/image_local_analysis.py` owns local image sanity checks before
  provider review. It may use optional Pillow for local dimensions/statistics
  but must not call image providers; legacy wrappers preserve `MIN_IMAGE_BYTES`
  monkeypatch behavior.
- `veritas/image_payloads.py` owns local image-to-data-URL conversion and
  imagedetector upload-file preparation. It may use optional Pillow for local
  resizing/conversion but must not call image providers or network services.
- `veritas/image_reporting.py` owns deterministic rendering of image audit
  display summaries, Markdown/HTML report sections, and the standalone
  `image_ai_review_manifest.html` review checklist. Provider calls and image
  collection stay outside this boundary.
- `veritas/image_results.py` owns deterministic normalization of image semantic
  model responses, imagedetector responses, provider timeout result payloads,
  and JSON-object extraction from model text. It must not perform network I/O.
- `veritas/image_semantic_provider.py` owns the OpenAI-compatible image
  semantic HTTP flow. It should stay namespace-aware while compatibility
  wrappers live in `veritas.legacy`, so tests and user scripts can still
  monkeypatch `_http_request`, payload preparation, timeout behavior, result
  normalizers, and provider endpoint/model constants.
- `veritas/image_selection.py` owns deterministic image audit sorting,
  semantic/detector priority keys, and cache flush callback handling. It must
  not collect images or call providers.
- `veritas/limit_utils.py` owns shared deterministic item-limit normalization
  used by reference and image audit flows.
- `veritas/evidence_rendering.py` owns deterministic evidence excerpt cleanup,
  MinerU table marker removal, Markdown/HTML table parsing, data-table HTML
  rendering, and compact evidence summary HTML. It must remain provider-free
  because MinerU extraction, reference/resource sections, and report rendering
  all reuse it.
- `veritas/external_timeout.py` owns signal-based timeout wrappers for external
  capability calls that may ignore socket timeouts. It must not know about any
  specific provider payload or response schema.
- `veritas/text_utils.py` owns shared text shortening, short text fingerprint,
  and token similarity helpers used by follow-up generation, risk rules,
  references, cache keys, evidence IDs, and renderers.
- `veritas/local_analysis.py` owns local non-provider analysis helpers:
  Benford/numeric extraction, local statistical checks, and structure-aware text
  chunking. These helpers must remain deterministic and must not call LLMs or
  network providers.
- `veritas/markdown_utils.py` owns shared deterministic Markdown rendering
  helpers such as table-cell escaping, used across report sections to avoid
  divergent escaping behavior.
- `veritas/mineru_text.py` owns deterministic formatting of MinerU
  `content_list` JSON into audit-oriented text blocks, including nested content
  flattening and table markdown normalization. MinerU API upload, polling, and
  ZIP download logic remain outside this boundary.
- `veritas/project_files.py` owns supported text-file extension constants,
  project directory file discovery/classification, optional dependency checks,
  extracted file-body cleanup, main-paper scoring, missing metadata detection,
  and run metadata normalization. Keep this boundary deterministic and
  filesystem-local; provider extraction remains elsewhere.
- `veritas/reference_audit.py` owns reference plausibility audit orchestration,
  including offline issue aggregation, online verification fan-out, cache reuse,
  and final status selection. It should stay namespace-aware while
  compatibility wrappers live in `veritas.legacy`, so tests and user scripts can
  still monkeypatch parsers, online lookup, cache keys, runtime clock, and text
  shortening.
- `veritas/reference_online.py` owns Crossref, OpenAlex, PubMed, DOI landing
  page, and official publisher-site network lookups plus multi-source online
  verification status selection. It should stay namespace-aware while
  compatibility wrappers live in `veritas.legacy`, so tests and user scripts can
  still monkeypatch `_http_request`, `_reference_get_json`, lookup functions,
  query builders, and match scoring.
- `veritas/cross_file_consistency.py` owns deterministic cross-file text
  segmentation, sample-size/group-label/supplement-reference consistency
  findings, and Markdown/HTML rendering for the cross-file audit section. It
  must remain provider-free and should consume already-extracted file entries
  rather than reading project files itself.
- `veritas/evidence_chain.py` owns deterministic Methods/Results/Abstract
  claim-chain findings, evidence key extraction, evidence item normalization,
  evidence-cluster aggregation, and Markdown/HTML rendering for the evidence
  chain section. It may aggregate existing report, reference, resource, image,
  statistics, and cross-file audit payloads, but must not call providers.
- `veritas/paper_identity.py` owns best-effort article title, journal, and
  author extraction for follow-up draft context. It should stay deterministic
  and may reuse evidence cleanup helpers, but must not call providers.
- `veritas/pattern_updates.py` owns the `--update-patterns` PubPeer-comment
  knowledge-base update flow, including prompt construction, LLM response JSON
  extraction, duplicate ID filtering, and `fraud_patterns.json` writes.
  `veritas.legacy` should wrap it with globals so historical monkeypatches of
  LLM endpoint/model/key, `urllib.request`, and `FRAUD_PATTERNS_PATH` continue
  to affect the CLI helper.
- `veritas/reference_parsing.py` owns deterministic reference-section splitting,
  merging separately extracted directory reference-file text into the reference
  audit input, offline bibliography parsing, DOI/title/author/container/year
  hint extraction, author similarity, reference query/cache-key construction,
  official-site search URL construction, HTML cleanup/title extraction,
  official-page match heuristics, Crossref/OpenAlex/PubMed response
  normalization, and deterministic online-match scoring. Crossref, OpenAlex,
  PubMed, and official-site network lookups remain outside this boundary.
- `veritas/reference_reporting.py` owns deterministic reference audit issue
  labels, online summary text, Markdown tables, and HTML cards. Reference
  parsing and online lookup remain outside this boundary.
- `veritas/report_action_context.py` owns deterministic construction of the
  saved-report context consumed by HTML PubPeer/comment and journal-letter
  actions. It may aggregate already-computed audit payloads, but must not start
  local services, call providers, or perform network I/O.
- `veritas/report_action_panel.py` owns deterministic HTML rendering and
  browser action-script generation for the saved-report PubPeer/comment and
  journal-letter action panel. Local action service process management and HTTP
  handlers remain outside this boundary.
- `veritas/report_action_service.py` owns local report action service health
  checks, background startup, HTML artifact opening, and shared JSON request
  parsing/response payloads plus the local HTTP action-service handler.
  `veritas.legacy` should wrap namespace-aware service helpers so historical
  monkeypatches of service health, subprocess spawning, follow-up generation,
  and timeout globals continue to affect GUI/report-action behavior.
- `veritas/report_checks.py` owns deterministic LLM finding suspicion scoring,
  source tags, source/reason extraction, merged-finding summary HTML, and check
  sort/verdict helpers shared by report rendering and evidence-chain clustering.
  It must remain provider-free and must not call text LLMs or external services.
- `veritas/report_html_fragments.py` owns top-level HTML report fragments such
  as limited notices, chunk metadata, number-consistency rows, LLM coverage
  banners, score breakdown text, document head/CSS shell split into base CSS
  and compact-skin overrides, body/header/stat/footer shell, and the namespace-aware render context used by that shell. It should stay
  namespace-aware while compatibility wrappers live in `veritas.legacy`, so
  tests and user scripts can still monkeypatch HTML escaping, runtime clock,
  version constants, and section renderers.
- `veritas/report_html_sections.py` owns HTML report sections derived from LLM
  checks: parse-error output, top suspicious evidence cards, all-checks table,
  per-finding detail cards, and conclusion text. It should stay
  namespace-aware while compatibility wrappers live in `veritas.legacy`, so
  tests and user scripts can still monkeypatch evidence renderers, check
  helpers, HTML escaping, and text shortening.
- `veritas/report_markdown.py` owns top-level Markdown report composition,
  including metadata header line construction, local statistics table, LLM
  finding summaries, and aggregation of already-rendered audit sections. It should stay
  namespace-aware while compatibility wrappers live in `veritas.legacy`, so
  tests and user scripts can still monkeypatch section renderers, check
  helpers, version constants, runtime clock, and metadata normalization.
- `veritas/zhuque.py` owns the Tencent Zhuque AI text detector helper flow:
  bounded text copy, cross-platform clipboard commands, browser launch, and
  desktop/terminal user prompts. It should stay namespace-aware while
  compatibility wrappers live in `veritas.legacy`, so tests and user scripts can
  still monkeypatch platform, subprocess, browser, clipboard, and input hooks.
- `veritas/review_overview.py` owns deterministic audit action-priority
  summaries and review-overview Markdown/HTML rendering. It may aggregate
  existing report, statistics, reference, resource, cross-file, evidence-chain,
  and image audit payloads, but must remain provider-free.
- `veritas/resource_parsing.py` owns deterministic extraction, cleanup,
  context capture, and classification of code/data/deployed-resource URLs from
  paper text. Resource availability network checks remain outside this boundary.
- `veritas/resource_availability.py` owns online availability checks for code,
  data, and deployed-resource URLs plus namespace-aware resource audit helpers.
  `veritas.legacy` should wrap these helpers with its globals so historical
  monkeypatches of `verify_resource_availability` and `_http_request` continue
  to affect audit behavior.
- `veritas/resource_reporting.py` owns deterministic resource audit status
  labels and Markdown/HTML report sections.
- `veritas/followups.py` owns PubPeer/comment and journal-letter language,
  tone, article-identity, issue-normalization, context-building, prompt
  construction, draft artifact load/save, and namespace-aware generation
  helpers. `veritas.legacy` may wrap namespace-aware functions with its own
  globals so historical `paper_audit.generate_followup_draft` monkeypatch
  behavior remains compatible.
- `veritas/versions.py` owns prompt, schema, adapter, and risk-rule version
  constants; compatibility modules should import these constants rather than
  redefining them.
- `veritas/config.py` owns runtime configuration loading/application helpers.
  Namespace-aware helpers let `veritas.legacy` preserve historical global
  monkeypatch behavior without making `veritas.config` import legacy.
- `veritas/desktop_gui.py` owns desktop GUI helper functions that do not require
  the Tk application class: labels, config snapshots, progress parsing, artifact
  preview, run summaries, and namespace-aware config/follow-up actions.
  `veritas.legacy` may keep `DesktopGuiApp` and wrap namespace-aware helpers
  with its globals while the GUI class is still in the compatibility layer.
- `veritas/production_adapters.py` may still call legacy provider functions
  that have not been extracted, but those calls should resolve legacy only when
  the provider method is invoked.
- `veritas/risk_rule_helpers.py` owns extraction-limited classification,
  OCR/table red-flag downgrade, check similarity/merge, and merged
  summary/conclusion helpers shared by risk scoring and renderers. Runtime-year
  future-publication checks also live there; legacy callers pass the current
  runtime year explicitly to preserve compatibility with existing monkeypatches.
- `veritas/risk_rules.py` owns `apply_risk_rules` and `merge_chunk_reports`;
  `veritas.legacy` re-exports the same function objects for `paper_audit`
  compatibility.
- `veritas/renderers.py` accepts `AuditReportModel` / `EvidenceFinding` and
  converts them before lazily delegating to the existing Markdown and HTML
  renderers.
- `veritas/run.py` exposes the run orchestration boundary without requiring
  callers to import the legacy module directly; the legacy run engine is loaded
  only when `run_audit(...)` is called.
- `veritas/run_failures.py` owns failed-run artifact/result helpers that save
  failed diagnostics through injected functions, record failed workspace
  artifacts, and build `RunResult.failed` payloads. Keep this boundary
  orchestration-local and provider-free.
- `veritas/run_logging.py` owns local run-output helpers: output base
  selection, tee logging, resume event JSONL writes, progress printing, LLM
  cache-read policy, text-LLM stage chunk/cache planning, text-LLM cache
  payload construction, text-LLM chunk cache read-state events, text-LLM
  failure cache save events, text-LLM retry-start/retry-failure/all-failed
  summaries, text-LLM cache-only failure conversion, text-LLM merge-completion
  details, text-LLM coverage metadata, text-LLM partial-report warning application, extraction-cache
  matching/state normalization/payload construction/save-event recording,
  online-check cache path/state/save-event construction, image-audit cache
  path/state/save-callback construction, run-summary input/route/scope helpers,
  workspace input and cache-use manifest
  construction, preflight workspace/resume-event recording, and saved MinerU
  URL/ZIP artifacts. It should stay filesystem-local and must not call
  providers.
- `veritas/text_extraction.py` owns local standard-library text extraction
  fallbacks such as raw PDF stream text extraction. It must not call MinerU,
  LLMs, or network providers.
- `veritas/web_runner.py` owns local Web Runner helper functions that do not
  require the `WebRunnerState` class: run timestamps/ids, history paths, safe
  run serialization, artifact summary extraction, local CORS headers, local
  path picking, dropped file URI parsing, static Web Runner workbench head/CSS/body
  markup/script-wrapper/state-script/path-script/input-script/report-script/run-script/bootstrap-script/HTML rendering, Web Runner audit subprocess command preparation, and
  namespace-aware config/default-output helpers.
  `veritas.legacy` may keep `WebRunnerState` and wrap namespace-aware helpers
  with its globals while the state machine remains in the compatibility layer.
