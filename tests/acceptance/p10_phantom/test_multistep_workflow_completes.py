<<<<<<< Updated upstream
"""Acceptance scaffold for P10 (p10_phantom).

Replace these contract tests with feature-level assertions as implementation matures.
"""

from pathlib import Path

PROJECT_ID = "P10"
PROJECT_KEY = "p10_phantom"
CI_CHECK = "p10-phantom-browser"
CHARTER = Path("CAPSTONE/project_charters/P10_phantom_autonomous_browser_agent.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P10_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p10_phantom.sh")
THIS_FILE = Path("tests/acceptance/p10_phantom/test_multistep_workflow_completes.py")


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
    assert DEMO_SCRIPT.stat().st_mode & 0o111, f"Demo script not executable: {DEMO_SCRIPT}"


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
=======
import pytest
import asyncio
import os
from browser.controller import BrowserController
from browser.extractor import PageExtractor
from browser.workflow import WorkflowSequencer

@pytest.mark.asyncio
async def test_multistep_workflow_completes():
    """Acceptance test: Verify a complex multi-step workflow executes correctly."""
    ctrl = BrowserController(headless=True, task_id="acceptance_test")
    try:
        await ctrl.start()
        extractor = PageExtractor(ctrl.page)
        sequencer = WorkflowSequencer(ctrl, extractor)
        
        workflow = {
            "name": "Integration Acceptance Workflow",
            "steps": [
                {"action": "navigate", "url": "https://example.com"},
                {"action": "wait", "seconds": 1},
                {
                    "action": "if",
                    "condition": {"selector": "h1"},
                    "then": [
                        {"action": "extract", "var": "page_title"}
                    ]
                }
            ]
        }
        
        result = await sequencer.execute_workflow(workflow)
        assert result["status"] == "success"
        assert "documentation examples" in result["variables"]["page_title"].lower()
        
    finally:
        await ctrl.stop()

@pytest.mark.asyncio
async def test_workflow_with_retries():
    """Acceptance test: Verify workflow retries work on failure."""
    ctrl = BrowserController(headless=True, task_id="retry_acceptance")
    try:
        await ctrl.start()
        extractor = PageExtractor(ctrl.page)
        sequencer = WorkflowSequencer(ctrl, extractor)
        
        workflow = {
            "name": "Retry Fallback Workflow",
            "steps": [
                {"action": "navigate", "url": "https://example.com"},
                {"action": "click", "selector": "#invalid-id", "retries": 1, "delay": 0.1}
            ]
        }
        
        with pytest.raises(Exception):
            await sequencer.execute_workflow(workflow)
            
    finally:
        await ctrl.stop()
>>>>>>> Stashed changes
