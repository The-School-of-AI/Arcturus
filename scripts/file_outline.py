import ast
import os
import sys
import re

def get_python_outline(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        
        outline = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                outline.append(f"CLASS: {node.name} (Line {node.lineno}-{node.end_lineno})")
            elif isinstance(node, ast.FunctionDef):
                # Check if it's a method
                parent = "MODULE"
                outline.append(f"FUNC: {node.name} (Line {node.lineno}-{node.end_lineno})")
        return "\n".join(outline)
    except Exception as e:
        return f"Error parsing Python: {e}"

def get_generic_outline(file_path):
    # Fallback regex for JS/TS/Go etc.
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        outline = []
        # Look for typical class/function patterns
        for i, line in enumerate(lines):
            # Regex for common function/class patterns
            class_match = re.search(r'(class|interface|type)\s+([A-Za-z0-9_]+)', line)
            func_match = re.search(r'(function|const|let|var)\s+([A-Za-z0-9_]+)\s*(=|\()|([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{', line)
            
            if class_match:
                outline.append(f"STRUCT: {class_match.group(2)} (Line {i+1})")
            elif func_match:
                name = func_match.group(2) or func_match.group(4)
                if name and name not in ['if', 'for', 'while', 'switch', 'catch']:
                    outline.append(f"ITEM: {name} (Line {i+1})")
        return "\n".join(outline)
    except Exception as e:
        return f"Error reading file: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python file_outline.py <file_path>")
        sys.exit(1)
    
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Error: File not found: {path}")
        sys.exit(1)
        
    if path.endswith(".py"):
        print(get_python_outline(path))
    else:
        print(get_generic_outline(path))
