"""
Watchtower OpenTelemetry integration.
Exports trace spans to MongoDB for persistence and querying.

WATCHTOWER: All instrumentation is in this package. Import span helpers to avoid
inlining tracer logic in business code.
"""
from ops.tracing.core import (
    MongoDBSpanExporter,
    init_tracing,
    get_tracer,
    shutdown_tracing,
)
from ops.tracing.context import (
    set_span_context,
    get_span_context,
)
from ops.tracing.spans import (
    run_span,
    agent_loop_run_span,
    agent_plan_span,
    agent_execute_dag_span,
    agent_execute_node_span,
    agent_iteration_span,
    llm_span,
    code_execution_span,
    sandbox_run_span,
)
from ops.tracing.helpers import attach_plan_graph_to_span

__all__ = [
    "MongoDBSpanExporter",
    "init_tracing",
    "get_tracer",
    "shutdown_tracing",
    "set_span_context",
    "get_span_context",
    "run_span",
    "agent_loop_run_span",
    "agent_plan_span",
    "agent_execute_dag_span",
    "agent_execute_node_span",
    "agent_iteration_span",
    "llm_span",
    "code_execution_span",
    "sandbox_run_span",
    "attach_plan_graph_to_span",
]
