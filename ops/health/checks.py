"""
Watchtower Health checks: service connectivity and system resource probes.
"""

import os
from typing import List

from config.settings_loader import settings, get_ollama_url
from memory.qdrant_config import get_qdrant_url
from ops.health.models import HealthResult, ResourceSnapshot


def check_mongodb() -> HealthResult:
    """Check MongoDB connectivity via watchtower config."""
    import time

    watchtower = settings.get("watchtower", {})
    uri = watchtower.get("mongodb_uri", "mongodb://localhost:27017")
    client = None
    try:
        from pymongo import MongoClient

        start = time.perf_counter()
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        latency_ms = (time.perf_counter() - start) * 1000
        return HealthResult(
            service="mongodb", status="ok", latency_ms=round(latency_ms, 2)
        )
    except Exception as e:
        return HealthResult(service="mongodb", status="down", details=str(e))
    finally:
        if client is not None:
            client.close()


def check_qdrant() -> HealthResult:
    """Check Qdrant REST API health endpoint."""
    import time

    try:
        import httpx

        url = get_qdrant_url().rstrip("/")
        health_url = f"{url}/health"
        start = time.perf_counter()
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(health_url)
            latency_ms = (time.perf_counter() - start) * 1000
        if resp.status_code == 200:
            return HealthResult(
                service="qdrant", status="ok", latency_ms=round(latency_ms, 2)
            )
        return HealthResult(
            service="qdrant",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            details=f"HTTP {resp.status_code}",
        )
    except Exception as e:
        return HealthResult(service="qdrant", status="down", details=str(e))


def check_ollama() -> HealthResult:
    """Check Ollama API availability."""
    import time

    try:
        import httpx

        base = get_ollama_url("base")
        start = time.perf_counter()
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(f"{base}/api/tags")
            latency_ms = (time.perf_counter() - start) * 1000
        if resp.status_code == 200:
            return HealthResult(
                service="ollama", status="ok", latency_ms=round(latency_ms, 2)
            )
        return HealthResult(
            service="ollama",
            status="degraded",
            latency_ms=round(latency_ms, 2),
            details=f"HTTP {resp.status_code}",
        )
    except Exception as e:
        return HealthResult(service="ollama", status="down", details=str(e))


def check_mcp() -> HealthResult:
    """Check MCP gateway: report status based on connected servers."""
    try:
        from shared.state import get_multi_mcp

        multi_mcp = get_multi_mcp()
        sessions = getattr(multi_mcp, "sessions", {})
        connected = [k for k, v in sessions.items() if v is not None]
        if connected:
            return HealthResult(
                service="mcp_gateway",
                status="ok",
                details=f"{len(connected)} server(s): {', '.join(connected[:5])}{'...' if len(connected) > 5 else ''}",
            )
        configs = getattr(multi_mcp, "server_configs", {})
        enabled = [k for k, v in configs.items() if v.get("enabled", True)]
        if not enabled:
            return HealthResult(
                service="mcp_gateway",
                status="ok",
                details="No MCP servers configured",
            )
        return HealthResult(
            service="mcp_gateway",
            status="degraded",
            details=f"Configured: {len(enabled)}, connected: 0",
        )
    except Exception as e:
        return HealthResult(service="mcp_gateway", status="down", details=str(e))


def check_neo4j() -> HealthResult:
    """Check Neo4j connectivity. Returns ok if reachable, skipped if disabled."""
    import time

    enabled = os.environ.get("NEO4J_ENABLED", "").lower() in ("true", "1", "yes")
    if not enabled:
        return HealthResult(
            service="neo4j",
            status="ok",
            details="Disabled (NEO4J_ENABLED not set)",
        )

    try:
        from neo4j import GraphDatabase
    except ImportError:
        return HealthResult(
            service="neo4j", status="down", details="neo4j driver not installed"
        )

    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    if not password:
        return HealthResult(
            service="neo4j", status="down", details="NEO4J_PASSWORD not set"
        )

    driver = None
    try:
        start = time.perf_counter()
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        latency_ms = (time.perf_counter() - start) * 1000
        return HealthResult(
            service="neo4j", status="ok", latency_ms=round(latency_ms, 2)
        )
    except Exception as e:
        return HealthResult(service="neo4j", status="down", details=str(e))
    finally:
        if driver is not None:
            driver.close()


def check_agent_core() -> HealthResult:
    """Check agent core liveness via active_loops state."""
    try:
        from shared.state import active_loops

        loop_count = len(active_loops)
        if loop_count == 0:
            return HealthResult(
                service="agent_core",
                status="ok",
                details="Idle (no active loops)",
            )
        return HealthResult(
            service="agent_core",
            status="ok",
            details=f"{loop_count} active loop(s)",
        )
    except Exception as e:
        return HealthResult(service="agent_core", status="down", details=str(e))


def collect_resources() -> ResourceSnapshot:
    """Collect system resource metrics using psutil."""
    import psutil

    cpu_pct = psutil.cpu_percent(interval=0.1)

    mem = psutil.virtual_memory()
    mem_pct = mem.percent
    mem_used_mb = round(mem.used / (1024 * 1024), 1)
    mem_total_mb = round(mem.total / (1024 * 1024), 1)

    disk = psutil.disk_usage("/")
    disk_pct = disk.percent
    disk_used_gb = round(disk.used / (1024**3), 2)
    disk_total_gb = round(disk.total / (1024**3), 2)

    return ResourceSnapshot(
        cpu_pct=cpu_pct,
        mem_pct=mem_pct,
        disk_pct=disk_pct,
        mem_used_mb=mem_used_mb,
        mem_total_mb=mem_total_mb,
        disk_used_gb=disk_used_gb,
        disk_total_gb=disk_total_gb,
    )


def run_all_health_checks() -> List[HealthResult]:
    """Run health checks for all services. Returns list of HealthResult."""
    return [
        check_mongodb(),
        check_qdrant(),
        check_ollama(),
        check_mcp(),
        check_neo4j(),
        check_agent_core(),
    ]
