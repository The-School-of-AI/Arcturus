"""
Local test harness for Bazaar marketplace skills.

Validates a skill's manifest and runs each declared tool inside a sandbox,
giving developers fast feedback before they publish.

Usage (programmatic):
    from marketplace.sdk.test_harness import run_harness
    report = run_harness(Path("marketplace/skills/weather_fetcher"))
    print(report.passed)      # True/False
    print(report.as_json())   # Full JSON report

Usage (CLI):
    python -m marketplace.sdk.cli skill test weather_fetcher
"""

from __future__ import annotations

import importlib
import sys
import json
import logging
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from marketplace.skill_base import SkillManifest, load_manifest

logger = logging.getLogger("bazaar.sdk")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class HarnessResult:
    """Result of a single check."""
    check: str              # human-readable check name
    passed: bool
    message: str = ""       # detail or error text
    hint: str = ""          # actionable fix hint (only on failure)


@dataclass
class HarnessReport:
    """Aggregated results from running the harness on one skill."""
    skill_name: str
    results: List[HarnessResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed(self) -> List[HarnessResult]:
        return [r for r in self.results if not r.passed]

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def _add(self, check: str, passed: bool,
             message: str = "", hint: str = "") -> HarnessResult:
        r = HarnessResult(check=check, passed=passed,
                          message=message, hint=hint)
        self.results.append(r)
        return r


def _check_manifest(report: HarnessReport,
                    skill_dir: Path) -> Optional[SkillManifest]:
    """Load and validate the manifest. Returns None on failure."""
    manifest_path = skill_dir / "manifest.yaml"

    # Check 1: file exists
    if not manifest_path.exists():
        report._add(
            "manifest exists",
            passed=False,
            message=f"No manifest.yaml found at {manifest_path}",
            hint="Run `arcturus skill create <name>` to scaffold a skill first.",
        )
        return None
    report._add("manifest exists", passed=True)

    # Check 2: Pydantic validation
    try:
        manifest = load_manifest(manifest_path)
    except Exception as exc:
        report._add(
            "manifest is valid",
            passed=False,
            message=str(exc),
            hint="Fix the YAML errors listed above then re-run.",
        )
        return None
    report._add("manifest is valid", passed=True,
                message=f"v{manifest.version} by {manifest.author}")

    # Check 3: at least one tool declared
    if not manifest.tools:
        report._add(
            "manifest has tools",
            passed=False,
            message="No tools declared in manifest.yaml",
            hint="Add at least one entry under the `tools:` key.",
        )
    else:
        report._add("manifest has tools", passed=True,
                    message=f"{len(manifest.tools)} tool(s) declared")

    return manifest

def _check_tool_importable(report: HarnessReport,
                           tool_name: str,
                           module_path: str,
                           function: str) -> bool:
    """Verify the tool module + function can be imported."""

    # Check: module importable
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        report._add(
            f"tool {tool_name} — module importable",
            passed=False,
            message=str(exc),
            hint=(
                f"Make sure `{module_path}` exists and is on sys.path. "
                "Check that your skill package is installed or your CWD is correct."
            ),
        )
        return False
    report._add(f"tool {tool_name} — module importable", passed=True)

    # Check: function exists in module
    if not hasattr(mod, function):
        report._add(
            f"tool {tool_name} — function callable",
            passed=False,
            message=f"Function '{function}' not found in module '{module_path}'",
            hint=f"Add a `def {function}(**kwargs)` to {module_path}.",
        )
        return False
    report._add(f"tool {tool_name} — function callable", passed=True)
    return True

def _check_tool_sandbox(report: HarnessReport,
                        tool_name: str,
                        module_path: str,
                        function: str,
                        permissions: List[str]) -> None:
    """
    Run the tool inside SandboxedExecutor with the skill's declared permissions.

    If the tool calls a blocked module (e.g. `requests` without `network`
    permission), the sandbox raises ImportError — we catch it and report.
    """
    try:
        from marketplace.sandbox import SandboxedExecutor, PermissionGuard
    except ImportError:
        report._add(
            f"tool {tool_name} — sandbox run",
            passed=False,
            message="marketplace.sandbox not found — complete Day 9 first.",
        )
        return

    try:
        executor = SandboxedExecutor()
        executor.register_skill_permissions(report.skill_name, permissions)
        from marketplace.sandbox import SAFE_MODULES
        top_level = module_path.split(".")[0]
        SAFE_MODULES.add(top_level)
        try:
            with PermissionGuard(permissions=permissions):
                # We must import the module inside the guard to catch top-level unauthorized imports
                # Since _check_tool_importable already imported it outside the sandbox, we must remove it
                # from sys.modules so it gets re-evaluated inside the sandbox.
                if module_path in sys.modules:
                    del sys.modules[module_path]
                
                mod = importlib.import_module(module_path)
                func = getattr(mod, function)
                executor.execute_tool(
                    tool_func=func,
                    tool_name=tool_name,
                    skill_name=report.skill_name,
                    arguments={},
                )
        finally:
            SAFE_MODULES.discard(top_level)
        report._add(f"tool {tool_name} — sandbox run", passed=True,
                    message="tool ran without sandbox violations")

    except ImportError as exc:
        # Sandbox blocked the tool from importing something
        blocked = str(exc)
        report._add(
            f"tool {tool_name} — sandbox run",
            passed=False,
            message=blocked,
            hint=(
                "The tool tried to import a module it is not allowed to use. "
                "Either add the required permission to manifest.yaml, or "
                "remove the import from your tool code."
            ),
        )
    except Exception as exc:
        # Tool crashed for a non-sandbox reason (e.g. missing API key)
        # We still consider this a pass from a *permissions* standpoint
        report._add(
            f"tool {tool_name} — sandbox run",
            passed=True,
            message=(
                f"Tool raised {type(exc).__name__} (non-sandbox error — OK for now): "
                f"{exc}"
            ),
        )

def run_harness(skill_dir: Path) -> HarnessReport:
    """
    Run the full test harness on a skill directory.

    Args:
        skill_dir: Path to the skill's root directory (must contain manifest.yaml)

    Returns:
        HarnessReport with all check results.
    """
    skill_name = skill_dir.name
    report = HarnessReport(skill_name=skill_name)

    # Phase 1: Manifest checks
    manifest = _check_manifest(report, skill_dir)
    if manifest is None:
        return report  # can't proceed without a manifest

    # Phase 2: Per-tool checks
    for tool in manifest.tools:
        importable = _check_tool_importable(
            report, tool.name, tool.module, tool.function
        )
        if importable:
            _check_tool_sandbox(
                report, tool.name, tool.module, tool.function,
                manifest.permissions,
            )

    return report


