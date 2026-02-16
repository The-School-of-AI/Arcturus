
import ast
import inspect
from typing import Any, Dict, List, Optional, get_type_hints

class MCPInspector:
    """
    Inspector that uses AST to extract MCP Tool definitions from Python files.
    """
    
    @staticmethod
    def inspect_file(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse a Python file and extract tool definitions for all top-level functions.
        Returns a list of MCP Tool schemas.
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
            
        return MCPInspector.inspect_source(source)

    @staticmethod
    def inspect_source(source: str) -> List[Dict[str, Any]]:
        """
        Parse source code string and extract tool definitions.
        """
        tools = []
        tree = ast.parse(source)
        
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                # Skip private functions
                if node.name.startswith('_'):
                    continue
                    
                tool_def = MCPInspector._node_to_tool(node)
                if tool_def:
                    tools.append(tool_def)
                    
        return tools

    @staticmethod
    def _node_to_tool(node: ast.FunctionDef) -> Optional[Dict[str, Any]]:
        """
        Convert an AST FunctionDef node to an MCP Tool schema.
        """
        docstring = ast.get_docstring(node)
        if not docstring:
            return None # Skip undocumented functions (or warn?)
            
        description = docstring.strip().split('\n\n')[0] # First paragraph as description
        
        # Extract arguments and types from AST
        properties = {}
        required = []
        
        args = node.args
        
        def parse_annotation(annotation) -> str:
            if annotation is None:
                return "string"
            
            if isinstance(annotation, ast.Name):
                id_ = annotation.id
                if id_ == 'str': return 'string'
                if id_ == 'int': return 'integer'
                if id_ == 'float': return 'number'
                if id_ == 'bool': return 'boolean'
                if id_ == 'dict': return 'object'
                if id_ == 'list': return 'array'
                return "string"
                
            if isinstance(annotation, ast.Subscript):
                # Handle Optional[T] or List[T]
                value = annotation.value
                if isinstance(value, ast.Name):
                    if value.id == 'Optional':
                        # Unwrap Optional[T] -> T
                        return parse_annotation(annotation.slice)
                    if value.id == 'List':
                        return 'array'
                    if value.id == 'Dict':
                        return 'object'
                        
            return "string" # Fallback
            
        # Helper to identify defaults
        # args.defaults corresponds to the LAST n arguments
        num_defaults = len(args.defaults)
        args_with_defaults = [a.arg for a in args.args[-num_defaults:]] if num_defaults > 0 else []

        for arg in args.args:
            name = arg.arg
            if name == 'self': continue
            
            json_type = parse_annotation(arg.annotation)
            
            # Simple docstring param extraction (naive)
            # TODO: Use docstring_parser library if available, else regex
            arg_desc = f"Argument {name}"
            
            properties[name] = {
                "type": json_type,
                "description": arg_desc
            }
            
            if name not in args_with_defaults:
                required.append(name)
                
        return {
            "name": node.name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
