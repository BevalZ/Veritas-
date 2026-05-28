# Align user-visible semantics with third-party-first ADRs

## What to build

Align README, CLI help, and report terminology with the accepted ADRs before deeper code movement.

This slice removes stale local-first and privacy-first promises from user-facing text and introduces the confirmed third-party-first vocabulary.

## Acceptance criteria

- [x] README presents the tool as third-party-service-first for public literature.
- [x] README no longer advertises Ollama/local LLM or local OCR as formal review paths.
- [x] CLI help does not imply disabling critical capabilities can still produce a complete report.
- [x] User-visible report text uses `证据风险分` instead of `打假得分`.
- [x] User-visible risk levels no longer include `可疑黑产`; use `严重证据冲突` for the highest evidence state.
- [x] `python paper_audit.py --help` still runs.

## Verification

- `python paper_audit.py --help`
- `python -m py_compile paper_audit.py`
- `rg -n "Ollama|本地LLM|本地OCR|隐私友好|打假得分|可疑黑产|强制使用原始PDF|仅原始PDF文本|完全离线|本地部署" README.md paper_audit.py`

## Blocked by

None - can start immediately.
