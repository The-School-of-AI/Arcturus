import ast
import hashlib
from typing import Dict, List, Optional
from pydantic import BaseModel

class FunctionInfo(BaseModel):
    name: str
    args: List[str]
    docstring: Optional[str]
    body_hash: str
    start_line: int
    end_line: int
    is_async: bool
    decorators: List[str]

class FileAnalysis(BaseModel):
    functions: Dict[str, FunctionInfo]
    classes: Dict[str, Dict[str, FunctionInfo]]  # Class methods
    file_hash: str

def get_ast_hash(node: ast.AST) -> str:
    """
    Generate a stable hash for an AST node, ignoring semantic-irrelevant details
    like docstrings (if handled separately) or exact formatting.
    However, for now, we just dump the structure.
    """
    # ast.dump includes fields which might be sensitive to location if include_attributes=True
    # We want location-independent hash for body content.
    s = ast.dump(node, include_attributes=False)
    return hashlib.md5(s.encode('utf-8')).hexdigest()

class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.functions: Dict[str, FunctionInfo] = {}
        self.classes: Dict[str, Dict[str, FunctionInfo]] = {}
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._process_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._process_function(node, is_async=True)

    def _process_function(self, node, is_async=False):
        # Extract docstring
        docstring = ast.get_docstring(node)
        
        # Calculate hash of the body (excluding docstring if possible, but hard with ast.dump)
        # For simplicity, we hash the entire node structure (without line numbers)
        body_hash = get_ast_hash(node)

        # Decorators
        decorators = []
        for d in node.decorator_list:
            if isinstance(d, ast.Name):
                decorators.append(d.id)
            elif isinstance(d, ast.Call):
                # Simple case for @decorator(args)
                if hasattr(d.func, 'id'):
                    decorators.append(d.func.id)
        
        args = [a.arg for a in node.args.args]
        
        info = FunctionInfo(
            name=node.name,
            args=args,
            docstring=docstring,
            body_hash=body_hash,
            start_line=node.lineno,
            end_line=node.end_lineno if hasattr(node, "end_lineno") else node.lineno,
            is_async=is_async,
            decorators=decorators
        )

        if self.current_class:
            if self.current_class not in self.classes:
                self.classes[self.current_class] = {}
            self.classes[self.current_class][node.name] = info
        else:
            self.functions[node.name] = info
            
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

def analyze_file(file_path: str) -> Optional[FileAnalysis]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        tree = ast.parse(content)
        analyzer = CodeAnalyzer(content)
        analyzer.visit(tree)
        
        file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        return FileAnalysis(
            functions=analyzer.functions,
            classes=analyzer.classes,
            file_hash=file_hash
        )
    except Exception as e:
        print(f"Error analyzing file {file_path}: {e}")
        return None
