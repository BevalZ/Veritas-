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
├── failed_diagnostics.py # Stable failed-audit payload and conversion helpers
├── followups.py       # PubPeer/comment and journal-letter draft workflow helpers
├── html_utils.py       # HTML escaping and script-safe JSON helpers
├── image_cache.py      # Image audit cache key and fingerprint helpers
├── image_reporting.py  # Image audit report and review-manifest rendering helpers
├── image_results.py    # Image provider response normalization helpers
├── image_selection.py  # Image audit selection and cache-flush helpers
├── local_analysis.py   # Local statistics and text chunking helpers
├── mineru_text.py      # MinerU structured content-list text formatting helpers
├── models.py           # Stable dataclass/report models and model conversion
├── paper_identity.py   # Best-effort article identity extraction helpers
├── preflight.py        # Critical capability preflight boundary
├── project_files.py    # Project file discovery and run metadata helpers
├── reference_parsing.py # Reference section parsing and query-building helpers
├── reference_reporting.py # Reference audit Markdown/HTML rendering helpers
├── renderers.py        # Markdown/HTML renderer boundary
├── report_checks.py    # Deterministic LLM finding scoring/display helpers
├── review_overview.py  # Review overview and action-priority rendering helpers
├── resource_parsing.py # Resource URL extraction and classification helpers
├── resource_reporting.py # Resource audit Markdown/HTML rendering helpers
├── risk_rule_helpers.py # Shared risk scoring/merge helpers for rules/rendering
├── risk_rules.py       # Versioned final risk scoring boundary
├── run.py              # Run request/result and orchestration boundary
├── text_utils.py       # Shared text shortening and token similarity helpers
├── versions.py         # Prompt/schema/adapter/risk-rule version constants
├── web_runner.py       # Local Web Runner helper boundary
└── workspace.py        # Per-run workspace boundary
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
- `veritas/artifacts.py` owns formal audit artifact path, limited-outcome, and
  coverage-blocking helpers; `paper_audit` keeps compatibility by re-exporting
  the same function objects through `veritas.legacy`.
- `veritas/failed_diagnostics.py` owns stable failed-audit JSON payload and
  failure-to-`AuditFailure` conversion helpers; Markdown/HTML formatting can
  remain in `veritas.legacy` until renderer dependencies are untangled.
- `veritas/html_utils.py` owns HTML escaping and script-safe JSON helpers used
  by renderers; these remain re-exported through `paper_audit` for
  compatibility while renderer extraction continues.
- `veritas/image_cache.py` owns deterministic image file fingerprints and image
  semantic cache key construction. Namespace-aware helpers let `veritas.legacy`
  preserve historical monkeypatch behavior for image semantic endpoint, model,
  and cache-version globals.
- `veritas/image_reporting.py` owns deterministic rendering of image audit
  display summaries, Markdown/HTML report sections, and the standalone
  `image_ai_review_manifest.html` review checklist. Provider calls and image
  collection stay outside this boundary.
- `veritas/image_results.py` owns deterministic normalization of image semantic
  model responses, imagedetector responses, provider timeout result payloads,
  and JSON-object extraction from model text. It must not perform network I/O.
- `veritas/image_selection.py` owns deterministic image audit sorting,
  semantic/detector priority keys, and cache flush callback handling. It must
  not collect images or call providers.
- `veritas/evidence_rendering.py` owns deterministic evidence excerpt cleanup,
  MinerU table marker removal, Markdown/HTML table parsing, data-table HTML
  rendering, and compact evidence summary HTML. It must remain provider-free
  because MinerU extraction, reference/resource sections, and report rendering
  all reuse it.
- `veritas/text_utils.py` owns shared text shortening, short text fingerprint,
  and token similarity helpers used by follow-up generation, risk rules,
  references, cache keys, evidence IDs, and renderers.
- `veritas/local_analysis.py` owns local non-provider analysis helpers:
  Benford/numeric extraction, local statistical checks, and structure-aware text
  chunking. These helpers must remain deterministic and must not call LLMs or
  network providers.
- `veritas/mineru_text.py` owns deterministic formatting of MinerU
  `content_list` JSON into audit-oriented text blocks, including nested content
  flattening and table markdown normalization. MinerU API upload, polling, and
  ZIP download logic remain outside this boundary.
- `veritas/project_files.py` owns supported text-file extension constants,
  project directory file discovery/classification, main-paper scoring, missing
  metadata detection, and run metadata normalization. Keep this boundary
  deterministic and filesystem-local; provider extraction remains elsewhere.
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
- `veritas/reference_parsing.py` owns deterministic reference-section splitting,
  offline bibliography parsing, DOI/title/author/container/year hint extraction,
  author similarity, and reference query/cache-key construction. Crossref,
  OpenAlex, PubMed, and official-site network lookups remain outside this
  boundary.
- `veritas/reference_reporting.py` owns deterministic reference audit issue
  labels, online summary text, Markdown tables, and HTML cards. Reference
  parsing and online lookup remain outside this boundary.
- `veritas/report_checks.py` owns deterministic LLM finding suspicion scoring,
  source tags, source/reason extraction, merged-finding summary HTML, and check
  sort/verdict helpers shared by report rendering and evidence-chain clustering.
  It must remain provider-free and must not call text LLMs or external services.
- `veritas/review_overview.py` owns deterministic audit action-priority
  summaries and review-overview Markdown/HTML rendering. It may aggregate
  existing report, statistics, reference, resource, cross-file, evidence-chain,
  and image audit payloads, but must remain provider-free.
- `veritas/resource_parsing.py` owns deterministic extraction, cleanup,
  context capture, and classification of code/data/deployed-resource URLs from
  paper text. Resource availability network checks remain outside this boundary.
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
- `veritas/web_runner.py` owns local Web Runner helper functions that do not
  require the `WebRunnerState` class: run timestamps/ids, history paths, safe
  run serialization, artifact summary extraction, local path picking, dropped
  file URI parsing, and namespace-aware config/default-output helpers.
  `veritas.legacy` may keep `WebRunnerState` and wrap namespace-aware helpers
  with its globals while the state machine remains in the compatibility layer.
