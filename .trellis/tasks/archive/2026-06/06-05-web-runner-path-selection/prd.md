# Improve Web Runner path selection and output defaults

## Goal

Make the local Web Runner friendlier for non-technical users by removing manual path typing from the primary workflow, adding buttons for choosing input and output paths, and defaulting output artifacts into a timestamped project folder next to the selected input.

## What I Already Know

- The Web Runner currently has text inputs for input path and output path/stem.
- Drag-and-drop can populate the input field, but browsers may expose only a name rather than an absolute path.
- The audit CLI already supports `-o <output_stem>`.
- Passing an output stem like `/parent/project_20260605-153000/audit_report` produces normal artifacts inside that timestamped folder.
- Standard browser file inputs cannot reliably provide absolute local paths; a local server endpoint can open a native chooser when GUI support is available.

## Requirements

- The visible Web Runner workflow should not require manual path typing.
- Input path selection should be available through buttons:
  - choose a file
  - choose a directory
- Output selection should be available through a button.
- Input and output path fields should be readonly display fields, while drag/drop still fills the input path.
- When input is selected or dropped, output should default to:
  - same parent directory as the selected input
  - subdirectory named `<project_name>_<timestamp>`
  - output stem `audit_report`
  - example: `/papers/Test_paper2_20260605-153000/audit_report`
- Starting a run without an explicit output should still use the timestamped default on the backend.
- No upload endpoint and no arbitrary filesystem browser endpoint should be added.
- Existing artifact allowlist behavior remains unchanged.

## Acceptance Criteria

- [ ] Workbench renders file, directory, and output selection buttons.
- [ ] Input and output text fields are readonly.
- [ ] Client-side default output helper derives `<project>_<timestamp>/audit_report` from a selected input path.
- [ ] Backend has a deterministic default output helper and uses it when `POST /api/runs` omits output.
- [ ] Path picker API supports `input_file`, `input_directory`, and `output_directory` modes.
- [ ] Tests cover picker endpoint helpers, default output calculation, readonly fields, and subprocess command output behavior.
- [ ] Existing Web Runner/report action tests still pass.

## Out of Scope

- Cloud upload or copying files into Veritas.
- Recursive filesystem browsing in the browser.
- Batch queues or multiple selected inputs.
- Replacing drag-and-drop.
- Guaranteeing native picker availability on headless servers.

## Technical Notes

- Likely files:
  - `veritas/legacy.py`
  - `tests/test_core.py`
- If native picker support is unavailable, the API should return a structured error instead of crashing the server.
