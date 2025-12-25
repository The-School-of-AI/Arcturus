import os
from core.explorer_utils import CodeSkeletonExtractor

def test_traversal():
    print("--- Testing CodeSkeletonExtractor ---")
    # Create dummy structure
    os.makedirs("test_analyze/src/logic", exist_ok=True)
    with open("test_analyze/src/logic/main.py", "w") as f:
        f.write("def hello():\n    print('world')")
    
    print(f"Created test structure in {os.path.abspath('test_analyze')}")
    
    extractor = CodeSkeletonExtractor("test_analyze")
    print(f"Ignore patterns: {extractor.ignore_patterns}")
    
    skeletons = extractor.extract_all()
    print(f"Found files: {list(skeletons.keys())}")
    
    if not skeletons:
        print("FAILED: No files found!")
    else:
        print("SUCCESS: Files found.")

    # Cleanup
    import shutil
    shutil.rmtree("test_analyze")

if __name__ == "__main__":
    test_traversal()
