from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Optional

from core.visual_explainer_service import generate_html

router = APIRouter(prefix="/visual-explainer", tags=["visual-explainer"])


class GenerateRequest(BaseModel):
    type: str  # "architecture" | "table" | "mermaid" | "raw"
    title: str = ""
    content: Any = {}  # structure depends on type (see docstring below)


class GenerateResponse(BaseModel):
    html: str


# Architecture content shape (when type="architecture"):
#   sections: list of { title, description?, items?, variant?, label? }
#     variant: optional "hero" | "accent" | "green" | "orange" | "sage" | "teal" | "plum" | "recessed"
#     label: optional monospace label above section title
#   subtitle?: string (shown under main title)
#   flowLabels?: list of strings; flowLabels[i] rendered between section[i] and section[i+1]


@router.post("/generate", response_model=GenerateResponse)
async def post_generate(request: GenerateRequest):
    """Generate self-contained HTML for diagrams/tables. No skill class dependency."""
    try:
        html = generate_html(
            diagram_type=request.type,
            title=request.title or "Visual",
            content=request.content,
        )
        return GenerateResponse(html=html)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))