import os
import ast
from typing import Dict, List, Any, Optional

class CodeSkeletonExtractor:
    """
    Extracts structural information from Python codebases.
    Leaves class and function signatures but removes method bodies to save tokens.
    """
    def __init__(self, root_path: str, ignore_patterns: Optional[List[str]] = None):
        self.root_path = root_path
        self.ignore_patterns = ignore_patterns or ['.git', '__pycache__', 'node_modules', '.venv', 'venv']
        # Load .gitignore if exists
        self.load_gitignore()

    def load_gitignore(self):
        gitignore_path = os.path.join(self.root_path, '.gitignore')
        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.ignore_patterns.append(line)

    def is_ignored(self, path: str) -> bool:
        for pattern in self.ignore_patterns:
            if pattern in path:
                return True
        return False

    def extract_file_skeleton(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return f"# ERROR: Syntax Error in {file_path}"

        skeleton = []
        
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                skeleton.append(self._process_function(node))
            elif isinstance(node, ast.ClassDef):
                skeleton.append(self._process_class(node))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                skeleton.append(ast.unparse(node))
        
        return "\n".join(skeleton)

    def _process_function(self, node: ast.AST, indent: int = 0) -> str:
        # Get signature only
        prefix = "    " * indent
        if isinstance(node, ast.AsyncFunctionDef):
            def_type = "async def"
        else:
            def_type = "def"
            
        args = ast.unparse(node.args)
        returns = f" -> {ast.unparse(node.returns)}" if getattr(node, 'returns', None) else ""
        
        sig = f"{prefix}{def_type} {node.name}({args}){returns}:"
        
        # Get docstring if exists
        docstring = ast.get_docstring(node)
        if docstring:
            # Keep only the first paragraph of docstring
            summary = docstring.split('\n\n')[0].strip()
            body = f'\n{prefix}    """{summary}"""'
        else:
            body = f"\n{prefix}    ..."
            
        return sig + body

    def _process_class(self, node: ast.ClassDef) -> str:
        bases = f"({', '.join(ast.unparse(b) for b in node.bases)})" if node.bases else ""
        sig = f"class {node.name}{bases}:"
        
        docstring = ast.get_docstring(node)
        body_parts = []
        if docstring:
            summary = docstring.split('\n\n')[0].strip()
            body_parts.append(f'    """{summary}"""')
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body_parts.append(self._process_function(item, indent=1))
            elif isinstance(item, ast.ClassDef):
                body_parts.append(self._process_class(item)) # Note: Simplified recursive class
        
        if not body_parts:
            body_parts.append("    ...")
            
        return sig + "\n" + "\n".join(body_parts)

    def extract_all(self) -> Dict[str, str]:
        results = {}
        for root, dirs, files in os.walk(self.root_path):
            # Skip ignored dirs
            dirs[:] = [d for d in dirs if not self.is_ignored(os.path.join(root, d))]
            
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    if not self.is_ignored(full_path):
                        rel_path = os.path.relpath(full_path, self.root_path)
                        results[rel_path] = self.extract_file_skeleton(full_path)
        return results

if __name__ == "__main__":
    # Test on current dir
    extractor = CodeSkeletonExtractor(os.getcwd())
    skeletons = extractor.extract_all()
    for path, skel in list(skeletons.items())[:3]:
        print(f"--- {path} ---")
        print(skel)
        print("\n")
