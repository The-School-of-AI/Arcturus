"""
Notes Scanner - Extracts preferences from user's Notes folder.

Scans markdown files in data/Notes/ for personal preferences and
adds them to the staging queue for normalization.
"""

import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings_loader import get_model, get_ollama_url, get_timeout
from remme.staging import get_staging_store
from remme.sources.scan_tracker import get_scan_tracker


NOTES_EXTRACTION_PROMPT = """Extract user preferences from this note.

Look for:
- Food/dietary preferences
- Work/professional context  
- Tech preferences (languages, frameworks, tools)
- Hobbies, interests
- Location, personal details

NOTE:
{content}

Return a JSON object with preferences found. Example: {{"role": "teacher", "location": "India"}}
Return {{}} if no personal preferences found.
JSON only, no explanation."""


class NotesScanner:
    """
    Scans Notes folder for preference extraction.
    """
    
    def __init__(self, notes_dir: str = "data/Notes"):
        self.notes_dir = Path(__file__).parent.parent.parent / notes_dir
        self.model = get_model("memory_extraction")
        self.api_url = get_ollama_url("chat")
        self.staging = get_staging_store()
    
    def get_note_files(self, max_files: int = 50) -> List[Path]:
        """Get markdown files from notes directory."""
        if not self.notes_dir.exists():
            print(f"⚠️ Notes directory not found: {self.notes_dir}")
            return []
        
        files = []
        for f in self.notes_dir.rglob("*.md"):
            # Skip very large files
            if f.stat().st_size < 50000:  # 50KB limit
                files.append(f)
        
        return files[:max_files]
    
    def extract_from_note(self, note_path: Path) -> Dict:
        """Extract preferences from a single note file."""
        try:
            content = note_path.read_text()[:3000]  # Limit content size
            
            prompt = NOTES_EXTRACTION_PROMPT.format(content=content)
            
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You extract user preferences from text. Return only valid JSON."},
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
            
            # Clean up common JSON issues
            raw_content = raw_content.strip()
            if not raw_content.startswith("{"):
                # Try to find JSON in the response
                start = raw_content.find("{")
                end = raw_content.rfind("}") + 1
                if start >= 0 and end > start:
                    raw_content = raw_content[start:end]
                else:
                    return {}
            
            preferences = json.loads(raw_content)
            return preferences if isinstance(preferences, dict) else {}
            
        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error for {note_path.name}: {str(e)[:50]}")
            return {}
        except Exception as e:
            print(f"⚠️ Failed to extract from {note_path.name}: {str(e)[:50]}")
            return {}
    
    def scan_all(self) -> int:
        """
        Scan all notes and add preferences to staging.
        
        Returns:
            Number of notes that yielded preferences
        """
        tracker = get_scan_tracker()
        all_files = self.get_note_files()
        
        # Filter to only unscanned/modified files
        files = tracker.get_unscanned_files("notes", all_files)
        
        print(f"📝 Scanning {len(files)} notes ({len(all_files) - len(files)} already scanned)...")
        
        if not files:
            print("📝 All notes already scanned. Use force=True to rescan.")
            return 0
        
        extracted_count = 0
        
        for note_path in files:
            preferences = self.extract_from_note(note_path)
            
            # Mark as scanned regardless of whether we found preferences
            tracker.mark_scanned("notes", note_path)
            
            if preferences:
                self.staging.add(
                    preferences,
                    source=f"notes/{note_path.name}"
                )
                extracted_count += 1
                print(f"  ✅ {note_path.name}: {len(preferences)} preferences")
        
        # Save tracker state
        tracker.save()
        
        print(f"📝 Notes scan complete: {extracted_count} files yielded preferences")
        return extracted_count


async def scan_notes() -> int:
    """Run notes scanner."""
    scanner = NotesScanner()
    return scanner.scan_all()
