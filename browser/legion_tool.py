"""
P08 Legion - Phantom Browser Tool Interface
Provides Legion-compatible tool endpoint for browser automation as a worker service.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolInput:
    """Input schema for Phantom Browser tool."""
    action: str
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    direction: Optional[str] = None
    amount: Optional[int] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Result schema for Phantom Browser tool."""
    success: bool
    action: str
    status: str
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    cost: Dict[str, float] = field(default_factory=dict)
    step: int = 0


class LegionToolInterface:
    """
    Tool interface compatible with P08 Legion worker agents.
    
    Allows Legion workers to invoke Phantom Browser as a tool with:
    - Structured input/output
    - Cost tracking (tokens, USD)
    - Step counter for action tracing
    - Error handling and recovery
    """
    
    SUPPORTED_ACTIONS = [
        "navigate",
        "click",
        "type",
        "scroll",
        "take_screenshot",
        "get_content",
        "select_option",
        "upload_file",
        "drag_and_drop",
        "switch_tab",
        "close_tab",
    ]
    
    def __init__(self, controller: Any = None):
        """
        Initialize Legion tool interface.
        
        Args:
            controller: BrowserController instance
        """
        self.controller = controller
        self.execution_log: List[ToolResult] = []
    
    def validate_input(self, tool_input: ToolInput) -> tuple[bool, Optional[str]]:
        """
        Validate tool input.
        
        Returns:
            (is_valid, error_message)
        """
        if not tool_input.action:
            return False, "action is required"
        
        if tool_input.action not in self.SUPPORTED_ACTIONS:
            return False, f"Unsupported action: {tool_input.action}"
        
        # Action-specific validation
        if tool_input.action in ["navigate"]:
            if not tool_input.url:
                return False, f"{tool_input.action} requires url"
        
        if tool_input.action in ["click", "select_option"]:
            if not tool_input.selector:
                return False, f"{tool_input.action} requires selector"
        
        if tool_input.action == "type":
            if not tool_input.selector or not tool_input.text:
                return False, "type requires selector and text"
        
        if tool_input.action == "scroll":
            if not tool_input.direction or tool_input.direction not in ["up", "down"]:
                return False, "scroll requires direction (up/down)"
        
        return True, None
    
    async def execute(
        self,
        tool_input: ToolInput,
    ) -> ToolResult:
        """
        Execute a tool action and return result.
        
        Args:
            tool_input: Action specification
        
        Returns:
            ToolResult with status, data, cost metrics
        """
        import time
        from datetime import datetime
        
        start_time = time.time()
        
        # Validate input
        is_valid, error = self.validate_input(tool_input)
        if not is_valid:
            return ToolResult(
                success=False,
                action=tool_input.action,
                status="validation_failed",
                error=error,
                execution_time_ms=0,
                cost={"input_tokens": 0, "output_tokens": 0, "total_cost_usd": 0.0},
                step=self.controller.get_step_counter() if self.controller else 0,
            )
        
        try:
            if not self.controller:
                return ToolResult(
                    success=False,
                    action=tool_input.action,
                    status="error",
                    error="No controller available",
                    execution_time_ms=0,
                    cost={"input_tokens": 0, "output_tokens": 0, "total_cost_usd": 0.0},
                    step=0,
                )
            
            result_data = {}
            
            # Execute action
            if tool_input.action == "navigate":
                await self.controller.navigate(tool_input.url)
                result_data["url"] = tool_input.url
                status = "success"
            
            elif tool_input.action == "click":
                await self.controller.click(tool_input.selector)
                result_data["selector"] = tool_input.selector
                status = "success"
            
            elif tool_input.action == "type":
                await self.controller.type(tool_input.selector, tool_input.text)
                result_data["selector"] = tool_input.selector
                result_data["text_length"] = len(tool_input.text)
                status = "success"
            
            elif tool_input.action == "scroll":
                await self.controller.scroll(
                    direction=tool_input.direction,
                    amount=tool_input.amount or 500
                )
                result_data["direction"] = tool_input.direction
                result_data["amount"] = tool_input.amount or 500
                status = "success"
            
            elif tool_input.action == "take_screenshot":
                screenshot_path = await self.controller.get_screenshot()
                result_data["screenshot_path"] = screenshot_path
                status = "success"
            
            elif tool_input.action == "get_content":
                content = await self.controller.get_page_content()
                result_data["content_length"] = len(content)
                result_data["content_preview"] = content[:500]
                status = "success"
            
            elif tool_input.action == "select_option":
                if not tool_input.text:
                    raise ValueError("select_option requires text (value) parameter")
                await self.controller.select_option(tool_input.selector, tool_input.text)
                result_data["selector"] = tool_input.selector
                result_data["value"] = tool_input.text
                status = "success"
            
            elif tool_input.action == "upload_file":
                files = tool_input.extra_data.get("files", [])
                if not files:
                    raise ValueError("upload_file requires files in extra_data")
                await self.controller.upload_file(tool_input.selector, files)
                result_data["selector"] = tool_input.selector
                result_data["file_count"] = len(files)
                status = "success"
            
            elif tool_input.action == "drag_and_drop":
                if not tool_input.extra_data.get("target_selector"):
                    raise ValueError("drag_and_drop requires target_selector")
                await self.controller.drag_and_drop(
                    tool_input.selector,
                    tool_input.extra_data["target_selector"]
                )
                result_data["source_selector"] = tool_input.selector
                result_data["target_selector"] = tool_input.extra_data["target_selector"]
                status = "success"
            
            elif tool_input.action == "switch_tab":
                tab_index = tool_input.extra_data.get("index", 0)
                await self.controller.switch_tab(tab_index)
                result_data["tab_index"] = tab_index
                status = "success"
            
            elif tool_input.action == "close_tab":
                tab_index = tool_input.extra_data.get("index", 0)
                await self.controller.close_tab(tab_index)
                result_data["tab_index"] = tab_index
                status = "success"
            
            else:
                return ToolResult(
                    success=False,
                    action=tool_input.action,
                    status="error",
                    error=f"Action not implemented: {tool_input.action}",
                    execution_time_ms=time.time() - start_time,
                    cost=self.controller.get_cost(),
                    step=self.controller.get_step_counter(),
                )
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Get current cost metrics
            cost = self.controller.get_cost()
            
            result = ToolResult(
                success=True,
                action=tool_input.action,
                status=status,
                data=result_data,
                error=None,
                execution_time_ms=execution_time_ms,
                cost=cost,
                step=self.controller.get_step_counter(),
            )
            
            self.execution_log.append(result)
            return result
        
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return ToolResult(
                success=False,
                action=tool_input.action,
                status="error",
                error=str(e),
                execution_time_ms=execution_time_ms,
                cost=self.controller.get_cost() if self.controller else {},
                step=self.controller.get_step_counter() if self.controller else 0,
            )
    
    def get_execution_log(self) -> List[ToolResult]:
        """Get log of executed tool actions."""
        return self.execution_log.copy()
    
    def to_mcp_tool_definition(self) -> Dict[str, Any]:
        """
        Generate MCP (Model Context Protocol) tool definition for Legion.
        
        Returns:
            Tool definition compatible with MCP servers
        """
        return {
            "name": "phantom_browser",
            "description": "Execute browser automation actions using Phantom Browser",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": self.SUPPORTED_ACTIONS,
                        "description": "Action to execute"
                    },
                    "url": {
                        "type": "string",
                        "description": "URL for navigation action"
                    },
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for click/type/select actions"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type or value to select"
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down"],
                        "description": "Scroll direction"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Scroll amount in pixels"
                    },
                    "extra_data": {
                        "type": "object",
                        "description": "Additional action-specific data"
                    }
                },
                "required": ["action"]
            }
        }


def create_legion_tool(controller: Any = None) -> LegionToolInterface:
    """
    Factory function to create a Legion-compatible Phantom Browser tool.
    
    Args:
        controller: BrowserController instance
    
    Returns:
        LegionToolInterface instance
    """
    return LegionToolInterface(controller)
