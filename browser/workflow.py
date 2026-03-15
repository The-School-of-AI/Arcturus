import asyncio
import logging
from typing import List, Dict, Any, Optional
import time

logger = logging.getLogger("phantom-workflow")

class WorkflowSequencer:
    """
    Executes complex multi-step browser workflows with conditional logic and error recovery.
    """
    
    def __init__(self, controller, extractor):
        self.controller = controller
        self.extractor = extractor
        self.variables = {}

    async def execute_workflow(self, workflow_def: Dict[str, Any]):
        """Run a workflow from a JSON definition."""
        name = workflow_def.get("name", "Unnamed Workflow")
        steps = workflow_def.get("steps", [])
        
        logger.info(f"🚀 Starting workflow: {name}")
        
        for i, step in enumerate(steps):
            logger.info(f"Step {i+1}/{len(steps)}: {step.get('action')}")
            result = await self._execute_step(step)
            if result and result.get("status") == "stop":
                logger.info(f" Workflow stopped: {result.get('message')}")
                return result
                
        logger.info(f"✅ Workflow '{name}' completed successfully")
        return {"status": "success", "variables": self.variables}

    async def _execute_step(self, step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        action = step.get("action")
        retries = step.get("retries", 3)
        delay = step.get("delay", 1.0)
        
        for attempt in range(retries):
            try:
                if action == "navigate":
                    await self.controller.navigate(step["url"])
                elif action == "click":
                    await self.controller.click(step["selector"])
                elif action == "type":
                    await self.controller.type(step["selector"], step["text"])
                elif action == "wait":
                    await asyncio.sleep(step.get("seconds", 2))
                elif action == "if":
                    return await self._handle_if(step)
                elif action == "extract":
                    val = await self.extractor.extract_structured_data()
                    self.variables[step.get("var", "last_extraction")] = val
                elif action == "stop":
                    return {"status": "stop", "message": step.get("message", "Action stop triggered")}
                
                # If we reach here, action succeeded
                return None
                
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {action}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(delay)
                    # Fallback: take a screenshot to help debug if it keeps failing
                    if attempt == retries - 2:
                        await self.controller.get_screenshot(f"fallback_error_{int(time.time())}.png")
                else:
                    raise e

    async def _handle_if(self, step: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        condition = step.get("condition", {})
        selector = condition.get("selector")
        text_matches = condition.get("text_matches")
        
        # Check condition
        met = False
        if selector:
            el = await self.controller.page.query_selector(selector)
            if el:
                if text_matches:
                    text = await el.inner_text()
                    met = text_matches in text
                else:
                    met = True
        
        branch = step.get("then") if met else step.get("else")
        if branch:
            for sub_step in branch:
                res = await self._execute_step(sub_step)
                if res: return res
        return None
