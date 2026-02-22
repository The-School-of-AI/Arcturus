import os
import json
from pathlib import Path
from typing import List
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("internal")

def _is_text_file(filepath: str) -> bool:
    """Basic check if a file is likely text based on extension."""
    text_extensions = {".py", ".md", ".txt", ".json", ".csv", ".yaml", ".yml", ".html", ".css", ".js", ".ts", ".tsx"}
    return any(filepath.endswith(ext) for ext in text_extensions)

@mcp.tool()
async def search_workspace_files(query: str, directory: str = ".") -> str:
    """
    Search the local workspace for files containing the given text query.
    Returns a list of matching file paths and the text snippets where the match was found.
    
    HOW IT WORKS:
    1. Recursively walks through all directories starting from the given base path.
    2. Skips non-text files and compiled/hidden folders like .git or node_modules to ensure fast searching.
    3. Opens each text file and scans line-by-line for the user's search query (case-insensitive).
    4. When a match is found, it extracts the line along with the preceding and succeeding line for "context".
    5. Formats the results into a readable list for the AI agent to understand what the code/documents say.
    """
    results = []
    base_dir = Path(directory).resolve()
    
    if not base_dir.exists() or not base_dir.is_dir():
        return f"[Error] Invalid directory: {directory}"

    query_lower = query.lower()
    
    # We ignore standard ignored dirs
    ignore_dirs = {".git", "node_modules", "venv", "__pycache__", ".venv"}

    try:
        # Walk through the directory
        for root, dirs, files in os.walk(base_dir):
            # Mutate dirs in-place to avoid walking ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            
            for file in files:
                if not _is_text_file(file):
                    continue
                
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        
                    for i, line in enumerate(lines):
                        if query_lower in line.lower():
                            # Grab context lines (1 before, 1 after)
                            start = max(0, i - 1)
                            end = min(len(lines), i + 2)
                            snippet = "".join(lines[start:end]).strip()
                            rel_path = os.path.relpath(filepath, base_dir)
                            results.append(f"File: {rel_path} (Line {i+1})\nSnippet: {snippet}")
                            # Stop after first match in file to avoid spam, or allow max 3 per file
                            if len([r for r in results if r.startswith(f"File: {rel_path}")]) >= 3:
                                break
                                
                    if len(results) >= 20: # Cap at 20 total results to prevent massive payloads
                        break
                except Exception:
                    pass
                        
            if len(results) >= 20:
                break
                
        if not results:
            return f"No results found for '{query}' in {directory}"
            
        return "Workspace Search Results:\n\n" + "\n---\n".join(results)
        
    except Exception as e:
        return f"[Error] Workspace search failed: {str(e)}"

@mcp.tool()
async def search_past_conversations(query: str) -> str:
    """
    Search across episodic memory and previous conversations for the user's project context.
    Reads from the memory service data store.
    
    HOW IT WORKS:
    1. Locates the centralized 'user_memory.json' database used by Arcturus's memory system.
    2. Loads all historical memories and tags into memory.
    3. Scans through the text and metadata tags for matches against the search query.
    4. Returns a bulleted list of previous conversations or facts that match the query, allowing the agent to "remember".
    """
    memory_file = Path(__file__).parent.parent / "data" / "user_memory.json"
    
    if not memory_file.exists():
        return "[Memory] No past conversations or episodic memory found."
        
    try:
        with open(memory_file, "r", encoding="utf-8") as f:
            memories = json.load(f)
            
        query_lower = query.lower()
        results = []
        
        for mem in memories:
            content = mem.get("content", "").lower()
            tags = [t.lower() for t in mem.get("tags", [])]
            
            if query_lower in content or any(query_lower in t for t in tags):
                results.append(f"- {mem.get('content')} (Tags: {', '.join(mem.get('tags', []))})")
                
        if not results:
            return f"No past memories matched '{query}'."
            
        return "Memory/Conversation Results:\n" + "\n".join(results)
        
    except Exception as e:
        return f"[Error] Memory search failed: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
