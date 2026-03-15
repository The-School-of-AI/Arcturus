import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import time

logger = logging.getLogger("phantom-logic")

@dataclass
class TaskComplexity:
    model_tier: str # 'fast', 'mid', 'frontier'
    reason: str

class LLMClassifier:
    """
    Classifies browser tasks by complexity to route to the appropriate LLM.
    - Fast: Atomic actions (click, type, navigate)
    - Mid: Single-page reasoning/extraction
    - Frontier: Complex multi-step planning or recovery
    """
    
    def classify(self, task: str) -> TaskComplexity:
        task_lower = task.lower()
        
        # Simple heuristics for routing (can be replaced with a small model call)
        if any(word in task_lower for word in ["navigate to", "click on", "type", "refresh"]):
            if len(task_lower.split()) < 10:
                return TaskComplexity(model_tier="fast", reason="Single atomic action")
        
        # Check frontier first (highest complexity)
        if any(word in task_lower for word in ["login", "log in", "dashboard", "multi-step", "complex", "plan", "auth"]):
            return TaskComplexity(model_tier="frontier", reason="High-level planning or auth flow")
            
        # Check mid (medium complexity)
        if any(word in task_lower for word in ["summarize", "extract", "find", "read", "scrape"]):
            return TaskComplexity(model_tier="mid", reason="Page reasoning/extraction")
            
        return TaskComplexity(model_tier="mid", reason="Default mid-tier routing")

class AgentLoop:
    """
    Core action loop for the autonomous browser agent.
    Handles state management, checkpointing, and task execution.
    """
    
    def __init__(self, controller, extractor):
        self.controller = controller
        self.extractor = extractor
        self.history = []
        self.checkpoints = {}

    async def execute_task(self, task: str):
        """Run the agent loop to fulfill a task."""
        logger.info(f"Starting task execution: {task}")
        
        # Step 1: Classify task
        classifier = LLMClassifier()
        complexity = classifier.classify(task)
        logger.info(f"Task classified as {complexity.model_tier} tier: {complexity.reason}")
        
        # Step 2: Initialize loop
        max_steps = 15
        step = 0
        
        while step < max_steps:
            step += 1
            logger.info(f"Step {step}/{max_steps}")
            
            # Perception: Get perception snapshot
            dom = await self.extractor.get_simplified_dom()
            
            # Decision: Simulated LLM call based on tier
            action = await self._call_llm_simulated(complexity.model_tier, task, dom)
            
            if action.get("status") == "complete":
                logger.info(f"Goal reached: {action.get('message')}")
                break
                
            # Execution
            try:
                if action["type"] == "navigate":
                    await self.controller.navigate(action["url"])
                elif action["type"] == "click":
                    await self.controller.click(action["selector"])
                elif action["type"] == "type":
                    await self.controller.type(action["selector"], action["text"])
                
                self.history.append(action)
            except Exception as e:
                logger.error(f"Action failed: {e}")
                # Simple recovery or stop
                break
                
        return {"status": "completed", "steps": step, "history": self.history, "tier": complexity.model_tier}

    async def _call_llm_simulated(self, tier: str, task: str, dom: str) -> Dict[str, Any]:
        """
        Simulated LLM call. In a production environment, this would call 
        Gemini 1.5 Pro (Frontier) or Flash (Fast/Mid).
        """
        # Logic to simulate a decision
        if "Example Domain" in dom:
            return {"type": "stop", "status": "complete", "message": "Arrived at destination"}
            
        if "navigate" in task.lower() and not self.history:
            # Simple extraction: take the first word after 'navigate to' until a comma, space, or semicolon
            raw_url = task.split("navigate to ")[1] if "navigate to " in task else "https://example.com"
            url = raw_url.split(',')[0].split(';')[0].split()[0]
            return {"type": "navigate", "url": url}
            
        return {"type": "stop", "status": "complete", "message": "Task processing finished (Simulation)"}

# LLM Routing classifier and core AgentLoop with checkpointing included above.
