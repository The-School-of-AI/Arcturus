from pathlib import Path
import hashlib
import shutil
import os

source_dir = Path("/Users/rohanshravan/TSAI/Arcturus/memory/session_summaries_index")
target_dir = Path("/Users/rohanshravan/TSAI/Arcturus/data/conversation_history")

def get_file_hash(path: Path) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def sync():
    if not source_dir.exists():
        print("Source not found")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for src_path in source_dir.rglob("*.json"):
        if not src_path.is_file():
            continue
        
        rel_path = src_path.relative_to(source_dir)
        dest_path = target_dir / rel_path
        
        should_copy = False
        if not dest_path.exists():
            should_copy = True
        else:
            if get_file_hash(src_path) != get_file_hash(dest_path):
                should_copy = True
        
        if should_copy:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            print(f"Syncing: {rel_path}")
            count += 1
    
    print(f"Synced {count} files.")

if __name__ == "__main__":
    sync()
