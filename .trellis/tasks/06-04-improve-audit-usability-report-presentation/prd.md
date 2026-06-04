# Improve audit usability and report presentation

## Goal

Make the paper audit tool easier to run and easier to interpret without changing the underlying audit science. The next iteration should improve the user-facing launch flow, the report's first-screen 复核概览, and the way users move from a summary finding to the supporting evidence or failure guidance.

## What I already know

- The current product is a CLI-first academic paper audit tool that generates Markdown, HTML, and JSON artifacts.
- The report already includes complete/limited/failed artifact types, local statistics, LLM findings, reference/resource audits, cross-file consistency, evidence-chain clusters, image sections, and follow-up draft actions.
- The recent `Test_paper2` run exposed concrete usability friction:
  - Missing optional dependencies made the first direct Word run fail until `python-docx` was installed.
  - Directory mode produced a misleading low-text result before direct `.docx` mode succeeded.
  - Explicit `-o Test_paper2/test_paper2_docx_direct` while the output directory was already `Test_paper2` produced nested `Test_paper2/Test_paper2/...` paths, which is hard for users to reason about.
  - Final reports are complete, but the first-read experience is dense.
- Existing tests cover report rendering, artifact type distinctions, output path normalization, workspace artifacts, direct Word extraction, failed diagnostics, and follow-up context.

## Assumptions

- MVP stays CLI + generated HTML report. It does not introduce a full web app or desktop GUI.
- The highest-value user is someone reviewing one paper or paper folder and needing a reliable, explainable review artifact.
- Improvements should preserve complete/limited/failed semantics and should not weaken existing preflight failure behavior.
- Presentation improvements should make automated findings easier to review, not make stronger misconduct claims.

## Requirements

### 1. Smooth launch and output UX

- Normalize explicit output paths so common invocations do not create surprising nested directories when the user passes an output path under the current output directory.
- Treat explicit relative `--output/-o` paths as relative to the current working directory, not relative to the automatically selected input/output directory.
  - No `-o`: keep existing default behavior and write beside the input file or inside the input directory.
  - `-o test_paper2_audit`: write `test_paper2_audit.audit.*` under the current working directory.
  - `-o Test_paper2/test_paper2_audit`: write `Test_paper2/test_paper2_audit.audit.*`.
- Print a clear pre-run or early-run summary:
  - input path and detected mode: single file vs directory
  - extraction route: MinerU PDF, direct `.docx`, Excel/text, or directory multi-format
  - output directory and final artifact stem
  - resume/cache directory
  - whether the run can be complete or is already scope-limited by CLI flags
- Improve optional dependency diagnostics:
  - direct `.docx` failure should say exactly which dependency is missing and include the minimal install command
  - directory runs that include 审查相关文件 requiring optional dependencies should not silently produce a misleading tiny extraction when the dependency is missing
- Treat extraction failure for any selected 审查相关文件 as blocking for complete reports:
  - main manuscript extraction failure -> `*.failed.*`
  - only auditable file extraction failure -> `*.failed.*`
  - supplement/table/data extraction failure -> `*.failed.*`, unless a future explicit user option excludes that file or opts into a range-limited skip
  - incidental files such as logs, hidden system files, and unrelated temp files may be ignored
- Keep `--no-open` behavior suitable for server/CI usage.

### 2. 复核概览 first screen

- Add a compact 复核概览 at the top of complete and limited HTML/Markdown reports.
- The 复核概览 should expose:
  - report type: complete or limited
  - final risk level and evidence risk score
  - red flag count, evidence warning count, extraction warning count
  - LLM coverage and failed chunks when relevant
  - top 3 priority actions with short manual-review guidance
  - final artifact paths when available
- The 复核概览 must not duplicate every detail table; it should help users decide what to inspect first.
- Keep existing detailed sections below the 复核概览.

### 3. 报告内证据导航 and error recovery

- Add stable anchors/IDs for each major report section and each finding row/detail inside the generated report:
  - 复核概览
  - suspicious findings
  - evidence-chain clusters
  - reference audit
  - resource audit
  - image audit
  - cross-file consistency
  - failed diagnostics
- Let top priority actions link directly to the relevant detail section or evidence cluster rendered in the same report.
- Do not promise source-document navigation in this task:
  - no PDF page-coordinate links
  - no Word paragraph IDs
  - no table-cell coordinate links
  - no source-span model changes
- For limited reports, show a clear limitation panel:
  - what limited coverage
  - what was completed
- For failed reports, do not render 复核概览. Render a 失败恢复面板 instead:
  - failed capability
  - error category
  - completed stages
  - cache/resume state when available
  - exact retry command
  - missing dependency or provider failure hints
- Preserve the current failed-report rule: failed diagnostics cannot generate PubPeer or journal-letter drafts.

## Acceptance Criteria

- [ ] Running `python3 paper_audit.py sample.docx -o sample_report --json --no-open` writes predictable `sample_report.audit.*` artifacts under the current working directory without nested output surprises.
- [ ] Running `python3 paper_audit.py Test_paper2 -o Test_paper2/test_paper2_audit --json --no-open` writes `Test_paper2/test_paper2_audit.audit.*`, not `Test_paper2/Test_paper2/test_paper2_audit.audit.*`.
- [ ] A direct `.docx` run without `python-docx` produces failed diagnostics with a minimal install command and does not produce a misleading complete report.
- [ ] A directory containing a `.docx` 审查相关文件 without `python-docx` writes failed diagnostics instead of auditing only incidental text.
- [ ] Incidental unrelated files in a directory do not block the run.
- [ ] Complete and limited HTML reports start with a compact 复核概览 containing report type, risk level, score, counts, coverage, and top actions.
- [ ] Complete and limited Markdown reports have the same 复核概览 content in plain text/table form.
- [ ] Top actions in HTML link to stable anchors in detail sections.
- [ ] Limited reports include a limitation panel with coverage constraints and completed stages.
- [ ] Failed reports render a 失败恢复面板 with completed stages, cache/resume state when available, retry command, and fix guidance, and do not show 复核优先级 or 证据风险分.
- [ ] Existing complete/limited/failed artifact naming tests continue to pass.
- [ ] Tests use deterministic fixtures/fake adapters and do not call external services.
- [ ] `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py` passes.
- [ ] `python3 paper_audit.py --help` passes after CLI/help text changes.
- [ ] `python3 -m pytest tests/test_core.py -q` passes when pytest is available.

## Implementation Arrangement

### Slice 1: Output and launch UX

- Inspect and adjust output path normalization around `get_output_base`, `_failed_artifact_options`, and `audit_artifact_paths`.
- Add focused tests for explicit output paths inside the input/output directory.
- Preserve default no-`-o` behavior so existing simple commands continue writing beside the input.
- Add or refactor a small run-summary formatter only if it avoids duplicating print logic.
- Strengthen missing optional dependency handling for directory extraction paths.

### Slice 2: 复核概览

- Add a shared 复核概览 data builder so Markdown and HTML render the same summary facts.
- Render the overview near the top of `format_report` and `format_html_report`.
- Keep the 复核概览 compact: it should summarize and link, not replace detailed sections.
- Add renderer tests for complete and limited 复核概览 states.

### Slice 3: 报告内证据导航 and recovery panel

- Add deterministic anchor generation for findings and major sections.
- Link priority actions to evidence details in HTML.
- Keep navigation within the generated report; do not add source-document location tracking.
- Add limited-report limitation panel rendering and failed-report 失败恢复面板 rendering.
- Add tests that assert anchors and retry guidance are present without snapshotting entire HTML.

## Out of Scope

- New fraud detection methods.
- New LLM prompts, schema changes, or risk-rule scoring changes unless needed only to expose existing fields.
- A full drag-and-drop web application.
- A local upload page or drag-drop runner.
- Run queue, live web progress, or artifact browser UI.
- Browser automation or external service calls in default tests.
- Visual redesign that changes the report into a marketing page.
- Source-document page, paragraph, table-cell, or image-coordinate navigation.
- A generalized source-span model for PDF/Word/table extraction.

## Technical Notes

- Likely implementation files:
  - `veritas/legacy.py`: CLI orchestration, output path handling, progress messages, report formatting implementation.
  - `veritas/renderers.py`: rendering boundary that delegates into legacy formatters.
  - `tests/test_core.py`: current high-coverage test file for CLI, artifacts, rendering, extraction, and report action behavior.
  - `README.md`: update only if CLI behavior or recommended command examples change.
- Relevant contracts from specs:
  - Preserve complete/limited/failed artifact distinctions.
  - Do not render malformed LLM findings into complete reports.
  - Default tests must not call third-party services.
  - Use fake adapters or deterministic fixtures for tests.
  - After backend edits, run py_compile and focused tests.
- Cross-layer data flow to protect:
  - CLI args -> run request/orchestration -> meta/artifact paths -> Markdown/HTML/JSON renderers -> follow-up context.
  - The 复核概览 should be built from existing report/meta/stat/reference/resource/evidence-chain fields rather than inventing a second risk model.
- Future task candidate:
  - Local web runner with file picker, drag-drop input, run queue, live progress, and artifact browser.
