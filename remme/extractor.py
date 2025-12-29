import requests
import json
import uuid
import sys
from typing import List, Dict
from pathlib import Path

# Add project root to path and import settings
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings_loader import settings, get_ollama_url, get_model, get_timeout

class RemmeExtractor:
    def __init__(self, model: str = None):
        # Use provided model or default from settings
        self.model = model or get_model("memory_extraction")
        self.api_url = get_ollama_url("chat")

    def extract(self, query: str, conversation_history: List[Dict], existing_memories: List[Dict] = None) -> List[Dict]:
        """
        Extract and Merge memories based on latest interaction.
        Returns a list of commands: [{"action": "add"|"update"|"delete", "text": "...", "id": "..."}]
        """
        
        # 1. Format history into a readable transcript
        transcript = ""
        for msg in conversation_history[-5:]: # Look at a bit more context
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            transcript += f"{role.upper()}: {content}\n"
        
        # Add current query
        transcript += f"USER: {query}\n"
        
        # Format existing memories for the prompt
        memories_str = "NONE"
        if existing_memories:
            memories_str = "\n".join([f"ID: {m['id']} | Fact: {m['text']}" for m in existing_memories])

        # 2. Construct the extraction prompt
        try:
            prompt_path = Path(__file__).parent.parent / "prompts" / "remme_extraction.md"
            base_prompt = prompt_path.read_text().strip()
        except:
            # Fallback to defaults if file missing
            base_prompt = settings["remme"]["extraction_prompt"]

        system_prompt = f"""{base_prompt}

EXISTING RELEVANT MEMORIES:
{memories_str}

OUTPUT FORMAT:
A JSON list of command objects:
[
  {{"action": "add", "text": "Detailed hub fact string"}},
  {{"action": "update", "id": "EXISTING_ID", "text": "Updated multi-part fact string"}},
  {{"action": "delete", "id": "EXISTING_ID"}}
]
"""

        print(f"[DEBUG] RemMe Target Model: {self.model}")
        
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Conversation:\n{transcript}\n\nExtract Facts:"}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1}, # Low temp for deterministic extraction
                    "format": "json" # Enforce JSON mode if supported by model version
                },
                timeout=get_timeout()
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "[]")
            print(f"[DEBUG] Raw Extraction Output ({len(content)} chars): {content}")
            
            # Parse JSON
            try:
                parsed = json.loads(content)
                commands = []
                
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "action" in item:
                            commands.append(item)
                        elif isinstance(item, str):
                            # Backward compatibility: treat raw strings as "add"
                            commands.append({"action": "add", "text": item})
                elif isinstance(parsed, dict):
                    # Handle case where model returns single object or named key
                    if "commands" in parsed and isinstance(parsed["commands"], list):
                        commands = parsed["commands"]
                    elif "action" in parsed:
                        commands = [parsed]
                
                print(f"[DEBUG] Parsed {len(commands)} commands.")
                return commands
            except json.JSONDecodeError:
                print(f"[WARN] Failed to parse JSON from RemMe: {content}")
                return []

        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Ollama Request Failed: {e}")
            return []
        except Exception as e:
            print(f"[ERROR] RemMe Extraction Unexpected Error: {e}")
            return []
