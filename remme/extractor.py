import requests
import json
import uuid
from typing import List, Dict
from .utils import EMBED_URL, OLLAMA_TIMEOUT

class RemmeExtractor:
    def __init__(self, model: str = "qwen3-vl:8b"): # Using 8b as default for speed/quality balance
        self.model = model
        self.api_url = "http://127.0.0.1:11434/api/chat"

    def extract(self, query: str, conversation_history: List[Dict]) -> List[str]:
        """
        Extract atomic facts from the latest interaction.
        Returns a list of string facts.
        """
        
        # 1. Format history into a readable transcript
        transcript = ""
        for msg in conversation_history[-3:]: # Look at last few turns
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            transcript += f"{role.upper()}: {content}\n"
        
        # Add current query
        transcript += f"USER: {query}\n"
        
        # 2. Construct the extraction prompt
        system_prompt = """You are a Memory Extraction AI. 
Your job is to read the conversation and extract "Atomic Facts" about the USER.
Rules:
1. ONLY extract facts about the User (preferences, details, projects, identity).
2. INTENTION matters: If user says "I want to use Python", fact is "User prefers Python".
3. Ignore transient chit-chat ("Hello", "Thanks").
4. Ignore questions unless they reveal a preference ("How do I use React?" -> "User is using React").
5. Output MUST be a JSON list of strings.
6. If no relevant facts found, output [].

Example Input:
USER: My name is Rohan. I'm building a graph app.
Output:
["User's name is Rohan", "User is building a graph application"]
"""

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
                timeout=OLLAMA_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "[]")
            print(f"[DEBUG] Raw Extraction Output: {content}")
            
            # Parse JSON
            try:
                facts = json.loads(content)
                if isinstance(facts, list):
                    return [str(f) for f in facts if isinstance(f, (str, int, float))]
                return []
            except json.JSONDecodeError:
                # Fallback: aggressive parsing if model chats instead of JSON
                print(f"Failed to parse extraction JSON: {content}")
                return []
                
        except Exception as e:
            print(f"Extraction failed: {e}")
            return []
