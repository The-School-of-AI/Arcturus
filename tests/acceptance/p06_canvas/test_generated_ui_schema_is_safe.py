"""Acceptance scaffold for P06 (p06_canvas).

Replace these contract tests with feature-level assertions as implementation matures.
"""

from pathlib import Path
import os
import sys

PROJECT_ID = "P06"
PROJECT_KEY = "p06_canvas"
CI_CHECK = "p06-canvas-runtime"
CHARTER = Path("CAPSTONE/project_charters/P06_canvas_live_visual_workspace_a2ui.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P06_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p06_canvas.sh")
THIS_FILE = Path("tests/acceptance/p06_canvas/test_generated_ui_schema_is_safe.py")


def _charter_text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def test_01_charter_exists() -> None:
    assert CHARTER.exists(), f"Missing charter: {CHARTER}"


def test_02_expanded_gate_contract_present() -> None:
    assert "Expanded Mandatory Test Gate Contract (10 Hard Conditions)" in _charter_text()


def test_03_acceptance_path_declared_in_charter() -> None:
    assert f"Acceptance: " in _charter_text()


def test_04_demo_script_exists() -> None:
    assert DEMO_SCRIPT.exists(), f"Missing demo script: {DEMO_SCRIPT}"


def test_05_demo_script_is_executable() -> None:
    if sys.platform != "win32":
        assert DEMO_SCRIPT.stat().st_mode & 0o111, f"Demo script not executable: {DEMO_SCRIPT}"
    else:
        assert DEMO_SCRIPT.exists()


def test_06_delivery_readme_exists() -> None:
    assert DELIVERY_README.exists(), f"Missing delivery README: {DELIVERY_README}"


def test_07_delivery_readme_has_required_sections() -> None:
    required = [
        "## 1. Scope Delivered",
        "## 2. Architecture Changes",
        "## 3. API And UI Changes",
        "## 4. Mandatory Test Gate Definition",
        "## 5. Test Evidence",
        "## 8. Known Gaps",
        "## 10. Demo Steps",
    ]
    text = DELIVERY_README.read_text(encoding="utf-8")
    for section in required:
        assert section in text, f"Missing section {section} in {DELIVERY_README}"


def test_08_ci_check_declared_in_charter() -> None:
    assert f"CI required check: " in _charter_text()
