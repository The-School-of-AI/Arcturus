"""
CLI entry point for the Arcturus skill SDK.

Usage:
    python -m marketplace.sdk.cli skill create <name>
    python -m marketplace.sdk.cli skill create <name> --author "Jane Doe"
"""

from __future__ import annotations

import re
import sys
import logging
from pathlib import Path

import click
from jinja2 import Environment, FileSystemLoader, select_autoescape
from marketplace.sdk.templates import get_template, TEMPLATES_DIR as DEFAULT_TEMPLATES_DIR
from marketplace.version_manager import VersionManager

logger = logging.getLogger("bazaar.sdk")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parent / "templates"
SKILLS_ROOT = Path("marketplace") / "skills"

_VALID_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_name(name: str) -> None:
    """Raise ValueError if name is not a valid snake_case Python identifier."""
    if not _VALID_NAME.match(name):
        raise ValueError(
            f"Invalid skill name '{name}'. "
            "Must be lowercase snake_case (e.g. 'weather_fetcher')."
        )


def _render(env: Environment, template_name: str, **kwargs: object) -> str:
    """Render a Jinja2 template by name, passing kwargs as context."""
    tpl = env.get_template(template_name)
    return tpl.render(**kwargs)


def _write(path: Path, content: str) -> None:
    """Write *content* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    click.echo(f"  created  {path}")


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

@click.group()
def main() -> None:
    """Arcturus Bazaar Skill Development Kit."""


@main.group()
def skill() -> None:
    """Commands for creating, testing, and publishing skills."""


@main.group()
def admin() -> None:
    """Admin and moderation commands for the marketplace."""


@skill.command("create")
@click.argument("name")
@click.option("--author", default="Community", show_default=True,
              help="Author name embedded in the manifest.")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True,
              help="Root directory where the skill folder will be created.")
@click.option(
    "--template", "template_name",
    default="default",
    show_default=True,
    type=click.Choice(["default", "prompt_only", "tool_enabled", "agent_based"],
                      case_sensitive=False),
    help="Starter template to use for the new skill.",
)
def create_skill(name: str, author: str, skills_root: str,
                 template_name: str) -> None:
    """
    Scaffold a new skill project called NAME.

    Use --template to select a starter pattern:
      default      Blank slate (same as Day 11)
      prompt_only  Text transformation, no permissions
      tool_enabled HTTP/API skill, declares network permission
      agent_based  Orchestrates other marketplace skills
    """
    try:
        _validate_name(name)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    skill_dir = Path(skills_root) / name
    if skill_dir.exists():
        click.echo(f"Error: skill directory already exists: {skill_dir}", err=True)
        sys.exit(1)

    # Resolve template
    from marketplace.sdk.templates import get_template
    try:
        tpl = get_template(template_name)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    env = Environment(
        loader=FileSystemLoader(str(tpl.directory)),
        autoescape=select_autoescape([]),
        keep_trailing_newline=True,
    )

    # For templates that don't have their own src_init.py.j2, fall back to root
    root_env = Environment(
        loader=FileSystemLoader(str(DEFAULT_TEMPLATES_DIR)),
        autoescape=select_autoescape([]),
        keep_trailing_newline=True,
    )

    ctx = {"skill_name": name, "author": author}

    click.echo(f"\n🔨  Scaffolding skill '{name}' "
               f"[template: {template_name}] in {skill_dir}/\n")

    # manifest.yaml, tools/main.py, test, README come from the template dir
    _write(skill_dir / "manifest.yaml",
           _render(env, "manifest.yaml.j2", **ctx))

    _write(skill_dir / "src" / "__init__.py",
           _render(root_env, "src_init.py.j2", **ctx))   # always the same

    _write(skill_dir / "src" / "tools" / "main.py",
           _render(env, "tools_main.py.j2", **ctx))

    _write(skill_dir / "tests" / f"test_{name}.py",
           _render(env, "test_skill.py.j2", **ctx))

    _write(skill_dir / "README.md",
           _render(env, "README.md.j2", **ctx))

    _register_draft(skill_dir)

    click.echo(f"\n✅  Done! Next steps:\n")
    click.echo(f"    1. Edit {skill_dir}/manifest.yaml")
    click.echo(f"    2. Implement {skill_dir}/src/tools/main.py")
    click.echo(f"    3. Run: python -m marketplace.sdk.cli skill test {name}")
    click.echo(f"    4. Run: python -m marketplace.sdk.cli skill publish {name}\n")

def _register_draft(skill_dir: Path) -> None:
    """
    Register the new skill as a draft entry in the SkillRegistry.
    Safe to call with a partially-generated directory (only manifest needed).
    """
    try:
        from marketplace.registry import SkillRegistry
        registry = SkillRegistry()
        registry.register_skill(skill_dir)
        click.echo(f"  registered in registry (status=draft)")
    except Exception as exc:  # noqa: BLE001
        # Non-fatal: scaffold succeeds even if registry is unavailable
        logger.warning("Could not register skill in registry: %s", exc)
        click.echo(f"  ⚠️  registry registration skipped: {exc}")

@skill.command("template")
@click.argument("action", type=click.Choice(["list"]), default="list")
def template_cmd(action: str) -> None:
    """
    Manage skill templates.

    \b
    Actions:
      list   Show all available templates
    """
    if action == "list":
        from marketplace.sdk.templates import list_templates
        click.echo("\n📋  Available skill templates:\n")
        for tpl in list_templates():
            perms = (", ".join(tpl.permissions)
                     if tpl.permissions else "none")
            click.echo(f"  {tpl.name:<16} {tpl.description}")
            click.echo(f"  {'':16} permissions: {perms}\n")

@skill.command("test")
@click.argument("name")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
@click.option("--json", "output_json", is_flag=True, default=False,
              help="Print full JSON report instead of human-readable output.")
def test_skill(name: str, skills_root: str, output_json: bool) -> None:
    """
    Run the local test harness on skill NAME.

    Validates the manifest and runs each declared tool inside a sandbox.
    """
    from marketplace.sdk.test_harness import run_harness

    skill_dir = Path(skills_root) / name
    if not skill_dir.exists():
        click.echo(f"Error: skill directory not found: {skill_dir}", err=True)
        sys.exit(1)

    click.echo(f"\n🔍  Testing skill '{name}' ...\n")
    report = run_harness(skill_dir)

    if output_json:
        click.echo(report.as_json())
    else:
        for r in report.results:
            icon = "✅" if r.passed else "❌"
            click.echo(f"  {icon}  {r.check}")
            if r.message:
                click.echo(f"       {r.message}")
            if not r.passed and r.hint:
                click.echo(f"     → {r.hint}")

    click.echo()
    if report.passed:
        click.echo("✅  All checks passed! Ready to publish.")
    else:
        failures = len(report.failed)
        click.echo(f"❌  {failures} check(s) failed. Fix them before publishing.")
        sys.exit(1)

@skill.command("doc")
@click.argument("name")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
@click.option("--out-root", default="docs/skills", show_default=True,
              help="Output directory for the generated .md file.")
def doc_skill(name: str, skills_root: str, out_root: str) -> None:
    """
    Generate Markdown documentation for skill NAME.

    Reads manifest.yaml and tool docstrings.
    Writes docs/skills/<name>.md (or --out-root/<name>.md).
    """
    from marketplace.sdk.docgen import generate_doc

    skill_dir = Path(skills_root) / name
    if not skill_dir.exists():
        click.echo(f"Error: skill directory not found: {skill_dir}", err=True)
        sys.exit(1)

    try:
        out_path = generate_doc(skill_dir, out_root=Path(out_root))
        click.echo(f"\n📄  Documentation written to: {out_path}\n")
    except (FileNotFoundError, ValueError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Version Management Commands
# ---------------------------------------------------------------------------

@skill.command("rollback")
@click.argument("name")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def rollback_skill(name: str, skills_root: str) -> None:
    """
    Roll back skill NAME to its previous version.

    Requires at least one prior version in the version ledger.
    """
    vm = VersionManager(skills_dir=Path(skills_root))
    result = vm.rollback(name)

    if result.success:
        click.echo(
            f"\n⏪  Rolled back '{name}': "
            f"v{result.previous_version} → v{result.restored_version}\n"
        )
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


@skill.command("pin")
@click.argument("name")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def pin_skill(name: str, skills_root: str) -> None:
    """
    Pin skill NAME at its current version to prevent upgrades.
    """
    vm = VersionManager(skills_dir=Path(skills_root))
    result = vm.pin(name)

    if result.success:
        click.echo(f"\n📌  {result.message}\n")
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


@skill.command("unpin")
@click.argument("name")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def unpin_skill(name: str, skills_root: str) -> None:
    """
    Un-pin skill NAME to allow upgrades again.
    """
    vm = VersionManager(skills_dir=Path(skills_root))
    result = vm.unpin(name)

    if result.success:
        click.echo(f"\n🔓  {result.message}\n")
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


@skill.command("upgrade")
@click.argument("name")
@click.option("--source", required=True, type=click.Path(exists=True),
              help="Path to the directory containing the new skill version.")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def upgrade_skill(name: str, source: str, skills_root: str) -> None:
    """
    Upgrade skill NAME to a new version from --source directory.

    Archives the current version before installing the new one.
    """
    from marketplace.installer import SkillInstaller
    from marketplace.registry import SkillRegistry

    skills_path = Path(skills_root)
    registry = SkillRegistry(skills_dir=skills_path)
    registry.discover_skills()
    installer = SkillInstaller(registry=registry)

    vm = VersionManager(skills_dir=skills_path)
    result = vm.upgrade(name, source_dir=Path(source), installer=installer)

    if result.success:
        click.echo(
            f"\n⬆️  Upgraded '{name}': "
            f"v{result.previous_version} → v{result.restored_version}\n"
        )
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Admin Management Commands
# ---------------------------------------------------------------------------

@admin.command("status")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_status(skills_root: str) -> None:
    """
    Show a high-level overview of the marketplace.

    Displays skill counts, moderation queue size, and abuse events.
    """
    from marketplace.admin import AdminDashboard, format_status_summary

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    summary = dashboard.get_status_summary()
    click.echo(format_status_summary(summary))


@admin.command("info")
@click.argument("name")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_info(name: str, skills_root: str) -> None:
    """
    Show detailed info for skill NAME.

    Combines version history, moderation record, and abuse events.
    """
    from marketplace.admin import AdminDashboard, format_skill_report

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    report = dashboard.get_skill_report(name)
    click.echo(format_skill_report(report))


@admin.command("queue")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_queue(skills_root: str) -> None:
    """
    Show all flagged skills awaiting review.
    """
    from marketplace.admin import AdminDashboard, format_moderation_queue

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    queue = dashboard.get_moderation_queue()
    click.echo(format_moderation_queue(queue))


@admin.command("flag")
@click.argument("name")
@click.option("--reason", required=True,
              type=click.Choice(
                  ["community_report", "suspicious_code", "policy_violation",
                   "excessive_permissions", "copycat"],
                  case_sensitive=False),
              help="Reason for flagging.")
@click.option("--detail", default="", help="Free-text explanation.")
@click.option("--moderator", default="admin", show_default=True)
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_flag(name: str, reason: str, detail: str,
               moderator: str, skills_root: str) -> None:
    """Flag skill NAME for moderation review."""
    from marketplace.admin import AdminDashboard
    from marketplace.moderation import FlagReason

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    result = dashboard.flag_skill(
        name, FlagReason(reason), reporter=moderator, detail=detail,
    )
    if result.success:
        click.echo(f"\n🚩  {result.message}\n")
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


@admin.command("review")
@click.argument("name")
@click.option("--moderator", required=True, help="Moderator starting the review.")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_review(name: str, moderator: str, skills_root: str) -> None:
    """Start reviewing flagged skill NAME."""
    from marketplace.admin import AdminDashboard

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    result = dashboard.start_review(name, moderator)
    if result.success:
        click.echo(f"\n🔍  {result.message}\n")
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


@admin.command("approve")
@click.argument("name")
@click.option("--moderator", required=True, help="Moderator approving the skill.")
@click.option("--reason", default="Approved after review", show_default=True)
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_approve(name: str, moderator: str, reason: str,
                  skills_root: str) -> None:
    """Approve skill NAME — restores it to active status."""
    from marketplace.admin import AdminDashboard

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    result = dashboard.approve_skill(name, moderator, reason)
    if result.success:
        click.echo(f"\n✅  {result.message}\n")
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


@admin.command("suspend")
@click.argument("name")
@click.option("--moderator", required=True, help="Moderator suspending the skill.")
@click.option("--reason", default="Suspended after review", show_default=True)
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_suspend(name: str, moderator: str, reason: str,
                  skills_root: str) -> None:
    """Suspend skill NAME — permanently blocks installation."""
    from marketplace.admin import AdminDashboard

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    result = dashboard.suspend_skill(name, moderator, reason)
    if result.success:
        click.echo(f"\n🚫  {result.message}\n")
    else:
        click.echo(f"Error: {result.message}", err=True)
        sys.exit(1)


@admin.command("abuse-report")
@click.option("--skill", "skill_name", default=None,
              help="Filter by skill name.")
@click.option("--type", "event_type", default=None,
              type=click.Choice(
                  ["rate_limited", "quota_exceeded", "circuit_tripped",
                   "circuit_recovered", "error_recorded"],
                  case_sensitive=False),
              help="Filter by event type.")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_abuse_report(skill_name: str, event_type: str,
                       skills_root: str) -> None:
    """Show abuse events (rate limits, circuit trips, errors)."""
    from marketplace.admin import AdminDashboard, format_abuse_report
    from marketplace.abuse import AbuseEventType

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    et = AbuseEventType(event_type) if event_type else None
    events = dashboard.get_abuse_report(skill_name=skill_name, event_type=et)
    click.echo(format_abuse_report(events))


@admin.command("reset-abuse")
@click.argument("name")
@click.option("--skills-root", default=str(SKILLS_ROOT), show_default=True)
def admin_reset_abuse(name: str, skills_root: str) -> None:
    """Reset abuse counters for skill NAME (keeps audit trail)."""
    from marketplace.admin import AdminDashboard

    dashboard = AdminDashboard(skills_dir=Path(skills_root))
    dashboard.reset_abuse(name)
    click.echo(f"\n🔄  Abuse counters reset for '{name}' (audit trail preserved)\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()