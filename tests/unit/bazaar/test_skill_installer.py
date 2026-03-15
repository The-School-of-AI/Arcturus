"""Tests for SkillInstaller — install, uninstall, validate, and dependency resolution."""
from pathlib import Path

import pytest

from marketplace.installer import InstallResult, SkillInstaller
from marketplace.registry import SkillRegistry

# --- Helpers ---

def create_skill_dir(base_path: Path, name: str, extra_yaml: str = "") -> Path:
    """Helper to create a skill directory with a manifest."""
    skill_dir = base_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "manifest.yaml").write_text(f"""
name: {name}
version: 1.0.0
description: Test skill {name}
{extra_yaml}
""")
    return skill_dir


# --- Fixtures ---

@pytest.fixture
def setup(tmp_path):
    """Create installer with a fresh registry and separate source/install dirs."""
    install_dir = tmp_path / "installed_skills"
    install_dir.mkdir()
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    registry = SkillRegistry(skills_dir=install_dir)
    installer = SkillInstaller(registry=registry)

    return installer, registry, source_dir, install_dir


# --- Validation Tests ---

def test_validate_passes_for_valid_skill(setup):
    """A skill with a valid manifest should pass validation."""
    installer, registry, source_dir, _ = setup
    skill_dir = create_skill_dir(source_dir, "valid_skill")

    result = installer.validate_skill(skill_dir)
    assert result.success is True


def test_validate_fails_for_missing_directory(setup):
    """Validation should fail if the source directory doesn't exist."""
    installer, _, _, _ = setup

    result = installer.validate_skill(Path("/nonexistent/path"))
    assert result.success is False
    assert "not found" in result.message


def test_validate_fails_for_missing_manifest(setup):
    """Validation should fail if manifest.yaml is missing."""
    installer, _, source_dir, _ = setup
    skill_dir = source_dir / "no_manifest"
    skill_dir.mkdir()

    result = installer.validate_skill(skill_dir)
    assert result.success is False
    assert "manifest" in result.message.lower()


def test_validate_fails_for_missing_skill_dependencies(setup):
    """Validation should fail if required skill dependencies aren't installed."""
    installer, _, source_dir, _ = setup
    skill_dir = create_skill_dir(source_dir, "needs_deps", extra_yaml="""
skill_dependencies:
  - gmail_reader
  - rag
""")

    result = installer.validate_skill(skill_dir)
    assert result.success is False
    assert "gmail_reader" in result.missing_deps
    assert "rag" in result.missing_deps


# --- Install Tests ---

def test_install_skill_copies_files_to_target(setup):
    """Installing a skill should copy files into the install directory."""
    installer, _, source_dir, install_dir = setup
    skill_dir = create_skill_dir(source_dir, "my_skill")

    result = installer.install_skill(skill_dir)
    assert result.success is True
    assert (install_dir / "my_skill" / "manifest.yaml").exists()


def test_install_skill_registers_in_registry(setup):
    """Installed skill should be discoverable in the registry."""
    installer, registry, source_dir, _ = setup
    skill_dir = create_skill_dir(source_dir, "my_skill")

    installer.install_skill(skill_dir)
    assert registry.get_skill("my_skill") is not None


def test_install_fails_if_already_installed(setup):
    """Installing a skill that already exists should fail without force."""
    installer, _, source_dir, _ = setup
    skill_dir = create_skill_dir(source_dir, "my_skill")

    installer.install_skill(skill_dir)
    result = installer.install_skill(skill_dir)
    assert result.success is False
    assert "already installed" in result.message


def test_install_with_force_overwrites_existing(setup):
    """force=True should allow overwriting an existing skill."""
    installer, registry, source_dir, _ = setup
    skill_dir = create_skill_dir(source_dir, "my_skill")

    installer.install_skill(skill_dir)
    result = installer.install_skill(skill_dir, force=True)
    assert result.success is True


def test_install_fails_if_deps_not_satisfied(setup):
    """Install should fail if skill_dependencies aren't installed."""
    installer, _, source_dir, _ = setup
    skill_dir = create_skill_dir(source_dir, "needs_gmail", extra_yaml="""
skill_dependencies:
  - gmail_reader
""")

    result = installer.install_skill(skill_dir)
    assert result.success is False
    assert "gmail_reader" in result.missing_deps


# --- Uninstall Tests ---

def test_uninstall_removes_from_registry(setup):
    """Uninstalling should remove the skill from the registry."""
    installer, registry, source_dir, _ = setup
    skill_dir = create_skill_dir(source_dir, "my_skill")

    installer.install_skill(skill_dir)
    result = installer.uninstall_skill("my_skill")
    assert result.success is True
    assert registry.get_skill("my_skill") is None


def test_uninstall_deletes_files_from_disk(setup):
    """Uninstalling should delete the skill directory from disk."""
    installer, _, source_dir, install_dir = setup
    skill_dir = create_skill_dir(source_dir, "my_skill")

    installer.install_skill(skill_dir)
    installer.uninstall_skill("my_skill")
    assert not (install_dir / "my_skill").exists()


def test_uninstall_fails_for_unknown_skill(setup):
    """Uninstalling a skill that doesn't exist should fail."""
    installer, _, _, _ = setup

    result = installer.uninstall_skill("nonexistent")
    assert result.success is False


def test_uninstall_blocked_by_dependents(setup):
    """Uninstalling a skill that others depend on should fail without force."""
    installer, registry, source_dir, install_dir = setup

    # Install base skill
    base_dir = create_skill_dir(source_dir, "gmail_reader")
    installer.install_skill(base_dir)

    # Install dependent skill directly into install_dir
    dep_dir = create_skill_dir(install_dir, "smart_email", extra_yaml="""
skill_dependencies:
  - gmail_reader
""")
    registry.register_skill(dep_dir)

    # Try to uninstall base — should fail
    result = installer.uninstall_skill("gmail_reader")
    assert result.success is False
    assert "smart_email" in str(result.missing_deps)


def test_uninstall_force_ignores_dependents(setup):
    """force=True should allow uninstalling even with dependents."""
    installer, registry, source_dir, install_dir = setup

    base_dir = create_skill_dir(source_dir, "gmail_reader")
    installer.install_skill(base_dir)

    dep_dir = create_skill_dir(install_dir, "smart_email", extra_yaml="""
skill_dependencies:
  - gmail_reader
""")
    registry.register_skill(dep_dir)

    result = installer.uninstall_skill("gmail_reader", force=True)
    assert result.success is True


# --- InstallResult Tests ---

def test_install_result_has_correct_fields():
    """InstallResult should be creatable with all fields."""
    result = InstallResult(
        success=True,
        skill_name="test",
        message="All good",
        missing_deps=["dep1"]
    )
    assert result.success is True
    assert result.skill_name == "test"
    assert result.missing_deps == ["dep1"]
