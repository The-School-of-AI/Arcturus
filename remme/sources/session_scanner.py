"""
Session Scanner - Extracts preferences from session summaries.

Scans memory/session_summaries_index/ for user preferences expressed
during conversations and adds them to staging queue.
"""

import json
import requests
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings_loader import get_model, get_ollama_url, get_timeout
from remme.staging import get_staging_store
from remme.sources.scan_tracker import get_scan_tracker


SESSION_EXTRACTION_PROMPT = """Extract user preferences from this conversation.

Look for explicit or implicit:
- Tech preferences (languages, tools, frameworks)
- Food/dietary preferences
- Work context (role, industry, company)
- Location, personal details
- Communication style preferences

CONVERSATION:
{content}

Return a JSON object with preferences found. Example: {{"language": "python", "dietary": "vegetarian"}}
Return {{}} if no personal preferences found.
JSON only, no explanation."""


class SessionScanner:
    """
    Scans session summaries for preference extraction.
    """
    
    def __init__(self, summaries_dir: str = "memory/session_summaries_index"):
        # Resolve path relative to project root (assuming this file is in remme/sources)
        self.project_root = Path(__file__).parent.parent.parent
        self.summaries_dir = self.project_root / summaries_dir
        self.model = get_model("memory_extraction")
        self.api_url = get_ollama_url("chat")
        self.staging = get_staging_store()
    
    def get_session_files(self, max_files: int = 100) -> List[Path]:
        """Get session summary files (including subdirectories)."""
        if not self.summaries_dir.exists():
            print(f"⚠️ Sessions directory not found: {self.summaries_dir}")
            return []
        
        # Use rglob to find files in subdirectories (2025/, 2026/, etc.)
        files = list(self.summaries_dir.rglob("*.json"))
        # Sort by modification time, newest first
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        return files[:max_files]
    
    def extract_from_session(self, session_path: Path) -> Dict:
        """Extract preferences from a session summary."""
        try:
            session_data = json.loads(session_path.read_text())
            
            content_parts = []
            
            # --- Schema 1: Legacy (summary, history) ---
            if "summary" in session_data or "history" in session_data:
                # Add summary if present
                if "summary" in session_data:
                    content_parts.append(f"Summary: {session_data['summary']}")
                
                # Add conversation history
                if "history" in session_data:
                    for msg in session_data["history"][-15:]:  # Last 15 messages
                        role = msg.get("role", "unknown")
                        text = msg.get("content", "")[:300]  # Limit message size
                        content_parts.append(f"{role.upper()}: {text}")
                
                # Add query if present
                if "query" in session_data:
                    content_parts.append(f"USER QUERY: {session_data['query']}")

            # --- Schema 2: Graph (nodes, graph.original_query) ---
            if "graph" in session_data or "nodes" in session_data:
                graph = session_data.get("graph", {})
                if "original_query" in graph:
                    content_parts.append(f"USER QUERY: {graph['original_query']}")
                
                nodes = session_data.get("nodes", [])
                # Sort nodes by some criteria if needed, but list order is usually execution order
                for node in nodes[-15:]: # Look at last 15 nodes
                    agent = node.get("agent", "Unknown")
                    desc = node.get("description", "")
                    prompt = node.get("agent_prompt", "")
                    
                    if desc:
                        content_parts.append(f"STEP ({agent}): {desc}")
                    if prompt:
                        content_parts.append(f"CONTEXT: {prompt[:500]}") # Truncate long prompts
                    
                    # Check for direct outputs if they are strings (rare in graph, usually dicts)
                    output = node.get("output")
                    if isinstance(output, str):
                        content_parts.append(f"OUTPUT: {output[:300]}")

            if not content_parts:
                print(f"❌ No content in {session_path.name}")
                return {}
            
            content = "\n".join(content_parts)[:4000]  # Limit total size
            
            print(f"Scanning {session_path.name} ({len(content)} chars)...")
            
            prompt = SESSION_EXTRACTION_PROMPT.format(content=content)
            
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You extract user preferences from conversations. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},
                    "format": "json"
                },
                timeout=get_timeout()
            )
            response.raise_for_status()
            result = response.json()
            raw_content = result.get("message", {}).get("content", "{}")
            
            print(f"LLM Response for {session_path.name}: {raw_content[:200].replace(chr(10), ' ')}")

            # Clean up common JSON issues
            raw_content = raw_content.strip()
            if not raw_content.startswith("{"):
                start = raw_content.find("{")
                end = raw_content.rfind("}") + 1
                if start >= 0 and end > start:
                    raw_content = raw_content[start:end]
                else:
                    return {}
            
            preferences = json.loads(raw_content)
            if preferences:
                print(f"✅ Found preferences in {session_path.name}: {preferences}")
            else:
                print(f"ℹ️  No preferences in {session_path.name}")
            
            return preferences if isinstance(preferences, dict) else {}
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error for {session_path.name}: {str(e)[:50]}")
            return {}
        except Exception as e:
            print(f"⚠️ Failed to extract from {session_path.name}: {str(e)[:50]}")
            return {}
    
    def scan_all(self, max_sessions: int = 50, force: bool = False) -> int:
        """
        Scan session summaries and add preferences to staging.
        
        Args:
            max_sessions: Maximum number of sessions to scan
            force: If True, rescan all files regardless of tracker state
        
        Returns:
            Number of sessions that yielded preferences
        """
        tracker = get_scan_tracker()
        all_files = self.get_session_files(max_sessions * 2)  # Get more to filter
        
        if force:
            files = all_files[:max_sessions]
            print(f"Force scanning {len(files)} sessions...")
        else:
            # Filter to only unscanned/modified files
            files = tracker.get_unscanned_files("sessions", all_files)
            files = files[:max_sessions]
        
        if not files:
            print("💬 All sessions already scanned. Use force=True to rescan.")
            return 0
        
        print(f"💬 Scanning {len(files)} session summaries...")
        
        extracted_count = 0
        
        for session_path in files:
            preferences = self.extract_from_session(session_path)
            
            # Mark as scanned
            tracker.mark_scanned("sessions", session_path)
            
            if preferences:
                self.staging.add(
                    preferences,
                    source=f"session/{session_path.stem}"
                )
                extracted_count += 1
                
        # Save tracker state
        tracker.save()
        
        print(f"💬 Session scan complete: {extracted_count} sessions yielded preferences")
        return extracted_count


async def scan_sessions(max_sessions: int = 50, force: bool = False) -> int:
    """Run session scanner."""
    scanner = SessionScanner()
    return scanner.scan_all(max_sessions, force=force)

if __name__ == "__main__":
    print("Running session scanner debugging...")
    scanner = SessionScanner()
    # Force scan top 5 files to debug
    scanner.scan_all(max_sessions=5, force=True)


