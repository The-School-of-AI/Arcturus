from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
import httpx
from pathlib import Path
from shared.state import PROJECT_ROOT
from .browser_utils import perform_web_search, extract_url_content

router = APIRouter(prefix="/ide", tags=["IDE Agent"])

@router.post("/tools/search")
async def tool_search(request: Request):
    try:
        body = await request.json()
        query = body.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Missing query")
        return await perform_web_search(query)
    except Exception as e:
        return f"[Error] {e}"

@router.post("/tools/read-url")
async def tool_read_url(request: Request):
    try:
        body = await request.json()
        url = body.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="Missing url")
        return await extract_url_content(url)
    except Exception as e:
        return f"[Error] {e}"

@router.post("/ask")
async def ask_ide_agent(request: Request):
    """
    Interactive chat with the IDE Agent.
    - Uses the standard AgentRunner with 'IDEAgent' profile.
    - Respects centralized model settings.
    """
    try:
        body = await request.json()
        query = body.get("query")
        history = body.get("history", [])
        images = body.get("images", [])
        
        from shared.state import get_agent_runner, PROJECT_ROOT
        runner = get_agent_runner()

        if not query:
            raise HTTPException(status_code=400, detail="Missing query")

        # Prepare input data for the agent
        input_data = {
            "task": query,
            "history": history,
            "project_root": str(PROJECT_ROOT)
        }

        # Handle images if provided
        image_path = None
        if images:
            img_dir = PROJECT_ROOT / ".arcturus" / "images"
            img_dir.mkdir(parents=True, exist_ok=True)
            import base64
            import time
            
            img_data = images[0]
            if "," in img_data:
                _, b64_str = img_data.split(",", 1)
            else:
                b64_str = img_data
                
            image_path = str(img_dir / f"ide_input_{int(time.time())}.png")
            Path(image_path).write_bytes(base64.b64decode(b64_str))

        # Run the agent
        result = await runner.run_agent("IDEAgent", input_data, image_path=image_path)
        
        if not result["success"]:
            return {"response": f"Error: {result.get('error', 'Unknown failure')}", "status": "failed"}

        output = result["output"]
        if isinstance(output, str):
            response_text = output
        else:
            response_text = output.get("response", output.get("answer", output.get("output", str(output))))
        
        # ✅ 46. Memory Stream Integration
        try:
            from core.episodic_memory import EpisodicMemory
            import time
            session_id = f"ide_{int(time.time())}"
            session_data = {
                "graph": {
                    "session_id": session_id,
                    "original_query": query,
                    "status": "completed",
                    "final_cost": output.get("cost", 0) if isinstance(output, dict) else 0
                },
                "nodes": [
                    {
                        "id": "chat_0",
                        "agent": "IDEAgent",
                        "description": query,
                        "status": "completed",
                        "output": output,
                        "agent_prompt": "Standard IDE Chat"
                    }
                ]
            }
            await EpisodicMemory().save_episode(session_data)
        except Exception as e:
            print(f"Failed to save IDE episode: {e}")

        return {
            "response": response_text,
            "status": "success",
            "metadata": {
                "model": output.get("executed_model", "unknown") if isinstance(output, dict) else "unknown",
                "cost": output.get("cost", 0) if isinstance(output, dict) else 0,
                "session_id": session_id
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
