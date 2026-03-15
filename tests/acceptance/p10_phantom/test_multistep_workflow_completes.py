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
