# Third-Party-First Implementation Checkpoint

Date: 2026-05-28

## Result

Checkpoint passed after one version-metadata gap was fixed.

## Findings

- Resolved: ADR-0004 required prompt/schema/adapter/risk-rule versions in formal reports. Markdown and HTML reports now include `PROMPT_VERSION`, `SCHEMA_VERSION`, `ADAPTER_VERSION`, and `RISK_RULE_VERSION`.
- Residual: `pytest` is not installed in this environment, so full pytest execution is not available here. Syntax checks, CLI help, direct package-boundary smoke, renderer version smoke, and evaluation replay smoke passed.

## Review Coverage

- Complete / limited / failed artifacts: covered by helper tests, fake-adapter E2E tests, headers, path helpers, and `.audit/.limited/.failed` naming.
- Strict blocking: MinerU and text LLM preflight failures produce failed diagnostics; reference lookup, image semantic, and imagedetector service-wide failures are covered by adapter/harness paths and `coverage_blocking_failure`.
- Full reference/image coverage: default limits are `None`, meaning all parsed references and all detected images; explicit limits become limited reasons.
- Risk language: reports use `证据风险分`; final risk rules are versioned and use `低`, `中`, `高`, and `严重证据冲突`.
- Evaluation path: synthetic replay is default; public-paper evaluations are separated and require explicit record mode.

## Verification

- `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py`
- `python3 paper_audit.py --help`
- Direct renderer smoke for prompt/schema/adapter/risk-rule version metadata.
- Direct `veritas.evaluation.run_replay_suite()` smoke.
- `python3 -m pytest tests/test_core.py -q` blocked by missing `pytest`.
