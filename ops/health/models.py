"""
Watchtower Health data models.
"""

from dataclasses import dataclass
from typing import Any


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


@dataclass
class ResourceSnapshot:
    """Point-in-time snapshot of system resource usage."""

    cpu_pct: float
    mem_pct: float
    disk_pct: float
    mem_used_mb: float = 0.0
    mem_total_mb: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_pct": self.cpu_pct,
            "mem_pct": self.mem_pct,
            "disk_pct": self.disk_pct,
            "mem_used_mb": self.mem_used_mb,
            "mem_total_mb": self.mem_total_mb,
            "disk_used_gb": self.disk_used_gb,
            "disk_total_gb": self.disk_total_gb,
        }
