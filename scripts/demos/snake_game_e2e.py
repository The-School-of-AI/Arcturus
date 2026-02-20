import asyncio
import sys
from pathlib import Path

# Add project root to path
# scripts/demos/snake_game_e2e.py -> 3 parents to reach Arcturus/
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
sys.path.append(str(PROJECT_ROOT))

async def main():
    from core.loop import AgentLoop4
    from shared.state import get_multi_mcp
    
    multi_mcp = get_multi_mcp()
    loop = AgentLoop4(multi_mcp)
    
    query = (
        "Create a simple playable Snake Game in a single HTML file with CSS and JS. "
        "Use Python's open() to save it to 'output/snake.html'. "
        "IMPORTANT: In your Python code, use single quotes or escaped double quotes for the HTML string "
        "to avoid triple-quote conflicts with the sandbox injection logic."
    )
    
    file_manifest = "Arcturus Core System"
    globals_schema = {}
    uploaded_files = []
    
    print(f"🚀 [E2E] Starting Snake Game Generation...")
    print(f"📝 Query: {query}")
    print(f"📂 Project Root: {PROJECT_ROOT}")
    
    try:
        context = await loop.run(query, file_manifest, globals_schema, uploaded_files)
        
        status = context.plan_graph.graph['status']
        session_id = context.plan_graph.graph['session_id']
        
        print(f"\n✨ [E2_FINISHED] Status: {status}")
        print(f"🆔 Session ID: {session_id}")
        
        output_path = PROJECT_ROOT / "output" / "snake.html"
        if output_path.exists():
            print(f"🎮 Success! Game generated at: {output_path}")
            print(f"🔗 Preview: file:///{output_path.as_posix()}")
        else:
            print(f"❌ Failure: 'output/snake.html' not found.")
            
    except Exception as e:
        import traceback
        print(f"❌ [E2E_ERROR] pipeline failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
