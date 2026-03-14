"""
P10 Phantom Browser - Artifact Schema
Provides unified artifact format compatible with P02 Oracle, P05 Chronicle, P06 Canvas, P08 Legion, P12 Aegis.
"""

from __future__ import annotations

import base64
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class InteractiveElement:
    """Represents an interactive element on the page."""
    ref: str  # e.g., "e0", "e1"
    tag: str  # "button", "input", "a", etc.
    role: str  # "button", "link", "textbox", etc.
    text: str  # Button label, placeholder, etc.
    rect: Dict[str, float]  # {x, y, width, height}


@dataclass
class PhantomArtifact:
    """
    Unified artifact format for Phantom Browser outputs.
    Designed to be compatible with all consuming projects.
    
    P02 Oracle: Includes url, title, timestamp for citations
    P05 Chronicle: Includes session_id, start_time, duration_ms for replay
    P06 Canvas: Includes screenshot_b64 for rendering
    P08 Legion: Includes cost for budget tracking
    P12 Aegis: Includes metadata for content verification
    """
    
    # Core identification (required)
    id: str
    session_id: str
    url: str
    title: str
    content: str
    
    # Timestamps (P05 Chronicle requirement)
    fetch_start_time: str  # ISO 8601 UTC
    fetch_end_time: str    # ISO 8601 UTC
    duration_ms: float
    
    # All fields with defaults must come after required fields
    final_url: Optional[str] = None  # After redirects
    
    # Content extraction (P02 Oracle requirement)
    content_length: int = 0  # For tracking
    
    # Visual capture (P06 Canvas requirement)
    screenshot_b64: str = ""  # Base64-encoded PNG for embedding
    screenshot_size_kb: float = 0.0
    
    # DOM analysis
    dom_snapshot: str = ""  # Simplified DOM representation
    interactive_elements: List[InteractiveElement] = field(default_factory=list)
    element_count: int = 0
    
    # Source metadata (P02 Oracle citations)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Cost tracking (P08 Legion budget)
    cost: Dict[str, float] = field(default_factory=lambda: {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_cost_usd": 0.0
    })
    
    # Security & audit (P12 Aegis)
    content_sanitized: bool = False
    sanitization_notes: List[str] = field(default_factory=list)
    injection_checks_passed: bool = True
    
    # Processing status
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling nested dataclasses."""
        data = asdict(self)
        data['interactive_elements'] = [
            asdict(el) if isinstance(el, InteractiveElement) else el
            for el in self.interactive_elements
        ]
        return data
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def save_to_file(self, output_path: Path) -> None:
        """Save artifact to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(self.to_json())
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> PhantomArtifact:
        """Reconstruct from dictionary."""
        if 'interactive_elements' in data:
            data['interactive_elements'] = [
                InteractiveElement(**el) if isinstance(el, dict) else el
                for el in data['interactive_elements']
            ]
        return PhantomArtifact(**data)
    
    @staticmethod
    def from_json(json_str: str) -> PhantomArtifact:
        """Reconstruct from JSON string."""
        return PhantomArtifact.from_dict(json.loads(json_str))


def encode_screenshot_to_base64(file_path: Path) -> str:
    """Encode a screenshot file to base64 string."""
    with open(file_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def create_artifact(
    artifact_id: str,
    session_id: str,
    url: str,
    title: str,
    content: str,
    dom_snapshot: str,
    interactive_elements: List[InteractiveElement],
    screenshot_b64: str,
    screenshot_size_kb: float = 0.0,
    duration_ms: float = 0.0,
) -> PhantomArtifact:
    """
    Factory function to create a PhantomArtifact.
    
    Args:
        artifact_id: Unique artifact identifier
        session_id: Session this artifact belongs to
        url: URL that was navigated to
        title: Page title
        content: Extracted text content
        dom_snapshot: Simplified DOM representation
        interactive_elements: List of clickable elements
        screenshot_b64: Base64-encoded screenshot
        screenshot_size_kb: Size of screenshot in KB
        duration_ms: Time taken to fetch and process
    
    Returns:
        Populated PhantomArtifact instance
    """
    now = datetime.utcnow().isoformat() + "Z"
    
    return PhantomArtifact(
        id=artifact_id,
        session_id=session_id,
        url=url,
        title=title,
        content=content,
        content_length=len(content),
        fetch_start_time=now,
        fetch_end_time=now,
        duration_ms=duration_ms,
        screenshot_b64=screenshot_b64,
        screenshot_size_kb=screenshot_size_kb,
        dom_snapshot=dom_snapshot,
        interactive_elements=interactive_elements,
        element_count=len(interactive_elements),
        metadata={
            "http_status": 200,
            "content_type": "text/html",
            "charset": "utf-8"
        }
    )
