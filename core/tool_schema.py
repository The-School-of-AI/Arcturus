
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, ValidationError

class ToolInputSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None

class ToolDefinition(BaseModel):
    name: str # The function name
    description: str = Field(..., min_length=1, description="Tool description (from docstring)")
    inputSchema: ToolInputSchema

    @field_validator('description')
    def description_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Tool description (docstring) cannot be empty')
        return v
    
    @field_validator('name')
    def name_must_be_snake_case(cls, v):
        if not v.islower() or ' ' in v:
             # simple check, maybe regex for strict snake_case
             pass
        return v

class InvalidToolDefinition(Exception):
    """Raised when a tool definition fails validation."""
    pass

def validate_tool_definition(tool_data: dict) -> ToolDefinition:
    """
    Validate a raw tool dictionary against strict schema.
    Raises InvalidToolDefinition if validation fails.
    """
    try:
        return ToolDefinition(**tool_data)
    except ValidationError as e:
        raise InvalidToolDefinition(f"Invalid Tool Definition for '{tool_data.get('name', 'unknown')}': {e}")
