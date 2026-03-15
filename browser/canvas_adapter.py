"""
P06 Canvas - Phantom Browser Canvas Adapter
Handles artifact rendering, base64 encoding, and Canvas schema integration.
"""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from browser.artifacts import PhantomArtifact


@dataclass
class CanvasArtifactPayload:
    """Canvas-compatible artifact wrapper."""
    
    # Required fields
    artifact_id: str
    
    # Fields with defaults
    artifact_type: str = "phantom_page_capture"
    
    # Metadata
    title: str = ""
    description: str = ""
    url: str = ""
    capture_time: str = ""
    
    # Visual
    screenshot_base64: str = ""
    screenshot_mime_type: str = "image/png"
    screenshot_size_bytes: int = 0
    
    # Content
    extracted_text: str = ""
    dom_snapshot: str = ""
    
    # Interactive elements for Canvas rendering
    interactive_elements: list = None
    
    # Cost tracking
    cost_usd: float = 0.0
    cost_tokens: Dict[str, int] = None
    
    # Provenance
    session_id: str = ""
    fetch_duration_ms: float = 0.0
    
    def __post_init__(self):
        """Initialize default values."""
        if self.interactive_elements is None:
            self.interactive_elements = []
        if self.cost_tokens is None:
            self.cost_tokens = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def save_to_file(self, filepath: str | Path) -> None:
        """Save artifact to JSON file."""
        Path(filepath).write_text(self.to_json(), encoding="utf-8")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CanvasArtifactPayload:
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_json(cls, json_str: str) -> CanvasArtifactPayload:
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


class CanvasRenderer:
    """Handles rendering artifacts in Canvas format."""
    
    # Preview router mapping
    CANVAS_ROUTES = {
        "phantom_page_capture": "/preview/phantom",
        "phantom_screenshot": "/preview/phantom/screenshot",
        "phantom_dom": "/preview/phantom/dom",
    }
    
    @classmethod
    def encode_screenshot(cls, image_path: str | Path) -> Tuple[str, int]:
        """
        Encode image file to base64 and get size.
        
        Args:
            image_path: Path to image file
        
        Returns:
            (base64_string, size_in_bytes)
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Read image bytes
        image_bytes = path.read_bytes()
        size_bytes = len(image_bytes)
        
        # Encode to base64
        b64_string = base64.b64encode(image_bytes).decode("utf-8")
        
        return b64_string, size_bytes
    
    @classmethod
    def adapt_artifact(
        cls,
        phantom_artifact: PhantomArtifact,
        screenshot_path: Optional[str | Path] = None
    ) -> CanvasArtifactPayload:
        """
        Convert PhantomArtifact to Canvas format.
        
        Args:
            phantom_artifact: Source artifact from Phantom Browser
            screenshot_path: Optional path to screenshot image
        
        Returns:
            Canvas-compatible artifact payload
        """
        payload = CanvasArtifactPayload(
            artifact_id=phantom_artifact.id,
            artifact_type="phantom_page_capture",
            title=phantom_artifact.title,
            description=f"Web content captured from {phantom_artifact.url}",
            url=phantom_artifact.url,
            capture_time=phantom_artifact.fetch_end_time,
            extracted_text=phantom_artifact.content,
            dom_snapshot=phantom_artifact.dom_snapshot,
            session_id=phantom_artifact.session_id,
            fetch_duration_ms=phantom_artifact.duration_ms,
            cost_usd=phantom_artifact.cost.get("total_cost_usd", 0.0),
            cost_tokens={
                "input_tokens": int(phantom_artifact.cost.get("input_tokens", 0)),
                "output_tokens": int(phantom_artifact.cost.get("output_tokens", 0)),
            },
        )
        
        # Convert interactive elements
        if phantom_artifact.interactive_elements:
            payload.interactive_elements = [
                {
                    "ref": elem.ref,
                    "tag": elem.tag,
                    "role": elem.role,
                    "text": elem.text,
                    "rect": elem.rect,
                }
                for elem in phantom_artifact.interactive_elements
            ]
        
        # Encode screenshot if provided
        if screenshot_path:
            try:
                b64, size = cls.encode_screenshot(screenshot_path)
                payload.screenshot_base64 = b64
                payload.screenshot_size_bytes = size
            except Exception as e:
                # Log warning but don't fail
                print(f"Warning: Failed to encode screenshot: {e}")
        
        # Use pre-encoded screenshot from artifact if available
        elif phantom_artifact.screenshot_b64:
            payload.screenshot_base64 = phantom_artifact.screenshot_b64
            # Estimate size from base64 (roughly 4/3 of actual)
            payload.screenshot_size_bytes = int(len(phantom_artifact.screenshot_b64) * 0.75)
        
        return payload
    
    @classmethod
    def get_preview_route(cls, artifact_type: str) -> Optional[str]:
        """
        Get Canvas preview router endpoint for artifact type.
        
        Args:
            artifact_type: Type of artifact
        
        Returns:
            Preview router path or None if not registered
        """
        return cls.CANVAS_ROUTES.get(artifact_type)
    
    @classmethod
    def register_preview_route(cls, artifact_type: str, route: str) -> None:
        """
        Register a preview route for artifact type.
        
        Args:
            artifact_type: Type of artifact
            route: Preview router endpoint path
        """
        cls.CANVAS_ROUTES[artifact_type] = route


class CanvasPreviewRouter:
    """Preview router registration for Canvas integration."""
    
    _registered_routes: Dict[str, str] = {}
    
    @classmethod
    def register_phantom_routes(cls) -> None:
        """Register all Phantom preview routes with Canvas."""
        routes = {
            "phantom_page_capture": "/preview/phantom/page",
            "phantom_screenshot": "/preview/phantom/screenshot",
            "phantom_dom": "/preview/phantom/dom",
            "phantom_elements": "/preview/phantom/elements",
        }
        
        for artifact_type, route in routes.items():
            cls._registered_routes[artifact_type] = route
    
    @classmethod
    def get_routes(cls) -> Dict[str, str]:
        """Get all registered routes."""
        return cls._registered_routes.copy()
    
    @classmethod
    def resolve_route(cls, artifact_type: str) -> Optional[str]:
        """Resolve artifact type to preview route."""
        return cls._registered_routes.get(artifact_type)


def create_canvas_payload_from_phantom(
    phantom_artifact: PhantomArtifact,
    screenshot_path: Optional[str | Path] = None
) -> CanvasArtifactPayload:
    """
    Factory function to create Canvas payload from Phantom artifact.
    
    Args:
        phantom_artifact: Source artifact
        screenshot_path: Optional screenshot image path
    
    Returns:
        Canvas-compatible payload ready for rendering
    """
    return CanvasRenderer.adapt_artifact(phantom_artifact, screenshot_path)
