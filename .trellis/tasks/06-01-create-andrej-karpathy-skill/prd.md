# Create Andrej Karpathy Skill

## Goal

Create a local Codex skill based on the upstream `https://github.com/multica-ai/andrej-karpathy-skills.git` repository so the guidance can be invoked as a normal Codex skill.

## Requirements

* Create the skill in the auto-discovered Codex skills directory: `${CODEX_HOME:-$HOME/.codex}/skills`.
* Name the skill `karpathy-guidelines` to match the upstream skill folder.
* Preserve the upstream intent: apply Andrej Karpathy-inspired coding, learning, and AI collaboration guidance.
* Convert the skill into this environment's valid skill format with clean frontmatter and concise instructions.
* Include UI metadata in `agents/openai.yaml`.
* Avoid unrelated repo changes beyond Trellis task bookkeeping.

## Acceptance Criteria

* [x] `karpathy-guidelines/SKILL.md` exists under `${CODEX_HOME:-$HOME/.codex}/skills`.
* [x] `SKILL.md` validates with the skill creator `quick_validate.py` script.
* [x] `agents/openai.yaml` exists and matches the skill purpose.
* [x] The source repository is referenced in the skill body for provenance.

## Definition of Done

* Validate the generated skill.
* Report the created path and validation result.
* Note any skipped steps or permission/network limitations.

## Technical Approach

Use the `skill-creator` initializer to scaffold the skill, then replace the template with concise Codex-facing guidance adapted from the upstream repository. Fetch upstream content into `/tmp` for inspection only.

## Decision (ADR-lite)

**Context**: The user asked to create a skill according to an external skill repository.

**Decision**: Create a local `karpathy-guidelines` skill rather than modifying the application codebase.

**Consequences**: The skill is available to Codex if the local skills directory is scanned. The workspace repo only receives Trellis task bookkeeping.

## Out of Scope

* Publishing the skill to a marketplace.
* Installing a plugin.
* Modifying application behavior in this repository.

## Technical Notes

* Upstream repo: `https://github.com/multica-ai/andrej-karpathy-skills.git`
* Source skill path observed via GitHub: `skills/karpathy-guidelines/SKILL.md`
* Created local skill at `/home/haozhao/.codex/skills/karpathy-guidelines`.
* Validation passed with `python3 /home/haozhao/.codex/skills/.system/skill-creator/scripts/quick_validate.py /home/haozhao/.codex/skills/karpathy-guidelines`.
* Project tests passed: `python3 -m pytest` (`131 passed`).
* Ruff is configured in `pyproject.toml` but unavailable in this environment (`python3 -m ruff` and `ruff` both failed because Ruff is not installed).
* Spec update review completed: no code-spec update needed because no app command/API/schema/env contract or reusable repo code pattern changed.
