"""
Watchtower Health module: service health checks for admin dashboard.
Checks MongoDB, Qdrant, Ollama, and MCP gateway.
"""
from dataclasses import dataclass
from typing import Any

from config.settings_loader import settings, get_ollama_url
from memory.qdrant_config import get_qdrant_url


@dataclass
class HealthResult:
    """Result of a single service health check."""

    service: str
    status: str  # "ok" | "degraded" | "down"
    latency_ms: float | None = None
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "details": self.details,
        }


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
        return HealthResult(service="mongodb", status="ok", latency_ms=round(latency_ms, 2))
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
            return HealthResult(service="qdrant", status="ok", latency_ms=round(latency_ms, 2))
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
            return HealthResult(service="ollama", status="ok", latency_ms=round(latency_ms, 2))
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
            return HealthResult(service="mcp_gateway", status="ok", details="No MCP servers configured")
        return HealthResult(
            service="mcp_gateway",
            status="degraded",
            details=f"Configured: {len(enabled)}, connected: 0",
        )
    except Exception as e:
        return HealthResult(service="mcp_gateway", status="down", details=str(e))


def run_all_health_checks() -> list[HealthResult]:
    """Run health checks for all services. Returns list of HealthResult."""
    return [
        check_mongodb(),
        check_qdrant(),
        check_ollama(),
        check_mcp(),
    ]
