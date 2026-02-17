# Devtools Scratch Scripts

This folder stores local debugging and inspection scripts that are not part of production runtime paths.

## Rules
- Keep experimental scripts here, not at repository root.
- Do not import these scripts from app runtime modules.
- If a script becomes production-worthy, move it into the correct package and add tests.

## Current Scripts
- `check_browser_use.py`
- `inspect_mcp_client.py`
- `debug_features.py`
- `debug_features_v2.py`
- `debug_json_fail.py`
- `debug_skills.py`
