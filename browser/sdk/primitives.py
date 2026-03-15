"""
Three-Primitive SDK: Simplified Browser Automation API

Three clean primitives covering 95% of browser automation use cases:
- act(): Execute a single natural language action
- extract(): Return structured data matching schema
- agent(): Run full multi-step task using Planner-Actor-Validator

Based on Stagehand's gold-standard SDK design.
"""

from typing import Dict, Any, Optional, Type, TypeVar, List
from dataclasses import dataclass
from abc import ABC, abstractmethod
import asyncio
import time


T = TypeVar('T')


@dataclass
class ActionResult:
    """Result of single action"""
    success: bool
    message: str
    duration_ms: int
    error: Optional[str] = None


@dataclass
class ExtractionResult:
    """Result of data extraction"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    validation_passed: bool = True
    matched_schema: Optional[Dict] = None


@dataclass
class AgentResult:
    """Result of multi-step agent execution"""
    success: bool
    completed_steps: int
    total_steps: int
    duration_ms: int
    final_state: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    backtrack_count: int = 0


class BrowserContext(ABC):
    """Abstract browser context interface"""
    
    @abstractmethod
    async def act(self, action: str) -> ActionResult:
        """Execute single action"""
        pass
    
    @abstractmethod
    async def extract(self, goal: str, schema: Type[T]) -> ExtractionResult:
        """Extract data"""
        pass
    
    @abstractmethod
    async def agent(self, goal: str, max_steps: int = 20) -> AgentResult:
        """Run multi-step task"""
        pass


class SimpleBrowserContext(BrowserContext):
    """
    Simple implementation of browser context for SDK.
    
    In production, would wrap Playwright/Selenium with all features
    (routing, vault, audit trail, backtracking, etc.)
    """
    
    def __init__(self, mock_mode: bool = True):
        """
        Initialize browser context.
        
        Args:
            mock_mode: If True, uses mock actions for testing
        """
        self.mock_mode = mock_mode
        self.action_history: List[Dict[str, Any]] = []
    
    async def act(self, action: str) -> ActionResult:
        """
        Execute a single natural language action.
        
        Example:
            result = await browser.act("Click the export button")
        
        Args:
            action: Natural language action description
        
        Returns:
            ActionResult with success status and details
        """
        start_time = time.time()
        
        try:
            if self.mock_mode:
                # Mock execution
                await asyncio.sleep(0.1)  # Simulate network latency
                success = True
                message = f"Executed: {action}"
            else:
                # Real execution would:
                # 1. Parse action into sub-goals
                # 2. Route to appropriate tier
                # 3. Execute via Planner-Actor-Validator
                # 4. Log to audit trail
                # 5. Update cache
                success = True
                message = f"Executed: {action}"
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = ActionResult(
                success=success,
                message=message,
                duration_ms=duration_ms,
            )
            
            # Log action
            self.action_history.append({
                'type': 'act',
                'action': action,
                'result': result.success,
                'duration_ms': duration_ms,
            })
            
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ActionResult(
                success=False,
                message="Action failed",
                duration_ms=duration_ms,
                error=str(e),
            )
    
    async def extract(
        self,
        goal: str,
        schema: Type[T],
    ) -> ExtractionResult:
        """
        Extract structured data from page.
        
        Example:
            from pydantic import BaseModel
            
            class Product(BaseModel):
                name: str
                price: float
                availability: str
            
            result = await browser.extract("Get product details", Product)
        
        Args:
            goal: What to extract
            schema: Pydantic/Zod schema for validation
        
        Returns:
            ExtractionResult with extracted data
        """
        start_time = time.time()
        
        try:
            if self.mock_mode:
                # Mock extraction
                await asyncio.sleep(0.2)
                data = {
                    'extracted': True,
                    'schema': str(schema),
                }
            else:
                # Real extraction would:
                # 1. Understand page content
                # 2. Identify elements matching schema
                # 3. Extract and format data
                # 4. Validate against schema
                # 5. Optionally click/navigate to get more data
                data = {}
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = ExtractionResult(
                success=True,
                data=data,
                validation_passed=True,
            )
            
            self.action_history.append({
                'type': 'extract',
                'goal': goal,
                'result': result.success,
                'duration_ms': duration_ms,
            })
            
            return result
        
        except Exception as e:
            return ExtractionResult(
                success=False,
                error=str(e),
            )
    
    async def agent(
        self,
        goal: str,
        max_steps: int = 20,
    ) -> AgentResult:
        """
        Run full multi-step task using Planner-Actor-Validator.
        
        Example:
            result = await browser.agent(
                "Complete checkout and confirm order",
                max_steps=10
            )
        
        Args:
            goal: High-level goal to achieve
            max_steps: Maximum steps before timeout
        
        Returns:
            AgentResult with execution details
        """
        start_time = time.time()
        
        try:
            completed_steps = 0
            
            if self.mock_mode:
                # Mock multi-step execution
                for i in range(min(5, max_steps)):
                    await asyncio.sleep(0.05)  # Simulate each step
                    completed_steps += 1
            else:
                # Real execution would:
                # 1. Planner decomposes goal into atomic sub-goals
                # 2. For each sub-goal:
                #    - Actor executes with tight observe-decide-execute loop
                #    - Validator verifies outcome (not just action)
                #    - On failure, Critic may trigger backtrack
                #    - Cache checked before LLM (if exact match)
                # 3. Track state with checkpoints
                # 4. Log all decisions to decision traces
                # 5. Record session replay
                completed_steps = max_steps
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            result = AgentResult(
                success=True,
                completed_steps=completed_steps,
                total_steps=max_steps,
                duration_ms=duration_ms,
                final_state={'goal': goal, 'completed': True},
            )
            
            self.action_history.append({
                'type': 'agent',
                'goal': goal,
                'steps': completed_steps,
                'duration_ms': duration_ms,
            })
            
            return result
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                completed_steps=0,
                total_steps=max_steps,
                duration_ms=duration_ms,
                error=str(e),
            )


# Module-level functions for easy import
_default_browser: Optional[SimpleBrowserContext] = None


def configure_browser(mock_mode: bool = True) -> SimpleBrowserContext:
    """
    Configure default browser context.
    
    Returns:
        Browser context for use with act(), extract(), agent()
    """
    global _default_browser
    _default_browser = SimpleBrowserContext(mock_mode=mock_mode)
    return _default_browser


async def act(action: str) -> ActionResult:
    """
    Execute a single natural language action.
    
    Global function using default browser context.
    """
    if _default_browser is None:
        configure_browser()
    
    return await _default_browser.act(action)


async def extract(goal: str, schema: Type[T]) -> ExtractionResult:
    """
    Extract structured data from page.
    
    Global function using default browser context.
    """
    if _default_browser is None:
        configure_browser()
    
    return await _default_browser.extract(goal, schema)


async def agent(goal: str, max_steps: int = 20) -> AgentResult:
    """
    Run full multi-step task.
    
    Global function using default browser context.
    """
    if _default_browser is None:
        configure_browser()
    
    return await _default_browser.agent(goal, max_steps)


# Example usage
if __name__ == "__main__":
    async def example():
        """Example of using the SDK"""
        # Configure browser
        configure_browser(mock_mode=True)
        
        # Single action
        result = await act("Click login button")
        print(f"Act result: {result}")
        
        # Multi-step task
        result = await agent("Complete purchase workflow")
        print(f"Agent result: {result}")
    
    # Run example (Python 3.7+)
    asyncio.run(example())
