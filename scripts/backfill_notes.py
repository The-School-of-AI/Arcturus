import json
import os
from pathlib import Path
import re

def sanitize_filename(title):
    # Remove invalid characters and limit length
    # Updated to remove #, *, etc more aggressively
    title = re.sub(r'[\\/*?:"<>|#]', "", title)
    title = title.replace("\n", " ").strip()
    return title[:60].strip()

def extract_title(content):
    # Try to find the first header
    match = re.search(r'^#+\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # Fallback to first non-empty line
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    if lines:
        return lines[0]
    return "Untitled Report"

def backfill_notes():
    project_root = Path(__file__).parent.parent
    summaries_dir = project_root / "memory" / "session_summaries_index"
    notes_dir = project_root / "data" / "Notes" / "Arcturus"
    
    # Clean up old notes
    if notes_dir.exists():
        print(f"Cleaning data/Notes/Arcturus...")
        for f in notes_dir.glob("*.md"):
            f.unlink()
    
    # Create notes directory if it doesn't exist
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    count = 0
    total_files = 0
    
    if not summaries_dir.exists():
        print(f"Summaries directory not found: {summaries_dir}")
        return

    print(f"Scanning {summaries_dir}...")
    
    for path in summaries_dir.rglob("session_*.json"):
        total_files += 1
        try:
            data = json.loads(path.read_text())
            file_has_report = False
            
            # Helper to check a node
            def check_node(node_data):
                nonlocal count, file_has_report
                # Check for FormatterAgent specific output
                output = node_data.get("output", {})
                if not output:
                    return

                markdown = output.get("markdown_report")
                # Also check for "formatted_report_..." keys 
                if not markdown:
                     for k, v in output.items():
                         if k.startswith("formatted_report") and isinstance(v, str):
                             markdown = v
                             break
                
                if markdown and len(markdown) > 100: 
                    title = extract_title(markdown)
                    filename = sanitize_filename(title) + ".md"
                    
                    target_path = notes_dir / filename
                    
                    # Prevent duplicate writes if multiple nodes have same content (rare)
                    if target_path.exists():
                        pass 

                    with open(target_path, 'w', encoding='utf-8') as f:
                        f.write(markdown)
                    
                    print(f"✅ Saved: {filename} (from {path.name})")
                    count += 1
                    file_has_report = True
            
            # Graph structure check
            nodes = data.get("nodes", [])
            if not nodes and "graph" in data and "nodes" in data["graph"]:
                 nodes = data["graph"]["nodes"]
            
            if nodes:
                for node in nodes:
                    check_node(node)
                    
            if not file_has_report:
                # Debug why
                # Check if it was a valid run but no formatter?
                print(f"⚠️ Skipped {path.name}: No FormatterAgent report found.")

        except Exception as e:
            print(f"❌ Error processing {path.name}: {e}")
            
    print(f"Backfill complete. Scanned {total_files} files. Saved {count} notes.")

if __name__ == "__main__":
    backfill_notes()
