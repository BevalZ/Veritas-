# Resolve dropped basename inputs in Web Runner

## Goal

Fix the Web Runner failure where dragging a file in Firefox/Linux still populates only a basename such as `2026-040896_稿件全文C.docx`, causing the audit subprocess to fail with `路径不存在`.

## What I Already Know

- The user reproduced the issue after adding `file://` URI parsing.
- The UI still receives only the basename, meaning the browser did not provide a usable full path in `text/uri-list`, `text/plain`, `file.path`, or directory entry data.
- The backend currently trusts the submitted `input_path` and launches the CLI from the repo working directory.
- Native picker selection can return a full path, but drag-and-drop may not.
- We must not add a general filesystem browser endpoint.

## Requirements

- If Web Runner receives an input with no parent directory and that path does not exist in the server cwd, it should try a bounded local basename search.
- Search should cover common local user locations where drag/drop originates:
  - home directory immediate/common subdirectories
  - Desktop, Documents, Downloads, Videos, Pictures
  - current working directory tree
- If exactly one matching file/directory is found, use that resolved full path for the subprocess and default output calculation.
- If no match is found, return a clear `input_path_not_found` web error before launching the subprocess.
- If multiple matches are found, return a clear `ambiguous_input_path` error with a small candidate list and ask user to use the file/directory picker.
- Preserve explicit paths unchanged.
- Do not upload files or expose arbitrary browsing.

## Acceptance Criteria

- [ ] Basename-only input resolves to a unique file in a configured search root.
- [ ] Missing basename returns `input_path_not_found` from Web Runner without spawning subprocess.
- [ ] Duplicate basename returns `ambiguous_input_path` without spawning subprocess.
- [ ] Explicit full paths are not rewritten.
- [ ] Tests cover unique/missing/ambiguous resolution and subprocess command uses the resolved path.
- [ ] Standard checks pass.

## Out of Scope

- Recursive full-disk search.
- Browser-side filesystem permissions.
- A new file browser API.
- Auto-picking among duplicate names.

## Technical Notes

- Likely file: `veritas/legacy.py`, `WebRunnerState.start_run()`.
- Tests: `tests/test_core.py`.
