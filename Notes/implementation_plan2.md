# [Goal Description]
Integrate Ruff (for fast linting and formatting) and Pyright (for static type checking) into the Arcturus IDE.
This enables:
1.  **Format on Save**: Automatically format Python files using Ruff.
2.  **Linting**: Display Ruff lint errors in the editor (future: Problems panel).
3.  **Type Checking**: Run Pyright to catch type errors.

## User Review Required
- **Dependencies**: Users will need `ruff` and `pyright` installed in their environment (or we can use `uv` / `pip` to install them automatically).
- **Configuration**: We will add a default [pyproject.toml](file:///Users/rohanshravan/TSAI/Arcturus/pyproject.toml) or `ruff.toml` if missing, or respect existing ones.

## Proposed Changes
### Backend (`routers/tools.py` or new `routers/language_server.py`)
#### [NEW] `routers/python_tools.py`
- Create endpoints:
    - `POST /python/format`: Run `ruff format` on a file/content.
    - `POST /python/lint`: Run `ruff check --output-format=json` and return diagnostics.
    - `POST /python/typecheck`: Run `pyright --outputjson` and return diagnostics.
- Helper functions to locate `ruff` and `pyright` binaries (or run via `python -m`).

### Frontend
#### [MODIFY] [EditorArea.tsx](file:///Users/rohanshravan/TSAI/Arcturus/platform-frontend/src/features/ide/components/EditorArea.tsx)
- Add `onSave` hook to call `/python/format` (blocking or async?).
- Add logic to fetch diagnostics from `/python/lint` and `/python/typecheck` after save.
- Display diagnostics (red squiggles) in Monaco Editor (using `monaco.editor.setModelMarkers`).

## Verification Plan
### Automated Tests
- Create a messy Python file (bad formatting, unused imports).
- Call `/python/format` -> Verify file is formatted.
- Call `/python/lint` -> Verify JSON response contains "unused import" error.
- Call `/python/typecheck` -> Verify JSON contains type errors.

### Manual Verification
- Open a Python file in IDE.
- Save -> Watch it format.
- Write a type error (`x: int = "string"`) -> See red squiggle (if markers are wired up).
