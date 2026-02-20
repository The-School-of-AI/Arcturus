from pydantic import BaseModel, Field
from typing import List, Union, Dict, Any, Optional

class UIComponent(BaseModel):
    id: str
    component: str  # Discriminator (e.g., "Button", "LineChart", "MonacoEditor")
    props: Dict[str, Any] = Field(default_factory=dict)
    children: List[str] = Field(default_factory=list) # IDs of children (flattened adjacency list)

class CreateSurfaceMessage(BaseModel):
    type: str = "createSurface"
    surfaceId: str
    catalogId: Optional[str] = "default"
    title: Optional[str] = "New Canvas"

class UpdateComponentsMessage(BaseModel):
    type: str = "updateComponents"
    surfaceId: str
    components: List[UIComponent]

class UpdateDataModelMessage(BaseModel):
    type: str = "updateDataModel"
    surfaceId: str
    data: Dict[str, Any]  # The delta or full state

class DeleteSurfaceMessage(BaseModel):
    type: str = "deleteSurface"
    surfaceId: str

class EvalJSMessage(BaseModel):
    type: str = "evalJS"
    surfaceId: str
    code: str

class UserEventMessage(BaseModel):
    type: str = "user_event"
    surfaceId: str
    event_type: str  # e.g., "click", "input", "submit"
    component_id: str
    data: Dict[str, Any] = Field(default_factory=dict)

class CanvasMessage(BaseModel):
    """Union type for all canvas-related messages."""
    msg: Union[
        CreateSurfaceMessage, 
        UpdateComponentsMessage, 
        UpdateDataModelMessage, 
        DeleteSurfaceMessage,
        EvalJSMessage,
        UserEventMessage
    ]
