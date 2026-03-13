"""
Arcturus Doctor: automated diagnostics.

Wraps ``ops.health.run_all_health_checks()`` and adds software/config validation.
Called via ``GET /admin/diagnostics``.

Each check returns a ``DiagnosticResult`` with actionable suggestions on failure.
"""

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("watchtower.diagnostics")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@dataclass
class DiagnosticResult:
    """Single diagnostic check result."""

    check: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "check": self.check,
            "status": self.status,
            "message": self.message,
        }
        if self.suggestion:
            d["suggestion"] = self.suggestion
        return d


# ------------------------------------------------------------------
# Individual checks
# ------------------------------------------------------------------


def _check_python_version() -> DiagnosticResult:
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 11:
        return DiagnosticResult("python_version", "pass", f"Python {version_str}")
    return DiagnosticResult(
        "python_version",
        "warn",
        f"Python {version_str} (3.11+ recommended)",
        suggestion="Upgrade to Python 3.11 or later for best compatibility.",
    )


def _check_env_vars() -> DiagnosticResult:
    required = ["GEMINI_API_KEY"]
    missing = [v for v in required if not os.environ.get(v)]
    if not missing:
        return DiagnosticResult("env_vars", "pass", "All required env vars set")
    return DiagnosticResult(
        "env_vars",
        "warn",
        f"Missing env vars: {', '.join(missing)}",
        suggestion="Set missing environment variables in .env file.",
    )


def _check_config_validity() -> DiagnosticResult:
    settings_path = _PROJECT_ROOT / "config" / "settings.json"
    if not settings_path.exists():
        return DiagnosticResult(
            "config_file",
            "fail",
            "config/settings.json not found",
            suggestion="Run the server once to auto-create from defaults, or copy settings.defaults.json.",
        )
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        required_keys = ["models", "ollama", "rag"]
        missing = [k for k in required_keys if k not in data]
        if missing:
            return DiagnosticResult(
                "config_file",
                "warn",
                f"settings.json missing keys: {', '.join(missing)}",
                suggestion="Add the missing keys or reset settings to defaults.",
            )
        return DiagnosticResult("config_file", "pass", "settings.json is valid")
    except json.JSONDecodeError as e:
        return DiagnosticResult(
            "config_file",
            "fail",
            f"settings.json is invalid JSON: {e}",
            suggestion="Fix the JSON syntax error or reset settings to defaults.",
        )


def _check_faiss_index() -> DiagnosticResult:
    index_dir = _PROJECT_ROOT / "data" / "faiss_index"
    if not index_dir.exists():
        return DiagnosticResult(
            "faiss_index",
            "warn",
            "No FAISS index directory found",
            suggestion="Index documents via the RAG system to create the FAISS index.",
        )
    index_files = list(index_dir.glob("*.faiss")) + list(index_dir.glob("*.index"))
    if not index_files:
        # Also check for .pkl files which FAISS uses
        index_files = list(index_dir.glob("*"))
    if not index_files:
        return DiagnosticResult(
            "faiss_index",
            "warn",
            "FAISS index directory exists but no index files found",
            suggestion="Index documents to generate FAISS index files.",
        )
    total_size = sum(f.stat().st_size for f in index_files if f.is_file())
    size_mb = round(total_size / (1024 * 1024), 2)
    return DiagnosticResult(
        "faiss_index",
        "pass",
        f"FAISS index: {len(index_files)} file(s), {size_mb} MB",
    )


def _check_disk_space() -> DiagnosticResult:
    try:
        import shutil

        total, used, free = shutil.disk_usage("/")
        free_gb = round(free / (1024**3), 1)
        if free_gb < 1:
            return DiagnosticResult(
                "disk_space",
                "fail",
                f"Only {free_gb} GB free disk space",
                suggestion="Free up disk space. At least 1 GB recommended.",
            )
        if free_gb < 5:
            return DiagnosticResult(
                "disk_space",
                "warn",
                f"{free_gb} GB free (5+ GB recommended)",
                suggestion="Consider freeing disk space for optimal performance.",
            )
        return DiagnosticResult("disk_space", "pass", f"{free_gb} GB free")
    except Exception as e:
        return DiagnosticResult("disk_space", "warn", f"Could not check: {e}")


def _check_services() -> List[DiagnosticResult]:
    """Wrap existing health checks as diagnostic results."""
    results = []
    try:
        from ops.health import run_all_health_checks

        for hc in run_all_health_checks():
            d = hc.to_dict()
            status_map = {"ok": "pass", "degraded": "warn", "down": "fail"}
            dr_status = status_map.get(d["status"], "warn")
            msg = d["service"]
            if d.get("latency_ms") is not None:
                msg += f" ({d['latency_ms']}ms)"
            if d.get("details"):
                msg += f" — {d['details']}"

            suggestion = ""
            if dr_status == "fail":
                suggestion = f"Start the {d['service']} service or check its configuration."
            elif dr_status == "warn":
                suggestion = f"Check {d['service']} — it may be partially available."

            results.append(
                DiagnosticResult(
                    check=f"service:{d['service']}",
                    status=dr_status,
                    message=msg,
                    suggestion=suggestion,
                )
            )
    except Exception as e:
        results.append(
            DiagnosticResult(
                "service_checks",
                "fail",
                f"Could not run health checks: {e}",
                suggestion="Check that ops.health module is importable.",
            )
        )
    return results


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------


def run_diagnostics() -> List[Dict[str, Any]]:
    """
    Run all diagnostic checks (arcturus doctor).

    Returns a list of dicts with keys: check, status, message, suggestion.
    """
    results: List[DiagnosticResult] = []

    # Software / environment checks
    results.append(_check_python_version())
    results.append(_check_env_vars())
    results.append(_check_config_validity())
    results.append(_check_faiss_index())
    results.append(_check_disk_space())

    # Service checks (wraps existing ops.health)
    results.extend(_check_services())

    summary = {
        "pass": sum(1 for r in results if r.status == "pass"),
        "warn": sum(1 for r in results if r.status == "warn"),
        "fail": sum(1 for r in results if r.status == "fail"),
    }
    overall = "pass" if summary["fail"] == 0 and summary["warn"] == 0 else "warn" if summary["fail"] == 0 else "fail"

    logger.info(
        "Diagnostics: %d pass, %d warn, %d fail → %s",
        summary["pass"],
        summary["warn"],
        summary["fail"],
        overall,
    )

    return {
        "overall": overall,
        "summary": summary,
        "checks": [r.to_dict() for r in results],
    }
