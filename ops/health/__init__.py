"""
Watchtower Health package: service health checks, resource metrics, and persistence.

Re-exports all public symbols so existing imports continue to work:
    from ops.health import HealthResult, run_all_health_checks
"""

from ops.health.models import HealthResult, ResourceSnapshot
from ops.health.checks import (
    check_mongodb,
    check_qdrant,
    check_ollama,
    check_mcp,
    check_neo4j,
    check_agent_core,
    collect_resources,
    run_all_health_checks,
)

__all__ = [
    "HealthResult",
    "ResourceSnapshot",
    "check_mongodb",
    "check_qdrant",
    "check_ollama",
    "check_mcp",
    "check_neo4j",
    "check_agent_core",
    "collect_resources",
    "run_all_health_checks",
]
