
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Any

class Style(BaseModel):
    colors: Dict[str, str] = Field(default_factory=lambda: {
        "primary": "#6366f1",
        "secondary": "#a855f7",
        "background": "#0f172a",
        "text": "#f8fafc"
    })
    glassmorphism: bool = True
    gradient_background: Optional[str] = None
    font_family: str = "Inter, sans-serif"

class Component(BaseModel):
    id: str
    type: str # 'hero', 'feature_grid', 'pricing', 'contact_form', 'chart', 'image_carousel'
    title: Optional[str] = None
    content: Optional[Any] = None
    animation: Optional[str] = "fade-in"
    styles: Optional[Dict[str, Any]] = None

class Page(BaseModel):
    title: str
    description: Optional[str] = None
    path: str = "/"
    components: List[Component]

class AppSchema(BaseModel):
    name: str
    version: str = "1.0.0"
    theme: Style
    pages: List[Page]
    seo: Dict[str, str] = Field(default_factory=lambda: {
        "title": "Generated App",
        "description": "Premium experience powered by Arcturus"
    })

def validate_ui_json(data: Dict[str, Any]) -> AppSchema:
    """Validate raw JSON against the AppSchema."""
    return AppSchema(**data)
