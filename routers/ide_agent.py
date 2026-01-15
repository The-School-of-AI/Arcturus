from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import json
import httpx
from pathlib import Path
from shared.state import PROJECT_ROOT

router = APIRouter(prefix="/ide", tags=["IDE Agent"])

@router.post("/ask")
async def ask_ide_agent(request: Request):
    """
    Interactive chat with the IDE Agent.
    - Loads system prompt from `prompts/ide_agent_prompt.md`
    - Injects project context
    - Streams response from Ollama
    """
    try:
        body = await request.json()
        query = body.get("query")
        history = body.get("history", [])
        image = body.get("image") # Base64
        tools = body.get("tools")
        project_root = body.get("project_root", str(PROJECT_ROOT))
        model = body.get("model", "qwen3-vl:8b")

        if not query:
            raise HTTPException(status_code=400, detail="Missing query")

        # 1. Load System Prompt
        prompt_path = PROJECT_ROOT / "prompts" / "ide_agent_prompt.md"
        base_system_prompt = prompt_path.read_text() if prompt_path.exists() else "You are a helpful coding assistant."

        # 2. Augment System Prompt
        system_prompt = f"""{base_system_prompt}

CRITICAL: Your current working directory (project root) is: {project_root}
All file operations MUST be relative to this root.

SHELL ENVIRONMENT:
- You are in a NON-INTERACTIVE shell. 
- NEVER use commands that wait for user input (e.g., `input()` in Python, `read` in bash). 
- If you write scripts, use `sys.argv` to accept arguments.
  Example: `script.py arg1 arg2` instead of interactive prompts.
- Prefer `python3` over `python` for execution.
- If a command hangs, it will be killed after 60 seconds.

CRITICAL: Always start your response with a thinking process enclosed in <think> tags. 
Analyze the user request, checks the tools available, and plan your answer before providing the final response or tool call.

"""
        if tools:
            tools_desc = json.dumps(tools, indent=2)
            system_prompt += f"""
### AGENT TOOLS
To use a tool, you MUST output a valid JSON block enclosed in markdown code fences:

```json
{{
  "tool": "tool_name",
  "args": {{ "arg_name": "value" }}
}}
```

Available Tools:
{tools_desc}
"""

        # 3. Construct Messages
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add history (limit to last 10 turns to save context)
        for msg in history[-10:]: 
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            
        user_msg = {"role": "user", "content": query}
        if image:
            if "," in image: image = image.split(",")[1]
            user_msg["images"] = [image]
        messages.append(user_msg)

        # 4. Stream Response
        async def token_generator():
            try:
                async with httpx.AsyncClient(timeout=300) as client:
                    async with client.stream("POST", "http://127.0.0.1:11434/api/chat", json={
                        "model": model, 
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": 0.3 # Lower temperature for coding
                        }
                    }) as response:
                        async for line in response.aiter_lines():
                            if not line: continue
                            try:
                                data = json.loads(line)
                                chunk = data.get("message", {}).get("content", "")
                                if chunk:
                                    yield f"data: {json.dumps({'content': chunk})}\n\n"
                                if data.get("done"):
                                    break
                            except:
                                continue
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(token_generator(), media_type="text/event-stream")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
