import ast
import asyncio
import time
import builtins
import textwrap
import re
import os
import json
from datetime import datetime
from pathlib import Path
import traceback
from core.utils import log_json_block, log_step, log_error, log_json_block
import io
import contextlib
import sys
# from agent.agentSession import ExecutionSnapshot

ALLOWED_MODULES = {
    "math", "random", "re", "datetime", "time", "collections", "itertools",
    "statistics", "string", "functools", "operator", "json", "pprint", "copy",
    "typing", "uuid", "hashlib", "base64", "hmac", "struct", "decimal", "fractions"
}

SAFE_BUILTINS = [
    # Core types and structure
    "bool", "int", "float", "str", "list", "dict", "set", "tuple", "complex",
    
    # Iteration and collection helpers
    "range", "enumerate", "zip", "map", "filter", "reversed", "next",
    
    # Logic and math
    "abs", "round", "divmod", "pow", "sum", "min", "max", "all", "any",
    
    # String and character
    "ord", "chr", "len", "sorted",
    
    # Type inspection
    "isinstance", "issubclass", "type", "id",
    
    # Functional
    "callable", "hash", "format",
    
    # Import-related
    "__import__",

    # Output and utility
    "print", "locals", "globals", "repr",
    "Exception", "True", "False", "None", "open"
]

MAX_FUNCTIONS = 20
TIMEOUT_PER_FUNCTION = 50

class KeywordStripper(ast.NodeTransformer):
    """Rewrite all function calls to remove keyword args and keep only values as positional."""
    def visit_Call(self, node):
        self.generic_visit(node)
        if node.keywords:
            # Convert all keyword arguments into positional args (discard names)
            for kw in node.keywords:
                node.args.append(kw.value)
            node.keywords = []
        return node


# ───────────────────────────────────────────────────────────────
# AST TRANSFORMER: auto-await known async MCP tools
# ───────────────────────────────────────────────────────────────
class AwaitTransformer(ast.NodeTransformer):
    def __init__(self, async_funcs):
        self.async_funcs = async_funcs

    def visit_Call(self, node):
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id in self.async_funcs:
            return ast.Await(value=node)
        return node



def fix_unterminated_triple_quotes(code: str) -> str:
    import re
    triple_quotes = re.findall(r'''"""''', code)
    if len(triple_quotes) % 2 != 0:
        log_error("Fixing unterminated triple-quoted string...", symbol="⚠️ ")
        return code + '\n"""'
    return code


def build_safe_globals(mcp_funcs: dict, multi_mcp=None, session_id: str = None) -> dict:
    safe_globals = {
        "__builtins__": {
            k: getattr(builtins, k) for k in SAFE_BUILTINS
        },
        **mcp_funcs,
    }

    for module in ALLOWED_MODULES:
        safe_globals[module] = __import__(module)

    safe_globals["final_answer"] = lambda x: safe_globals.setdefault("result_holder", x)

    if session_id:
        safe_globals.update(load_session_vars(session_id))
        
    # Inject DATA_DIR so agents know where to look
    safe_globals["DATA_DIR"] = str(Path(__file__).parent.parent / "data")

    if multi_mcp:
        async def parallel(*tool_calls):
            coros = [multi_mcp.function_wrapper(tool_name, *args) for tool_name, *args in tool_calls]
            return await asyncio.gather(*coros)
        safe_globals["parallel"] = parallel

    # Allow both direct access (`urls`) and schema-style (`globals_schema.get("urls", "")`)
    safe_globals["globals_schema"] = {
        k: v for k, v in safe_globals.items() if k not in {"__builtins__", "final_answer", "parallel"}
    }

    return safe_globals


def save_session_vars(session_id: str, variables: dict):
    os.makedirs("action/sandbox_state", exist_ok=True)
    path = f"action/sandbox_state/{session_id}.json"

    # Load existing vars if any
    try:
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = {}

    # Merge
    merged = {**existing, **variables}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)


def load_session_vars(session_id: str) -> dict:
    try:
        with open(f"action/sandbox_state/{session_id}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def count_function_calls(code: str) -> int:
    tree = ast.parse(code)
    return sum(isinstance(node, ast.Call) for node in ast.walk(tree))


def make_tool_proxy(tool_name: str, mcp):
    async def _tool_fn(*args):
        return await mcp.function_wrapper(tool_name, *args)
    return _tool_fn

async def run_user_code(code: str, multi_mcp, session_id: str = "default_session") -> dict:
    start_time = time.perf_counter()
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def is_json_serializable(value):
        return isinstance(value, (str, int, float, bool, type(None), list, dict))

    try:
        func_count = count_function_calls(code)
        if func_count > MAX_FUNCTIONS:
            return {
                "status": "error",
                "error": f"Too many functions ({func_count} > {MAX_FUNCTIONS})",
                "execution_time": start_timestamp,
                "total_time": str(round(time.perf_counter() - start_time, 3))
            }

        tool_funcs = {
            tool.name: make_tool_proxy(tool.name, multi_mcp)
            for tool in multi_mcp.get_all_tools()
        }

        sandbox = build_safe_globals(tool_funcs, multi_mcp, session_id)
        local_vars = {}

        log_step(f"[CODE:]: {code}", symbol="🐍")

        cleaned_code = fix_unterminated_triple_quotes(textwrap.dedent(code.strip()))
        tree = ast.parse(cleaned_code)

        # ─── AST Transformations ─────────────────────────────────────
        tree = KeywordStripper().visit(tree)
        tree = AwaitTransformer(set(tool_funcs)).visit(tree)

        # Rewrite return <varname> → return {"varname": varname}
        new_body = []
        return_found = False
        for node in tree.body:
            if isinstance(node, ast.Return):
                return_found = True
                if isinstance(node.value, ast.Name):
                    varname = node.value.id
                    new_body.append(
                        ast.Return(
                            value=ast.Dict(
                                keys=[ast.Constant(value=varname)],
                                values=[ast.Name(id=varname, ctx=ast.Load())]
                            )
                        )
                    )
                else:
                    new_body.append(node)
            else:
                new_body.append(node)

        # If return is missing but 'result' exists, add `return result`
        has_result_var = any(
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "result" for t in node.targets)
            for node in new_body
        )
        result_vars = {
            node.targets[0].id
            for node in tree.body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        }

        if not return_found and "result" in result_vars:
            new_body.append(ast.Return(value=ast.Name(id="result", ctx=ast.Load())))


        ast.fix_missing_locations(tree)
        tree.body = new_body
        ast.fix_missing_locations(tree)

        # ─── Wrap as async def __main() ──────────────────────────────
        func_def = ast.AsyncFunctionDef(
            name="__main",
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=tree.body,
            decorator_list=[]
        )
        wrapper = ast.Module(body=[func_def], type_ignores=[])
        ast.fix_missing_locations(wrapper)
        

        compiled = compile(wrapper, filename="<user_code>", mode="exec")
        exec(compiled, sandbox, local_vars)

        # ─── Execute and collect result ──────────────────────────────
        timeout = max(3, func_count * TIMEOUT_PER_FUNCTION)
        
        # Capture stdout/stderr
        log_capture = io.StringIO()
        
        with contextlib.redirect_stdout(log_capture), contextlib.redirect_stderr(log_capture):
            returned = await asyncio.wait_for(local_vars["__main"](), timeout=timeout)

        result_value = {}
        

        def serialize_result(v):
            """Serialize a value to JSON-compatible format.
            
            CRITICAL: Handles MCP tool results that may return:
            - Raw JSON-serializable values
            - Objects with .content attribute (MCP responses)
            - String representations of Python lists/dicts
            
            The last case caused a bug where urls were stored as strings like "['url1', 'url2']"
            and then iterated character-by-character in the next iteration.
            """
            # Already JSON-compatible primitives
            if isinstance(v, (int, float, bool, type(None))):
                return v
            
            # Lists and dicts - recursively serialize contents
            if isinstance(v, list):
                return [serialize_result(item) for item in v]
            if isinstance(v, dict):
                return {k: serialize_result(val) for k, val in v.items()}
            
            # Strings - check if they're actually serialized lists/dicts
            if isinstance(v, str):
                stripped = v.strip()
                # Check if it looks like a Python/JSON list or dict
                if (stripped.startswith('[') and stripped.endswith(']')) or \
                   (stripped.startswith('{') and stripped.endswith('}')):
                    # Try JSON first
                    try:
                        parsed = json.loads(stripped)
                        return serialize_result(parsed)  # Recursively process
                    except (json.JSONDecodeError, TypeError):
                        pass
                    
                    # Try Python literal (handles single quotes, True/False/None)
                    try:
                        parsed = ast.literal_eval(stripped)
                        return serialize_result(parsed)  # Recursively process
                    except (ValueError, SyntaxError):
                        pass
                
                # It's just a regular string
                return v
            
            # MCP ActionResultOutput with success/content/error attributes
            if hasattr(v, "success") and hasattr(v, "content") and hasattr(v, "error"):
                if not v.success:
                    return f"Error executing tool: {v.error}"
                return serialize_result(v.content) if v.content else "Success"
            
            # MCP response with .content list (common pattern)
            if hasattr(v, "content") and isinstance(v.content, list):
                text_content = "\n".join(x.text for x in v.content if hasattr(x, "text"))
                
                # Try to parse as structured data
                stripped = text_content.strip()
                if (stripped.startswith('[') and stripped.endswith(']')) or \
                   (stripped.startswith('{') and stripped.endswith('}')):
                    # Try JSON first
                    try:
                        parsed = json.loads(stripped)
                        return serialize_result(parsed)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    
                    # Try Python literal
                    try:
                        parsed = ast.literal_eval(stripped)
                        return serialize_result(parsed)
                    except (ValueError, SyntaxError):
                        pass
                
                return text_content
            
            # Fallback: convert to string
            return str(v)

        if isinstance(returned, dict) and list(returned.keys()) == ["result"]:
            result_value = {"result": serialize_result(returned["result"])}
        if isinstance(returned, dict):
            result_value = {k: serialize_result(v) for k, v in returned.items()}
            
            # Check for MCP tool failures or error messages
            for v in result_value.values():
                if isinstance(v, str) and (
                    v.lower().startswith("error executing tool") or
                    v.lower().startswith("error:") or
                    "failed" in v.lower()
                ):
                    return {
                        "status": "error", 
                        "error": v,
                        "execution_time": start_timestamp,
                        "total_time": str(round(time.perf_counter() - start_time, 3))
                    }
            
            # Check if any MCP tool returned success=False
            for k, v in returned.items():
                if hasattr(v, "success") and not v.success:
                    error_msg = v.error if hasattr(v, "error") and v.error else f"Tool {k} failed"
                    return {
                        "status": "error",
                        "error": error_msg,
                        "execution_time": start_timestamp,
                        "total_time": str(round(time.perf_counter() - start_time, 3))
                    }

        else:
            result_value = {"result": serialize_result(returned)}

        # import pdb; pdb.set_trace()

        

        log_json_block("Executor result", result_value)

        save_session_vars(session_id, result_value)
        # import pdb; pdb.set_trace()

        return {
            "status": "success",
            "result": result_value,
            "raw": result_value,
            "logs": log_capture.getvalue(),
            "execution_time": start_timestamp,
            "total_time": str(round(time.perf_counter() - start_time, 3))
        }

    except asyncio.TimeoutError:
        return {
            "status": "error",
            "error": f"Execution timed out after {func_count * TIMEOUT_PER_FUNCTION} seconds",
            "execution_time": start_timestamp,
            "total_time": str(round(time.perf_counter() - start_time, 3))
        }
    except Exception as e:
        print("⚠️ Code execution error:\n", traceback.format_exc())
        return {
            "status": "error",
            "error": f"{type(e).__name__}: {str(e)}",
            "traceback": traceback.format_exc(),
            "execution_time": start_timestamp,
            "total_time": str(round(time.perf_counter() - start_time, 3))
        }
