
import os
from rich import print
try:
    from mem0 import Memory
except ImportError:
    Memory = None
    print("[yellow]⚠️ mem0 not installed. Memory features will be disabled.[/yellow]")

class MemoryStore:
    def __init__(self, user_id="default_user", local_path=None):
        self.user_id = user_id
        if Memory:
            # Local mode by default if no config provided, handles ~/.mem0 internally or custom path
            config = {}
            if local_path:
                config["db_path"] = local_path
            
            self.m = Memory(config=config) if config else Memory()
            print(f"[green] Mem0 initialized for user: {user_id}[/green]")
        else:
            self.m = None

    def add(self, text: str, user_id: str = None):
        """Add a memory/fact"""
        if not self.m: return
        target_user = user_id or self.user_id
        # mem0 .add takes messages or text.
        self.m.add(text, user_id=target_user)

    def search(self, query: str, user_id: str = None, limit: int = 5) -> list:
        """Search memories"""
        if self.m:
            target_user = user_id or self.user_id
            return self.m.search(query, user_id=target_user, limit=limit)
        
        # Fallback to local user_memory.json if mem0 is missing
        try:
            from pathlib import Path
            import json
            memory_file = Path("data/user_memory.json")
            if memory_file.exists():
                memories = json.loads(memory_file.read_text())
                query_terms = query.lower().split()
                results = []
                for mem in memories:
                    content = mem.get("content", "").lower()
                    if any(term in content for term in query_terms):
                        results.append({"memory": mem.get("content")})
                return results[:limit]
        except Exception:
            pass
        return []

    def get_all(self, user_id: str = None) -> list:
        """Get all memories"""
        if not self.m: return []
        target_user = user_id or self.user_id
        return self.m.get_all(user_id=target_user)
