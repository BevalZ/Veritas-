# Fix Web Runner dropped file path resolution

## Goal

Fix Web Runner drag-and-drop so dropping a file from the desktop/file manager resolves the full local path when the browser provides one, instead of falling back to the bare file name and causing `路径不存在`.

## What I Already Know

- The user reproduced the bug in Firefox on Linux: dropping `2026-040896_稿件全文C.docx` populated only the filename.
- Starting the run then failed because the subprocess cwd is the repository, not the file's containing folder.
- Browsers often expose only `File.name`, but Linux file managers commonly include full `file://` URIs in `text/uri-list` or `text/plain`.
- The current implementation checks `webkitGetAsEntry()`, then `file.path`, `webkitRelativePath`, and `file.name`.

## Requirements

- Prefer full local file URI data from `DataTransfer.getData("text/uri-list")` and `DataTransfer.getData("text/plain")` before falling back to `File.name`.
- Decode `file://` URIs to local paths.
- Ignore non-file URI/list comments.
- Preserve existing drag/drop behavior when no full path is available.
- Do not upload file bytes or add a filesystem browser endpoint.

## Acceptance Criteria

- [ ] Dropping data with `file:///home/user/paper.docx` resolves to `/home/user/paper.docx`.
- [ ] URI lists with comments resolve the first file URI.
- [ ] Non-file data falls back to existing file/entry handling.
- [ ] Tests cover the helper logic through rendered JS string coverage or extracted backend helper if added.
- [ ] Standard checks pass.

## Out of Scope

- Guaranteeing full path support in browsers that do not provide any URI/path data.
- Native drag integration beyond the browser's DataTransfer payload.
- Uploading or copying dropped files.

## Technical Notes

- Likely file: `veritas/legacy.py`, `render_web_runner_page()` JavaScript.
- Tests: `tests/test_core.py`.
