"""
WATCHTOWER: Span context managers for common trace patterns.
Import these instead of inlining tracer/span logic in business code.
"""
from contextlib import contextmanager

from ops.tracing.core import get_tracer
from ops.tracing.context import get_span_context


@contextmanager
def run_span(run_id: str, query: str):
    """
    WATCHTOWER: Root span for the entire agent run.
    Span name: run.execute
    """
    tracer = get_tracer("runs")
    with tracer.start_as_current_span("run.execute") as span:
        span.set_attribute("run_id", run_id)
        span.set_attribute("query", (query or "")[:200])
        yield span


@contextmanager
def agent_loop_run_span(session_id: str = "", query: str = ""):
    """
    WATCHTOWER: Span for the full agent loop.
    Span name: agent_loop.run
    """
    tracer = get_tracer("agent_loop")
    with tracer.start_as_current_span("agent_loop.run") as span:
        span.set_attribute("session_id", session_id or "")
        span.set_attribute("title", "Start the Agent Loop")
        span.set_attribute("query", (query or "")[:100])
        yield span


@contextmanager
def agent_plan_span():
    """
    WATCHTOWER: Span for the planner phase.
    Span name: agent_loop.plan
    Yields span so caller can set plan_graph after planner completes.
    """
    tracer = get_tracer("agent_loop")
    with tracer.start_as_current_span("agent_loop.plan") as span:
        yield span


@contextmanager
def agent_execute_dag_span():
    """
    WATCHTOWER: Span for DAG execution (contains execute_node spans).
    Span name: agent_loop.execute_dag
    """
    tracer = get_tracer("agent_loop")
    with tracer.start_as_current_span("agent_loop.execute_dag"):
        yield


@contextmanager
def agent_execute_node_span(step_id: str, agent_type: str, session_id: str = ""):
    """
    WATCHTOWER: Span for each agent step (PlannerAgent, CoderAgent, etc.).
    Span name: agent_loop.execute_node
    Attributes: node_id, agent, session_id
    """
    tracer = get_tracer("agent_loop")
    node_name = f"{agent_type}_{step_id}"
    with tracer.start_as_current_span(f"agent_loop.execute_node_{node_name}") as span:
        span.set_attribute("node_id", step_id)
        span.set_attribute("agent", agent_type)
        span.set_attribute("session_id", session_id or "")
        yield span


@contextmanager
def llm_span(model_key: str, model_type: str, prompt_length: int):
    """
    WATCHTOWER: Span for each LLM API call.
    Span name: llm.generate
    Enriches with agent/node_id from context. Caller sets output_length, output_preview after result.
    """
    tracer = get_tracer("model_manager")
    with tracer.start_as_current_span("llm.generate") as span:
        span.set_attribute("model", model_key)
        span.set_attribute("provider", model_type)
        span.set_attribute("prompt_length", prompt_length)
        ctx = get_span_context()
        if ctx.get("agent"):
            span.set_attribute("agent", ctx["agent"])
        if ctx.get("node_id"):
            span.set_attribute("node_id", ctx["node_id"])
        yield span
