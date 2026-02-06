import sys
import os

print(f"Executable: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print("Path:")
for p in sys.path:
    print(f"  - {p}")

try:
    import mcp
    print(f"✅ 'mcp' imported from: {mcp.__file__}")
except ImportError as e:
    print(f"❌ 'mcp' failed to import: {e}")
    # Try finding it in site-packages manually
    import site
    print("Site packages:")
    for s in site.getsitepackages():
        print(f"  - {s}")
