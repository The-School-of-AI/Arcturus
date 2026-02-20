"""Root conftest for pytest configuration."""
import sys
import os
from pathlib import Path

# Ensure project root is in Python path for all tests
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
