# Improve Web Runner run completion actions

## Goal

Close the local Web Runner run loop for non-technical users by making the output location visible, surfacing the most useful completion actions, and providing a retry action after failed or canceled runs.

## What I Already Know

- The Web Runner already starts real audit subprocesses.
- Output defaults to a timestamped project folder beside the input.
- Run history records artifact paths and exposes allowlisted artifact links.
- `/artifact/<run_id>/folder` currently returns a JSON object with the output folder path.
- The workbench currently renders recent run links, but the current-run panel does not strongly surface output folder, completion actions, or retry.

## Requirements

- Show the selected/default output path before and during a run.
- When a run completes, show direct actions for recorded artifacts:
  - open HTML report
  - open Markdown report
  - open JSON report
  - open output folder path
- For failed or canceled runs, show a retry action that starts a new run with the same input/output/fresh settings.
- The retry action should not create a concurrent run if one is already active.
- Folder access must continue to use recorded run metadata only; do not add arbitrary filesystem browsing.
- Keep the UI quiet and workbench-like.

## Acceptance Criteria

- [ ] Current-run panel displays the output stem/path for the selected or running task.
- [ ] Current-run panel renders artifact action buttons after completion when artifacts are recorded.
- [ ] Failed/canceled runs expose a retry button.
- [ ] Retry reuses the previous run's `input_path`, `output`, and `fresh` values.
- [ ] Tests cover current-run action rendering and retry payload behavior.
- [ ] Existing standard checks pass.

## Out of Scope

- Native OS folder opening from the browser.
- New arbitrary file/folder browser endpoints.
- Multi-run queue.
- Rebuilding the detailed report reader inside the workbench.

## Technical Notes

- Likely file: `veritas/legacy.py`, `render_web_runner_page()`.
- Tests should remain string/unit-level in `tests/test_core.py`.
