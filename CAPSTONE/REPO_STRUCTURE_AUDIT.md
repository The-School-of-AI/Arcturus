# Repository Structure Audit

Generated on 2026-02-17 after cleanup pass.

## 1) Root-Level Files (Current)

```
.env
.gitignore
ARCHITECTURE.md
HOWTORUN.md
__init__.py
api.py
app.py
arcturus_ui.json
package-lock.json
pyproject.toml
pytest.ini
uv.lock
```

## 2) Log/Debug/Temp Signals (Depth <= 3, Current)

```
__pycache__/test_debug.cpython-311-pytest-9.0.2.pyc
scripts/devtools/debug_features.py
scripts/devtools/debug_features_v2.py
scripts/devtools/debug_json_fail.py
scripts/devtools/debug_skills.py
```

## 3) Cleanup Actions Applied
- Moved loose debug/helper scripts from root to `scripts/devtools/`.
- Archived duplicate UI snapshots under `CAPSTONE/archives/ui_snapshots/`.
- Moved `test_regex.js` to `tests/manual/legacy/scripts/`.
- Removed stale `mcp_servers/rag_debug.log` from source directory.
- Updated `mcp_servers/server_rag.py` to write debug logs to `data/runtime_logs/rag_debug.log`.
- Removed root `.DS_Store`.

## 4) Remaining Recommendations
1. Keep root-level scripts minimal; put experiments in `scripts/devtools/` or `tests/manual/legacy/`.
2. Keep only one canonical root UI seed (`arcturus_ui.json`) unless a new archive is intentional.
3. Add a repo hygiene CI check if you want strict prevention of future root clutter.
