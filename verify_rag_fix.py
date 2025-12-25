import sys
import os
from pathlib import Path

# Add current dir to path to import server_rag
sys.path.append(str(Path(__file__).parent / "mcp_servers"))
from server_rag import process_documents

print("🚀 Verifying Safe Embedding Fix...")
try:
    # Target the problematic file relative to 'data/'
    target = "deekseek_moe_moh_v2_continue_with_hicra.py"
    print(f"📦 Processing: {target}")
    process_documents(target_path=target)
    print("✅ Success! Safe Embedding handled the large file without 500 Errors.")
except Exception as e:
    print(f"❌ Failed: {e}")
