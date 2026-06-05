# Add drag-and-drop input path to Web Runner

## Goal

Make the Web Runner easier for non-technical users by allowing users to drag a paper file or audit directory onto the workbench input area instead of manually typing the path.

## What I Already Know

- The Web Runner is served by `python paper_audit.py --serve-web`.
- The current MVP has a text input for `input_path`, an optional output field, a fresh checkbox, start/cancel controls, logs, config status, and recent runs.
- The backend intentionally runs the existing CLI in a subprocess and does not upload file contents to the web server.
- Artifact and path security boundaries matter: the Web Runner must not become a general local filesystem browser.

## Assumptions

- Drag-and-drop should only populate the existing input path field.
- Drag-and-drop should not upload file bytes or add a new backend endpoint.
- Browser support for real local paths is limited; when the browser does not expose `file.path`, the UI should fall back to `file.name` and leave the user able to edit the field.
- Directory drag should use `DataTransferItem.webkitGetAsEntry()` where available to detect a directory and populate the best available name/path.

## Requirements

- The input area accepts drag/drop of one file or directory.
- Dropping a file or directory fills the existing input path field with the best available path string.
- The drop target shows a clear drag-over state.
- The UI keeps manual typing/editing as the fallback.
- No file bytes are uploaded to the server.
- No arbitrary filesystem browsing endpoint is added.
- Existing start/cancel/log/history behavior remains unchanged.

## Acceptance Criteria

- [ ] Web Runner page includes a visible drop target associated with the input path.
- [ ] Dropping a file calls client-side logic that populates `inputPath`.
- [ ] Dropping a directory-like item uses the directory entry name/path when available.
- [ ] Drag/drop events prevent the browser from navigating away.
- [ ] Tests cover the rendered drop target and client-side helper functions.
- [ ] Existing Web Runner and report action tests still pass.

## Out of Scope

- Native OS file picker.
- Uploading files/directories into Veritas.
- Recursive directory inspection in the browser.
- New backend path browsing or file discovery APIs.
- Multi-item batch queue.

## Technical Notes

- Likely file: `veritas/legacy.py`, function `render_web_runner_page()`.
- Tests should stay deterministic in `tests/test_core.py` and should not require a real browser.
