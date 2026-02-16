
import ast
import asyncio
import time
import builtins
import textwrap
import re
import os
import json
import io
import contextlib
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

# Core Logging Utility
from core.utils import log_step, log_error, log_json_block

class SandboxResult(dict):
    """Container for sandbox execution results."""
    def __init__(self, status: str, result: Any = None, logs: str = "", error: str = None, **kwargs):
        super().__init__(
            status=status,
            result=result,
            logs=logs,
            error=error,
            **kwargs
        )

class UniversalSandbox:
    """
    Standardized Sandbox for executing AI-generated code.
    Features AST transformation for MCP tool integration, safety checks, and session persistence.
    """
    
    ALLOWED_MODULES = {
        "math", "random", "re", "datetime", "time", "collections", "itertools",
        "statistics", "string", "functools", "operator", "json", "pprint", "copy",
        "typing", "uuid", "hashlib", "base64", "hmac", "struct", "decimal", "fractions"
    }

    SAFE_BUILTINS = [
        "bool", "int", "float", "str", "list", "dict", "set", "tuple", "complex",
        "range", "enumerate", "zip", "map", "filter", "reversed", "next",
        "abs", "round", "divmod", "pow", "sum", "min", "max", "all", "any",
        "ord", "chr", "len", "sorted", "isinstance", "issubclass", "type", "id",
        "callable", "hash", "format", "__import__", "print", "locals", "globals", "repr",
        "Exception", "True", "False", "None", "open"
    ]

    def __init__(self, multi_mcp=None, session_id: str = "default"):
        self.multi_mcp = multi_mcp
        self.session_id = session_id
        self.max_functions = 20
        self.timeout_per_func = 50
        self.state_dir = Path("action/sandbox_state")
        self.state_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, code: str) -> Dict[str, Any]:
        """Runs the provided Python code securely."""
        start_time = time.perf_counter()
        start_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Cleaning & Prep
        code = textwrap.dedent(code.strip())
        
        # 2. Safety Check
        is_safe, violations = self._check_safety(code)
        if not is_safe:
            return SandboxResult(
                "blocked", 
                error=f"Security violation: {violations[0]['description']}",
                execution_time=start_ts,
                total_time=round(time.perf_counter() - start_time, 3)
            )

        try:
            tree = ast.parse(code)
            
            # 3. Analyze complexity
            func_count = sum(isinstance(node, ast.Call) for node in ast.walk(tree))
            if func_count > self.max_functions:
                return SandboxResult("error", error="Complexity limit exceeded", execution_time=start_ts)

            # 4. Prepare Environment
            tool_funcs = self._get_tool_proxies()
            safe_globals = self._build_globals(tool_funcs)
            local_vars = {}

            # 5. Transform AST
            tree = self._transform_ast(tree, set(tool_funcs))
            
            # Auto-return last expression if it's meaningful
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                tree.body[-1] = ast.Return(value=tree.body[-1].value)
            
            # 6. Compile & Wrap
            func_def = ast.AsyncFunctionDef(
                name="__main",
                args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                body=tree.body,
                decorator_list=[]
            )
            module = ast.Module(body=[func_def], type_ignores=[])
            ast.fix_missing_locations(module)
            
            compiled = compile(module, filename="<sandbox>", mode="exec")
            exec(compiled, safe_globals, local_vars)

            # 7. Execute with Monitoring
            log_capture = io.StringIO()
            timeout = max(5, func_count * 2) 
            
            # Custom logging hook to safely capture without recursion
            class RealTimeLogger(io.StringIO):
                def write(self, s):
                    super().write(s)
                    # We avoid calling log_step here because log_step writes to stderr,
                    # which is currently redirected to this very logger, causing recursion.
                    # We'll log the full capture AFTER the execution block.
                def flush(self):
                    super().flush()

            rt_logger = RealTimeLogger()
            
            with contextlib.redirect_stdout(rt_logger), contextlib.redirect_stderr(rt_logger):
                returned = await asyncio.wait_for(local_vars["__main"](), timeout=timeout)

            # 8. Extract & Serialize Results
            result_data = self._serialize(returned)
            self._save_state(result_data)
            
            final_logs = rt_logger.getvalue()
            return SandboxResult(
                "success",
                result=result_data,
                logs=final_logs,
                execution_time=start_ts,
                total_time=round(time.perf_counter() - start_time, 3)
            )

        except Exception as e:
            return SandboxResult(
                "error",
                error=f"{type(e).__name__}: {str(e)}",
                traceback=traceback.format_exc(),
                execution_time=start_ts,
                total_time=round(time.perf_counter() - start_time, 3)
            )

    def _check_safety(self, code: str):
        # Basic check for now
        blocked = ["rm -rf", "shutil.rmtree", "os.remove", "os.system", "subprocess"]
        violations = []
        for p in blocked:
            if p in code:
                violations.append({"description": f"Blocked pattern found: {p}"})
        return len(violations) == 0, violations

    def _get_tool_proxies(self):
        if not self.multi_mcp: return {}
        proxies = {}
        for tool in self.multi_mcp.get_all_tools():
            async def proxy_fn(*args, t=tool.name):
                return await self.multi_mcp.function_wrapper(t, *args)
            proxies[tool.name] = proxy_fn
        return proxies

    def _build_globals(self, mcp_funcs: dict):
        g = {
            "__builtins__": {k: getattr(builtins, k) for k in self.SAFE_BUILTINS},
            **mcp_funcs
        }
        for mod in self.ALLOWED_MODULES:
            try: g[mod] = __import__(mod)
            except: pass
        return g

    def _transform_ast(self, tree, async_funcs):
        # Auto-await transformer
        class Transformer(ast.NodeTransformer):
            def visit_Call(self, node):
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) and node.func.id in async_funcs:
                    return ast.Await(value=node)
                return node
        return Transformer().visit(tree)

    def _serialize(self, v):
        if isinstance(v, (int, float, bool, type(None), str, list, dict)): return v
        if hasattr(v, "content") and isinstance(v.content, list):
            return "\n".join(x.text for x in v.content if hasattr(x, "text"))
        return str(v)

    def _save_state(self, data):
        if not self.session_id: return
        path = self.state_dir / f"{self.session_id}.json"
        try:
            existing = json.loads(path.read_text()) if path.exists() else {}
            existing.update(data if isinstance(data, dict) else {"result": data})
            path.write_text(json.dumps(existing, indent=2))
        except: pass
