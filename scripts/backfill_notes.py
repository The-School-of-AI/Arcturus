import json
import os
from pathlib import Path
import re

def sanitize_filename(title):
    # Remove invalid characters and limit length
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title[:50].strip()

def extract_title(content):
    # Try to find the first header
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # Fallback to first line
    first_line = content.strip().split('\n')[0]
    return first_line.strip()

def backfill_notes():
    project_root = Path(__file__).parent.parent
    summaries_dir = project_root / "memory" / "session_summaries_index"
    notes_dir = project_root / "data" / "Notes" / "Arcturus"
    
    # Create notes directory if it doesn't exist
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    count = 0
    
    if not summaries_dir.exists():
        print(f"Summaries directory not found: {summaries_dir}")
        return

    print(f"Scanning {summaries_dir}...")
    
    for path in summaries_dir.rglob("session_*.json"):
        try:
            data = json.loads(path.read_text())
            
            # Helper to check a node
            def check_node(node_data):
                nonlocal count
                # Check for FormatterAgent specific output
                # We look for fallback_markdown which is the standard report key
                output = node_data.get("output", {})
                if not output:
                    return

                markdown = output.get("fallback_markdown")
                # Also check for "formatted_report_..." keys which might contain the text
                if not markdown:
                     for k, v in output.items():
                         if k.startswith("formatted_report") and isinstance(v, str):
                             markdown = v
                             break
                
                if markdown and len(markdown) > 100: # Filter out trivial outputs
                    # Generate filename
                    title = extract_title(markdown)
                    filename = sanitize_filename(title) + ".md"
                    
                    target_path = notes_dir / filename
                    
                    # Avoid overwriting with older versions if file exists? 
                    # For now, let's just write headers to indicate source
                    
                    header = f"<!-- Source: {path.name} -->\n"
                    if target_path.exists():
                        # If existing file is from same source, skip or overwrite. 
                        # If different source, maybe append ID
                        pass
                    
                    with open(target_path, 'w', encoding='utf-8') as f:
                        f.write(markdown)
                    
                    print(f"Saved: {filename} (from {path.name})")
                    count += 1
            
            # Graph structure check
            if "nodes" in data:
                # Flat list format
                for node in data["nodes"]:
                    check_node(node)
            else:
                # NetworkX adjacency format sometimes puts nodes in 'nodes' list too, 
                # but if it's strictly link-node, we traverse.
                # Actually our JSON usually has "nodes": [{id:..., ...}] even in networkx format
                # Let's check if 'graph' wrapper exists
                pass

        except Exception as e:
            print(f"Error processing {path}: {e}")
            
    print(f"Backfill complete. Saved {count} notes.")

if __name__ == "__main__":
    backfill_notes()
