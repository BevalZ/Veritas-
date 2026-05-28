# Logging Guidelines

> How logging is done in this project.

---

## Overview

The current CLI uses console output plus per-run workspace JSON files instead of
a logging framework. Long-running audit stages should emit concise progress to
stdout and record structured run state in the workspace or resume cache.

---

## Log Levels

- Success/progress messages use clear CLI text and progress bars.
- Warnings use `⚠️` in user-facing output when a run becomes limited or a
  non-critical operation is skipped.
- Critical failures use failed diagnostic artifacts rather than only console
  text.

---

## Structured Logging

Structured run state should be written as JSON:

- `.paper_audit_runs/<run_id>/workspace.json`
- `.paper_audit_runs/<run_id>/input_manifest.json`
- `.paper_audit_runs/<run_id>/cache_use.json`
- `.paper_audit_runs/<run_id>/preflight.json`
- `.paper_audit_runs/<run_id>/report_outcome.json`

Failed diagnostics must include capability, error class, completed stages,
fix hints, retry command, and technical details.

---

## What to Log

- Runtime configuration presence and selected model/provider identifiers, but
  never secrets.
- Preflight start/result for critical services.
- Stage completion and cache hit/miss summaries.
- Formal artifact paths and workspace artifact snapshots.
- Evaluation replay payload summaries.

---

## What NOT to Log

- API keys, bearer tokens, cookies, or presigned upload URLs.
- Full private configuration files.
- Large raw LLM/provider responses in console output; preserve raw responses in
  structured artifacts or caches when needed for diagnostics.
