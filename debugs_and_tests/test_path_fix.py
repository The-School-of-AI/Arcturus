import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.utils import get_log_folder

try:
    log_path = get_log_folder("test_session")
    print(f"Log Path: {log_path}")
    
    expected_part = "16_NetworkX/memory/session_logs"
    if expected_part in str(log_path):
        print("✅ SUCCESS: Path contains expected package structure")
    else:
        print(f"❌ FAILURE: Path {log_path} does not contain {expected_part}")

except Exception as e:
    print(f"❌ ERROR: {e}")
