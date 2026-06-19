# Desktop GUI App for Veritas

## Goal

Deliver a real local desktop GUI for Veritas, not just a browser URL. The app should open as a native window, let the user select an audit input, run the existing audit pipeline, stream progress, and open generated report outputs directly.

## What I Already Know

- The previous delivery was a localhost Web Runner (`--serve-web`), which is a browser-based UI, not the desktop GUI software the user expected.
- The project is Python-first and already has a compatibility entry point at `paper_audit.py`.
- Existing audit behavior lives in `veritas/legacy.py`.
- The Web Runner already has a tested backend state object, artifact discovery, run logging, cancel/retry, config status, and safe artifact allowlisting.
- The repo has no Qt, Electron, Tauri, PyWebView, or packaging dependency.
- The code already uses stdlib `tkinter` for native file/directory pickers in `pick_local_path`.
- To minimize risk, the GUI should reuse `WebRunnerState` rather than creating a second audit orchestration path.

## Assumptions

- "GUI software" means a native desktop window, not a web page the user has to open manually.
- The immediate deliverable can be launched with `python paper_audit.py --gui`; installed environments should also expose `veritas-gui`.
- A packaged `.exe`/`.app` installer is useful later, but is out of scope unless the repo already has packaging infrastructure.

## Five Design Passes

### Pass 1: Native Product Boundary

Decision: implement a `tkinter` desktop app.

Why: it ships with Python, matches existing local picker usage, avoids dependency installation, and can be tested in headless CI by separating app contracts from actual window display.

Gap closed: user sees a native window instead of a localhost browser page.

### Pass 2: Backend Reuse

Decision: drive runs through `WebRunnerState`.

Why: it already owns subprocess invocation, single-active-run protection, artifact discovery, log offsets, cancellation, report summary extraction, and default output behavior.

Gap closed: no second CLI runner with divergent behavior.

### Pass 3: Report Output

Decision: expose HTML, Markdown, JSON, and folder opening from the native UI using recorded artifact paths.

Why: the product goal is direct report output. A GUI that runs audits but leaves users hunting for files is incomplete.

Gap closed: completed/failed/limited outputs are visible and actionable.

### Pass 4: Failure Recovery

Decision: GUI status must show picker errors, config readiness, audit failures, canceled state, and retry/open actions without crashing the window.

Why: the real audit pipeline depends on local files, config, and external services.

Gap closed: failures remain useful and visible.

### Pass 5: Local Safety

Decision: keep the GUI local-only and do not add arbitrary file-serving or remote API surfaces.

Why: the desktop app can open local paths directly; it should not weaken Web Runner security boundaries.

Gap closed: no new network exposure, no secret serialization.

## Requirements

- Add a CLI flag `--gui` to launch the native desktop app.
- Add a console script entry point `veritas-gui` for installed environments.
- The GUI opens a native window titled for Veritas.
- The GUI provides controls to choose input file, choose input directory, choose output directory, toggle fresh run, start, cancel, retry, and refresh config status.
- The GUI streams run logs inside the window while the audit subprocess runs.
- The GUI shows current status, input path, output path, report type, risk level, and summary when available.
- The GUI exposes direct actions for generated HTML, Markdown, JSON, and output folder artifacts.
- The GUI must reuse existing audit subprocess behavior through `WebRunnerState`.
- The GUI must not require a browser to operate.
- The GUI must not serialize or display raw API keys.
- The GUI must remain testable without opening a real window in unit tests.

## Acceptance Criteria

- [ ] `python paper_audit.py --gui` is accepted by CLI help and launches the desktop app.
- [ ] `pyproject.toml` declares a `veritas-gui` desktop launcher command.
- [ ] The desktop app can start an audit using the same backend command path as Web Runner.
- [ ] The desktop app can cancel an active run through `WebRunnerState.cancel_run`.
- [ ] The desktop app displays logs and final run metadata.
- [ ] The desktop app can open generated report artifacts and containing folder when present.
- [ ] Unit tests cover CLI help, GUI launch routing, backend reuse, artifact action mapping, and config secrecy.
- [ ] Existing Web Runner tests still pass.
- [ ] Full `tests/test_core.py` passes.

## Definition of Done

- Native GUI implementation added.
- CLI exposes `--gui`.
- Tests added/updated.
- `python3 -m py_compile paper_audit.py veritas/*.py tests/test_core.py` passes.
- `python3 paper_audit.py --help` passes.
- `python3 -m pytest tests/test_core.py -q` passes.
- A real GUI launch command is demonstrated or, if display is unavailable, the launch path is verified and the limitation is stated.

## Out of Scope

- Installer packaging (`.exe`, `.dmg`, `.deb`) in this task.
- Replacing the Web Runner.
- Public hosting, accounts, remote uploads, or multi-user access.
- Rewriting audit algorithms.

## Technical Notes

- Primary implementation: `veritas/legacy.py`.
- Compatibility entry: `paper_audit.py`.
- Likely new function: `run_desktop_gui(...)`.
- Existing backend to reuse: `WebRunnerState`.
- Existing safe config status: `web_runner_config_status()`.
- Existing native picker precedent: `pick_local_path()` uses `tkinter`.
