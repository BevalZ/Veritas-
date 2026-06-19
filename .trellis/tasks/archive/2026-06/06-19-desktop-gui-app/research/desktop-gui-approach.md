# Desktop GUI Approach

## Question

How should Veritas deliver a real desktop GUI while reusing the current Python audit pipeline?

## Options Considered

### Option A: stdlib tkinter native app

- Pros: no new dependency, already used in `pick_local_path`, works with Python 3.10+, easy to route through `WebRunnerState`, testable by separating contracts from window startup.
- Cons: less visually polished than Qt/Electron; packaging into platform installers remains separate work.

### Option B: Qt/PySide desktop app

- Pros: richer widgets and more professional desktop UI.
- Cons: adds a large dependency not present in `requirements.txt` or `pyproject.toml`; may complicate CI and user setup.

### Option C: Electron/Tauri wrapper around Web Runner

- Pros: can reuse the existing HTML UI.
- Cons: introduces a new stack/build toolchain, duplicates process lifecycle concerns, and is not currently represented in repo dependencies.

## Decision

Use Option A for this task: a native `tkinter` app launched by `python paper_audit.py --gui`.

This directly addresses the user's correction ("GUI software", not browser UI) while staying aligned with existing repo constraints and avoiding dependency installation. The implementation should reuse `WebRunnerState` so the desktop app and Web Runner share run behavior.

## Follow-Up

If the user later asks for a distributable app bundle, add a separate packaging task for PyInstaller or platform-specific packaging.
