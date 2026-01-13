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
                        # Normalize: remove trailing slash and leading slash
                        pattern = line.rstrip('/').lstrip('/')
                        if pattern:
                            self.ignore_patterns.append(pattern)

    def is_ignored(self, path: str) -> bool:
        """Smarter ignore logic: check components of the path against patterns."""
        rel_path = os.path.relpath(path, self.root_path)
        if rel_path == ".":
            return False
            
        parts = rel_path.split(os.sep)
        for part in parts:
            if part in self.ignore_patterns:
                # print(f"  [Ignore] Exact match: {part} in {rel_path}")
                return True
            
            # Simple wildcard matching
            for pattern in self.ignore_patterns:
                if pattern == '*': continue # Never ignore everything via literal *
                
                # Handle *.ext
                if pattern.startswith('*') and len(pattern) > 1:
                    suffix = pattern[1:]
                    if part.endswith(suffix):
                        # print(f"  [Ignore] Suffix match: {pattern} for {part} in {rel_path}")
                        return True
                # Handle dir/*
                if pattern.endswith('*') and len(pattern) > 1:
                    prefix = pattern[:-1]
                    if part.startswith(prefix):
                        # print(f"  [Ignore] Prefix match: {pattern} for {part} in {rel_path}")
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
        """Extract skeletons from all supported code files."""
        results = {}
        
        # Supported code file extensions
        code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
            '.java', '.kt', '.scala', '.go', '.rs', '.rb', '.php',
            '.c', '.cpp', '.h', '.hpp', '.cs', '.swift', '.m',
            '.md', '.json', '.yaml', '.yml', '.toml'
        }
        
        print(f"  📂 Scanning: {self.root_path}")
        print(f"  🔍 Looking for extensions: {code_extensions}")
        
        for root, dirs, files in os.walk(self.root_path):
            # Skip ignored dirs
            dirs[:] = [d for d in dirs if not self.is_ignored(os.path.join(root, d))]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in code_extensions:
                    full_path = os.path.join(root, file)
                    if not self.is_ignored(full_path):
                        rel_path = os.path.relpath(full_path, self.root_path)
                        print(f"    ✓ Found: {rel_path}")
                        # For Python, use AST skeleton; for others, read content directly
                        if ext == '.py':
                            results[rel_path] = self.extract_file_skeleton(full_path)
                        else:
                            results[rel_path] = self._read_file_content(full_path)
        
        print(f"  📊 Total files extracted: {len(results)}")
        return results
    
    def _read_file_content(self, file_path: str, max_lines: int = 500) -> str:
        """Read file content, truncating if too large."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                if len(lines) > max_lines:
                    content = ''.join(lines[:max_lines])
                    content += f"\n\n... (truncated, {len(lines) - max_lines} more lines)"
                else:
                    content = ''.join(lines)
                return content
        except Exception as e:
            return f"# ERROR reading file: {e}"

    def scan_project(self) -> Dict[str, Any]:
        """Scan project for file stats."""
        file_stats = []
        summary = {"total_files": 0, "total_size": 0, "total_lines": 0}
        
        # File type categorization
        code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
            '.java', '.kt', '.scala', '.go', '.rs', '.rb', '.php',
            '.c', '.cpp', '.h', '.hpp', '.cs', '.swift', '.m',
            '.sh', '.bash', '.zsh', '.sql'
        }
        config_extensions = {'.json', '.yaml', '.yml', '.toml', '.xml', '.env', '.ini', '.cfg'}
        doc_extensions = {'.md', '.txt', '.rst', '.html', '.css', '.scss'}
        asset_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.mp3', '.mp4', '.wav'}
        binary_extensions = {'.pdf', '.zip', '.tar', '.gz', '.pyc', '.pkl', '.bin', '.exe', '.dll', '.so', '.dylib', '.woff', '.woff2', '.ttf', '.eot'}
        
        for root, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if not self.is_ignored(os.path.join(root, d))]
            
            for file in files:
                full_path = os.path.join(root, file)
                if self.is_ignored(full_path):
                    continue
                    
                rel_path = os.path.relpath(full_path, self.root_path)
                try:
                    size = os.path.getsize(full_path)
                    lines = 0
                    extension = os.path.splitext(file)[1].lower()
                    
                    # Determine file type
                    if extension in binary_extensions:
                        file_type = "binary"
                    elif extension in asset_extensions:
                        file_type = "asset"
                    elif extension in code_extensions:
                        file_type = "code"
                    elif extension in config_extensions:
                        file_type = "code"  # Include configs as analyzable
                    elif extension in doc_extensions:
                        file_type = "code"  # Include docs as analyzable
                    else:
                        # Try to read as text
                        file_type = "code"
                    
                    # Count lines for non-binary files
                    if file_type != "binary" and file_type != "asset":
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                lines = sum(1 for _ in f)
                        except UnicodeDecodeError:
                            file_type = "binary"

                    stat = {
                        "path": rel_path,
                        "size": size,
                        "lines": lines,
                        "type": file_type,
                        "extension": extension
                    }
                    file_stats.append(stat)
                    
                    summary["total_files"] += 1
                    summary["total_size"] += size
                    if file_type == "code":
                        summary["total_lines"] += lines
                        
                except Exception as e:
                    print(f"Error scanning {rel_path}: {e}")
                    
        return {"files": file_stats, "summary": summary}

if __name__ == "__main__":
    # Test on current dir
    extractor = CodeSkeletonExtractor(os.getcwd())
    skeletons = extractor.extract_all()
    for path, skel in list(skeletons.items())[:3]:
        print(f"--- {path} ---")
        print(skel)
        print("\n")
