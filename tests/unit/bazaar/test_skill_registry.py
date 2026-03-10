"""Tests for SkillRegistry — discovery, lookup, search, and dependency management."""
import pytest
from pathlib import Path
from marketplace.registry import SkillRegistry
from marketplace.skill_base import SkillManifest


# --- Fixtures ---

@pytest.fixture
def empty_registry(tmp_path):
    """A registry pointing to an empty directory."""
    return SkillRegistry(skills_dir=tmp_path)


@pytest.fixture
def sample_registry(tmp_path):
    """A registry with two sample skills pre-loaded."""
    # Create gmail_reader skill
    gmail_dir = tmp_path / "gmail_reader"
    gmail_dir.mkdir()
    (gmail_dir / "manifest.yaml").write_text("""
name: gmail_reader
version: 1.0.0
description: Read emails from Gmail inbox
author: ByteBeam
category: communication
permissions:
  - network
dependencies:
  - google-api-python-client
intent_triggers:
  - email
  - inbox
  - gmail
tools:
  - name: read_inbox
    description: Read recent emails
    module: tools.gmail_reader
    function: read_inbox
""")
    
    # Create code_review skill (depends on nothing)
    code_dir = tmp_path / "code_review"
    code_dir.mkdir()
    (code_dir / "manifest.yaml").write_text("""
name: code_review
version: 1.0.0
description: Automated code review with style checks
author: Community
category: development
intent_triggers:
  - review code
  - pull request
tools:
  - name: review_pr
    description: Review a pull request
    module: tools.reviewer
    function: review_pr
""")
    
    registry = SkillRegistry(skills_dir=tmp_path)
    registry.discover_skills()
    return registry


# --- Discovery Tests ---

def test_discover_skills_finds_valid_skills(sample_registry):
    """discover_skills should find all directories containing manifest.yaml."""
    assert sample_registry.count == 2


def test_discover_skills_returns_zero_for_empty_dir(empty_registry):
    """An empty skills directory should discover zero skills."""
    count = empty_registry.discover_skills()
    assert count == 0


def test_discover_skills_skips_dirs_without_manifest(tmp_path):
    """Directories without manifest.yaml should be silently skipped."""
    (tmp_path / "not_a_skill").mkdir()
    (tmp_path / "random_file.txt").write_text("hello")
    
    registry = SkillRegistry(skills_dir=tmp_path)
    count = registry.discover_skills()
    assert count == 0


def test_discover_skills_continues_on_invalid_manifest(tmp_path):
    """A broken manifest shouldn't crash discovery of other skills."""
    # Valid skill
    valid_dir = tmp_path / "valid_skill"
    valid_dir.mkdir()
    (valid_dir / "manifest.yaml").write_text("name: valid_skill")
    
    # Broken skill (empty manifest)
    broken_dir = tmp_path / "broken_skill"
    broken_dir.mkdir()
    (broken_dir / "manifest.yaml").write_text("")
    
    registry = SkillRegistry(skills_dir=tmp_path)
    count = registry.discover_skills()
    assert count == 1  # only the valid one


# --- Lookup Tests ---

def test_get_skill_returns_manifest_by_name(sample_registry):
    """get_skill should return the correct manifest for a registered skill."""
    manifest = sample_registry.get_skill("gmail_reader")
    assert manifest is not None
    assert manifest.name == "gmail_reader"
    assert manifest.category == "communication"


def test_get_skill_returns_none_for_unknown(sample_registry):
    """get_skill should return None for a skill that doesn't exist."""
    assert sample_registry.get_skill("nonexistent") is None


def test_list_skills_returns_all_registered(sample_registry):
    """list_skills should return all registered manifests."""
    skills = sample_registry.list_skills()
    names = [s.name for s in skills]
    assert "gmail_reader" in names
    assert "code_review" in names


def test_list_by_category_filters_correctly(sample_registry):
    """list_by_category should only return skills matching the category."""
    comm_skills = sample_registry.list_by_category("communication")
    assert len(comm_skills) == 1
    assert comm_skills[0].name == "gmail_reader"


# --- Search Tests ---

def test_search_matches_name(sample_registry):
    """Search should match against skill name."""
    results = sample_registry.search_skills("gmail")
    assert len(results) == 1
    assert results[0].name == "gmail_reader"


def test_search_matches_description(sample_registry):
    """Search should match against skill description."""
    results = sample_registry.search_skills("code review")
    assert len(results) == 1
    assert results[0].name == "code_review"


def test_search_matches_intent_triggers(sample_registry):
    """Search should match against intent triggers."""
    results = sample_registry.search_skills("inbox")
    assert len(results) == 1
    assert results[0].name == "gmail_reader"


def test_search_is_case_insensitive(sample_registry):
    """Search should be case-insensitive."""
    results = sample_registry.search_skills("GMAIL")
    assert len(results) == 1


def test_search_returns_empty_for_no_match(sample_registry):
    """Search should return empty list when nothing matches."""
    results = sample_registry.search_skills("blockchain")
    assert results == []


# --- Unregister Tests ---

def test_unregister_removes_skill(sample_registry):
    """unregister_skill should remove the skill from the registry."""
    assert sample_registry.unregister_skill("gmail_reader") is True
    assert sample_registry.get_skill("gmail_reader") is None
    assert sample_registry.count == 1


def test_unregister_returns_false_for_unknown(sample_registry):
    """unregister_skill should return False for a skill that doesn't exist."""
    assert sample_registry.unregister_skill("nonexistent") is False


# --- Dependency Tests ---

def test_get_dependents_finds_reverse_dependencies(tmp_path):
    """get_dependents should find skills that depend on the given skill."""
    # Create base skill
    base_dir = tmp_path / "gmail_reader"
    base_dir.mkdir()
    (base_dir / "manifest.yaml").write_text("name: gmail_reader")
    
    # Create skill that depends on gmail_reader
    smart_dir = tmp_path / "smart_email"
    smart_dir.mkdir()
    (smart_dir / "manifest.yaml").write_text("""
name: smart_email
skill_dependencies:
  - gmail_reader
""")
    
    registry = SkillRegistry(skills_dir=tmp_path)
    registry.discover_skills()
    
    dependents = registry.get_dependents("gmail_reader")
    assert "smart_email" in dependents


def test_get_dependents_returns_empty_when_no_dependents(sample_registry):
    """A skill with no dependents should return an empty list."""
    dependents = sample_registry.get_dependents("gmail_reader")
    assert dependents == []


def test_check_dependencies_finds_missing_deps(sample_registry):
    """check_dependencies should list skill_dependencies not in the registry."""
    manifest = SkillManifest(
        name="smart_email",
        skill_dependencies=["gmail_reader", "slack_notifier"]
    )
    missing = sample_registry.check_dependencies(manifest)
    assert "slack_notifier" in missing
    assert "gmail_reader" not in missing  # gmail_reader IS in the registry


def test_check_dependencies_returns_empty_when_all_satisfied(sample_registry):
    """All dependencies present should return an empty list."""
    manifest = SkillManifest(
        name="email_bundle",
        skill_dependencies=["gmail_reader"]
    )
    missing = sample_registry.check_dependencies(manifest)
    assert missing == []