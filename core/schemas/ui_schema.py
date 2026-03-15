
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class Style(BaseModel):
    colors: dict[str, str] = Field(default_factory=lambda: {
        "primary": "#6366f1",
        "secondary": "#a855f7",
        "background": "#0f172a",
        "text": "#f8fafc"
    })
    glassmorphism: bool = True
    gradient_background: str | None = None
    font_family: str = "Inter, sans-serif"

class Component(BaseModel):
    id: str
    type: str # 'hero', 'feature_grid', 'pricing', 'contact_form', 'chart', 'image_carousel'
    title: str | None = None
    content: Any | None = None
    animation: str | None = "fade-in"
    styles: dict[str, Any] | None = None

class Page(BaseModel):
    title: str
    description: str | None = None
    path: str = "/"
    components: list[Component]

class AppSchema(BaseModel):
    name: str
    version: str = "1.0.0"
    theme: Style
    pages: list[Page]
    seo: dict[str, str] = Field(default_factory=lambda: {
        "title": "Generated App",
        "description": "Premium experience powered by Arcturus"
    })

def validate_ui_json(data: dict[str, Any]) -> AppSchema:
    """Validate raw JSON against the AppSchema."""
    return AppSchema(**data)
