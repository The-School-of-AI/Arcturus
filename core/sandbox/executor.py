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

from ops.tracing import sandbox_run_span
from opentelemetry.trace import Status, StatusCode

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

    def __init__(self, multi_mcp=None, session_id: str = "default", step_id: str = None, event_bus=None):
        self.multi_mcp = multi_mcp
        self.session_id = session_id
        self.step_id = step_id
        self.event_bus = event_bus
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
            with sandbox_run_span(self.session_id, code) as blocked_span:
                blocked_span.set_attribute("status", "blocked")
                blocked_span.set_attribute("error", f"Security violation: {violations[0]['description']}"[:500])
            return SandboxResult(
                "blocked", 
                error=f"Security violation: {violations[0]['description']}",
                execution_time=start_ts,
                total_time=round(time.perf_counter() - start_time, 3)
            )

        with sandbox_run_span(self.session_id, code) as span:
            try:
                tree = ast.parse(code)
                
                # 3. Analyze complexity
                func_count = sum(isinstance(node, ast.Call) for node in ast.walk(tree))
                if func_count > self.max_functions:
                    span.set_attribute("status", "error")
                    span.set_attribute("error", "Complexity limit exceeded")
                    return SandboxResult("error", error="Complexity limit exceeded", execution_time=start_ts)

                # 4. Prepare Environment
                tool_funcs = self._get_tool_proxies()
                safe_globals = self._build_globals(tool_funcs)
                local_vars = {}

                # 5. Transform AST
                tree = self._transform_ast(tree, set(tool_funcs))

                # Auto-return last expression/assignment if code doesn't explicitly return
                if tree.body:
                    last_stmt = tree.body[-1]
                    has_return = any(isinstance(n, ast.Return) for n in ast.walk(tree))
                    if not has_return:
                        if isinstance(last_stmt, ast.Expr):
                            # Bare expression: `json.loads(...)` → `return json.loads(...)`
                            tree.body[-1] = ast.Return(value=last_stmt.value)
                        elif isinstance(last_stmt, ast.Assign) and len(last_stmt.targets) == 1:
                            # Assignment: `results = json.loads(...)` → keep assignment + `return results`
                            target = last_stmt.targets[0]
                            if isinstance(target, ast.Name):
                                tree.body.append(ast.Return(value=ast.Name(id=target.id, ctx=ast.Load())))

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
                # Use timeout_per_func (MCP tool calls can take 30+ seconds)
                timeout = max(30, func_count * self.timeout_per_func)

                # Custom logging hook to safely capture without recursion
                class RealTimeLogger(io.StringIO):
                    def write(self, s):
                        super().write(s)
                    def flush(self):
                        super().flush()

                rt_logger = RealTimeLogger()
                
                with contextlib.redirect_stdout(rt_logger), contextlib.redirect_stderr(rt_logger):
                    returned = await asyncio.wait_for(local_vars["__main"](), timeout=timeout)

                # 8. Extract & Serialize Results
                result_data = self._serialize(returned)
                self._save_state(result_data)
                
                final_logs = rt_logger.getvalue()
                total_time = round(time.perf_counter() - start_time, 3)
                span.set_attribute("status", "success")
                span.set_attribute("execution_time", str(total_time))
                result_preview = str(result_data)[:500]
                span.set_attribute("result_preview", result_preview)
                return SandboxResult(
                    "success",
                    result=result_data,
                    logs=final_logs,
                    execution_time=start_ts,
                    total_time=total_time
                )

            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                span.set_attribute("status", "error")
                span.set_attribute("error", f"{type(e).__name__}: {str(e)}"[:500])
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
        """
        Build a dict of callable proxies for every MCP tool.

        Each tool is registered under multiple aliases so the LLM's generated
        code resolves even when it uses a slightly wrong name variant:
          - Exact name:             fetch_search_urls  (canonical)
          - No-separator lowercase: fetchsearchurls    (common LLM hallucination)
          - No-underscore lower:    fetchsearchurls    (same, covered)
        """
        if not self.multi_mcp:
            return {}

        proxies = {}
        all_tool_names = []

        for tool in self.multi_mcp.get_all_tools():
            canonical = tool.name
            all_tool_names.append(canonical)

            async def proxy_fn(*args, t=canonical):
                # Emit source_progress for search tools so the frontend can track URL extraction
                progress_task = None
                if t == "search_web_with_text_content" and self.event_bus and self.step_id:
                    total_sources = 15  # Default for deep research
                    if args and len(args) >= 2:
                        try: total_sources = min(max(int(args[1]), 1), 20)
                        except: pass
                    async def _emit():
                        interval = max(0.6, 8.0 / total_sources)
                        for i in range(1, total_sources + 1):
                            await asyncio.sleep(interval)
                            await self.event_bus.publish("source_progress", "AgentLoop4", {
                                "step_id": self.step_id,
                                "current": i,
                                "total": total_sources,
                                "message": f"Reading source {i}/{total_sources}..."
                            })
                    progress_task = asyncio.create_task(_emit())
                result = await self.multi_mcp.function_wrapper(t, *args)
                if progress_task and not progress_task.done():
                    progress_task.cancel()
                # Emit tool_result for search tools
                if t == "search_web_with_text_content" and self.event_bus and self.step_id:
                    source_count = 0
                    urls = []
                    try:
                        result_str = str(result).strip() if result else ""
                        log_step("SandboxURL", f"📡 Raw result type={type(result).__name__} len={len(result_str)} starts={result_str[:80]!r}")
                        # Handle both raw JSON arrays and potential wrapper formats
                        parsed = None
                        if result_str.startswith("["):
                            try:
                                parsed = json.loads(result_str)
                            except json.JSONDecodeError:
                                # Could be "[error] ..." string from MCP
                                log_step("SandboxURL", f"⚠️ starts with [ but not valid JSON, trying bracket search")
                                bracket_pos = result_str.find("[{")
                                if bracket_pos >= 0:
                                    parsed = json.loads(result_str[bracket_pos:])
                        elif "{" in result_str and "url" in result_str:
                            start = result_str.find("[{")
                            if start >= 0:
                                parsed = json.loads(result_str[start:])
                        if isinstance(parsed, list):
                            source_count = len(parsed)
                            urls = [
                                {"url": item.get("url", ""), "title": item.get("title", "")}
                                for item in parsed if isinstance(item, dict) and item.get("url")
                            ]
                            log_step("SandboxURL", f"✅ step={self.step_id} parsed={source_count} items, extracted={len(urls)} urls")
                            if urls:
                                log_step("SandboxURL", f"   First URL: {urls[0].get('url','')[:80]}")
                        else:
                            log_step("SandboxURL", f"⚠️ step={self.step_id} parsed=None (not a list)")
                    except Exception as e:
                        log_step("SandboxURL", f"❌ Failed to parse URLs for step {self.step_id}: {e}")
                    log_step("SandboxURL", f"📤 Publishing tool_result step={self.step_id} source_count={source_count} urls_count={len(urls)}")
                    await self.event_bus.publish("tool_result", "AgentLoop4", {
                        "step_id": self.step_id,
                        "tool_name": t,
                        "source_count": source_count,
                        "urls": urls,
                        "message": f"Processed {source_count} sources from {t}" if source_count else f"Tool {t} completed"
                    })
                return result

            # Register under canonical name
            proxies[canonical] = proxy_fn

            # Register under stripped/merged lowercase alias
            # e.g. fetch_search_urls → fetchsearchurls
            alias = canonical.replace("_", "").replace("-", "").lower()
            if alias != canonical and alias not in proxies:
                proxies[alias] = proxy_fn

        # Store tool names so the safety-net can suggest them
        self._available_tool_names = all_tool_names
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
