"""
P05 Chronicle: Git/checkpoint alignment and cross-module trace linking.

Provides:
- Git alignment: capture HEAD commit sha and branch when creating checkpoints
- Trace linking: capture OpenTelemetry trace_id/span_id for Watchtower cross-module linking
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def get_git_head_info(repo_path: Path | None = None) -> dict[str, str]:
    """
    Get current git HEAD commit sha and branch.
    Returns {"git_commit_sha": sha, "git_branch": branch} or empty strings if not a git repo.
    """
    result: dict[str, str] = {"git_commit_sha": "", "git_branch": ""}
    cwd = repo_path or Path.cwd()
    if not (cwd / ".git").exists():
        return result
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            result["git_commit_sha"] = out.stdout.strip()[:40]
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            result["git_branch"] = out.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return result


def get_current_trace_ids() -> dict[str, str]:
    """
    Get current OpenTelemetry trace_id and span_id from active span.
    Links Chronicle checkpoints to Watchtower spans for cross-module trace linking.
    Returns {"trace_id": hex, "span_id": hex} or empty strings if no active span.
    """
    result: dict[str, str] = {"trace_id": "", "span_id": ""}
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if not span or not span.is_recording():
            return result
        ctx = span.get_span_context()
        if ctx.trace_id and ctx.span_id:
            result["trace_id"] = format(ctx.trace_id, "032x")
            result["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        pass
    return result
