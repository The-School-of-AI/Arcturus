
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from mcp.server.fastmcp import FastMCP
from core.generator import AppGenerator

mcp = FastMCP("app-generator")

@mcp.tool()
async def generate_app(name: str, prompt: str) -> str:
    """
    Generate a new Arcturus App (Frontend UI + Backend Service).
    
    Args:
        name: Name of the application (e.g., "Inventory Tracker")
        prompt: Description of the app requirements and features.
    """
    try:
        generator = AppGenerator(project_root=project_root)
        result = await generator.generate_app(name, prompt)
        return f"✅ App '{name}' generated successfully!\nID: {result['id']}\nPath: {result['path']}\nFiles: ui.json, {', '.join(result.get('backend_files', []))}"
    except Exception as e:
        return f"❌ Failed to generate app: {str(e)}"

if __name__ == "__main__":
    mcp.run()
