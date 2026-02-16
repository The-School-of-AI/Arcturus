
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class PreviewResponse(BaseModel):
    viewer: str  # 'pdf', 'markdown', 'code', 'image', 'web', 'json', 'dag', 'docx'
    url: Optional[str] = None
    content: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = {}

class PreviewManager:
    """Central logic for determining how to preview any content (local file or remote URL)."""
    
    EXTENSION_MAP = {
        '.pdf': 'pdf',
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.png': 'image',
        '.jpg': 'image',
        '.jpeg': 'image',
        '.gif': 'image',
        '.webp': 'image',
        '.docx': 'docx',
        '.doc': 'docx',
        # Code types
        '.py': 'code',
        '.js': 'code',
        '.ts': 'code',
        '.tsx': 'code',
        '.jsx': 'code',
        '.css': 'code',
        '.html': 'code',
        '.sh': 'code',
        '.txt': 'code',
        '.json': 'json' # Might be refined to 'dag' or 'app' later
    }

    @classmethod
    def get_preview_for_file(cls, file_path: str, title: Optional[str] = None) -> PreviewResponse:
        path = Path(file_path)
        if not path.exists():
            return PreviewResponse(viewer='markdown', content=f"### ❌ File Not Found\n`{file_path}`")
        
        ext = path.suffix.lower()
        if ext and ext not in cls.EXTENSION_MAP:
            import logging
            logging.warning(f"⚠️ No specific viewer found for extension '{ext}' in {file_path}. Defaulting to 'code'.")
            viewer = 'code'
        else:
            viewer = cls.EXTENSION_MAP.get(ext, 'code')
        
        # Binary special handling (return URLs instead of content)
        if viewer in ['pdf', 'image', 'docx']:
            # These usually require a dedicated binary endpoint to serve the stream
            # We'll assume the URL construction happens at the router level or use a standard pattern
            return PreviewResponse(
                viewer=viewer,
                url=f"/rag/document_content?path={os.path.abspath(file_path)}",
                title=title or path.name,
                metadata={"size": path.stat().st_size}
            )
        
        # Text based handling
        try:
            content = path.read_text(errors='replace')
            
            # Refine JSON
            if viewer == 'json':
                try:
                    data = json.loads(content)
                    # Check for Plan Graph
                    if isinstance(data, dict) and (("nodes" in data and "links" in data) or ("graph" in data)):
                        viewer = 'dag'
                    # Check for App Schema
                    elif isinstance(data, dict) and "theme" in data and "pages" in data:
                        viewer = 'app'
                except:
                    pass

            return PreviewResponse(
                viewer=viewer,
                content=content,
                title=title or path.name,
                metadata={"extension": ext}
            )
        except Exception as e:
            return PreviewResponse(viewer='markdown', content=f"### ❌ Error Reading File\n{str(e)}")

    @classmethod
    def get_preview_for_url(cls, url: str) -> PreviewResponse:
        """Determines best viewer for a remote URL."""
        lower_url = url.lower()
        
        if lower_url.endswith('.pdf') or 'arxiv.org/pdf/' in lower_url:
            return PreviewResponse(viewer='pdf', url=url)
        
        if any(lower_url.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
            return PreviewResponse(viewer='image', url=url)
            
        # Default to web viewer (iframe)
        return PreviewResponse(viewer='web', url=url)

# Helper for singleton usage
def get_preview(path_or_url: str, title: Optional[str] = None) -> PreviewResponse:
    if path_or_url.startswith(('http://', 'https://')):
        return PreviewManager.get_preview_for_url(path_or_url)
    return PreviewManager.get_preview_for_file(path_or_url, title)
