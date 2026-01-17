import sys
import os
import ast

def replace_symbol_in_file(file_path, symbol_name, new_content_file):
    """
    Replaces a top-level function or class definition in a Python file.
    
    Args:
        file_path (str): Path to the python file to modify.
        symbol_name (str): Name of the class or function to replace.
        new_content_file (str): Path to a temporary file containing the new code.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        with open(new_content_file, 'r', encoding='utf-8') as f:
            new_code = f.read()

        tree = ast.parse(source)
        
        target_node = None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol_name:
                    target_node = node
                    break
        
        if not target_node:
            print(f"Error: Symbol '{symbol_name}' not found in {file_path}")
            sys.exit(1)

        # Calculate start and end byte offsets
        # ast.get_source_segment is available in Python 3.8+
        segment = ast.get_source_segment(source, target_node)
        if not segment:
             # Fallback if get_source_segment fails (rare but possible)
             lines = source.splitlines(keepends=True)
             start_line = target_node.lineno - 1
             end_line = target_node.end_lineno
             original_code = "".join(lines[start_line:end_line])
        else:
             original_code = segment

        # Perform replacement
        # We use string replacement on the exact segement found
        # This preserves surrounding whitespace better than rebuilding lines
        new_source = source.replace(original_code, new_code + '\n', 1)

        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_source)

        print(f"Successfully replaced symbol '{symbol_name}'")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 replace_symbol.py <file_path> <symbol_name> <new_content_file>")
        sys.exit(1)
    
    replace_symbol_in_file(sys.argv[1], sys.argv[2], sys.argv[3])
