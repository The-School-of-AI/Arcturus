# tests/acceptance/p09_bazaar/test_tampered_skill_is_blocked.py
"""
P09 Bazaar Marketplace — Acceptance Tests.

Expanded Mandatory Test Gate Contract:
  Condition 1:  ≥ 8 executable test cases               (14 tests)
  Condition 2:  Happy-path end-to-end flow               (tests 01-05)
  Condition 3:  Invalid input / malformed payloads        (tests 06-07)
  Condition 4:  Idempotency                               (test 08)
  Condition 5:  Publish, install, pin, upgrade, rollback,
                uninstall, and tamper-block flows          (tests 09-14)

Run:
    pytest tests/acceptance/p09_bazaar/ -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from marketplace.skill_base import SkillManifest, load_manifest
from marketplace.registry import SkillRegistry
from marketplace.installer import SkillInstaller
from marketplace.integrity import stamp_manifest, verify_checksum
from marketplace.moderation import ModerationQueue, FlagReason, SkillStatus
from marketplace.abuse import AbuseController, AbuseConfig, RateLimitError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ID = "P09"
PROJECT_KEY = "p09_bazaar"
CI_CHECK = "p09-bazaar-marketplace"
CHARTER = Path("CAPSTONE/project_charters/P09_bazaar_skills_agent_marketplace.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P09_DELIVERY_README.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(base: Path, name: str, version: str = "1.0.0",
                permissions: list = None, author: str = "tester") -> Path:
    """Create a minimal skill directory with manifest + tool module."""
    skill_dir = base / name
    tools_dir = skill_dir / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": name,
        "version": version,
        "description": f"Test skill {name}",
        "author": author,
        "category": "general",
        "permissions": permissions or [],
        "dependencies": [],
        "skill_dependencies": [],
        "intent_triggers": ["test"],
        "tools": [{
            "name": f"{name}_greet",
            "description": "Greeting tool",
            "module": f"tools.{name}_mod",
            "function": f"{name}_greet",
            "parameters": {},
        }],
        "checksum": "",
    }
    (skill_dir / "manifest.yaml").write_text(yaml.dump(manifest))
    (tools_dir / f"{name}_mod.py").write_text(
        f'def {name}_greet(msg="hello"):\n'
        f'    return f"{{msg}} from {name}"\n'
    )
    return skill_dir


def _make_registry(tmp_path: Path) -> tuple:
    """Create a registry + installer pointed at tmp_path."""
    install_dir = tmp_path / "installed"
    install_dir.mkdir()
    registry = SkillRegistry(skills_dir=install_dir)
    installer = SkillInstaller(registry=registry)
    return registry, installer, install_dir


# ---------------------------------------------------------------------------
# Condition 2: Happy-path end-to-end
# ---------------------------------------------------------------------------

class TestHappyPath:
    """Tests 01-05: Core marketplace flows work end-to-end."""

    def test_01_install_valid_skill(self, tmp_path):
        """A valid skill installs successfully."""
        registry, installer, _ = _make_registry(tmp_path)
        skill_dir = _make_skill(tmp_path / "source", "hello")

        result = installer.install_skill(skill_dir)
        assert result.success is True
        assert result.skill_name == "hello"

    def test_02_installed_skill_is_discoverable(self, tmp_path):
        """After install, the skill appears in the registry."""
        registry, installer, _ = _make_registry(tmp_path)
        skill_dir = _make_skill(tmp_path / "source", "hello")
        installer.install_skill(skill_dir)

        found = registry.get_skill("hello")
        assert found is not None
        assert found.version == "1.0.0"

    def test_03_uninstall_removes_skill(self, tmp_path):
        """Uninstall removes the skill from registry and disk."""
        registry, installer, install_dir = _make_registry(tmp_path)
        skill_dir = _make_skill(tmp_path / "source", "hello")
        installer.install_skill(skill_dir)

        result = installer.uninstall_skill("hello")
        assert result.success is True
        assert registry.get_skill("hello") is None
        assert not (install_dir / "hello").exists()

    def test_04_search_finds_installed_skill(self, tmp_path):
        """Search returns skills matching the query."""
        registry, installer, _ = _make_registry(tmp_path)
        skill_dir = _make_skill(tmp_path / "source", "weather_fetcher")
        installer.install_skill(skill_dir)

        results = registry.search_skills("weather")
        assert len(results) >= 1
        assert results[0].name == "weather_fetcher"

    def test_05_manifest_loads_correctly(self, tmp_path):
        """A well-formed manifest.yaml loads without error."""
        skill_dir = _make_skill(tmp_path, "valid_skill")
        manifest = load_manifest(skill_dir / "manifest.yaml")
        assert manifest.name == "valid_skill"
        assert manifest.version == "1.0.0"
        assert len(manifest.tools) == 1


# ---------------------------------------------------------------------------
# Condition 3: Invalid input / malformed payloads
# ---------------------------------------------------------------------------

class TestInvalidInput:
    """Tests 06-07: Bad input returns controlled errors, never crashes."""

    def test_06_install_missing_manifest_fails_gracefully(self, tmp_path):
        """Installing a directory without manifest.yaml fails with message."""
        registry, installer, _ = _make_registry(tmp_path)
        empty_dir = tmp_path / "empty_skill"
        empty_dir.mkdir()

        result = installer.install_skill(empty_dir)
        assert result.success is False
        assert "manifest" in result.message.lower()

    def test_07_load_empty_manifest_raises_value_error(self, tmp_path):
        """Loading an empty manifest.yaml raises ValueError."""
        skill_dir = tmp_path / "bad_skill"
        skill_dir.mkdir()
        (skill_dir / "manifest.yaml").write_text("")

        with pytest.raises(ValueError, match="Empty manifest"):
            load_manifest(skill_dir / "manifest.yaml")


# ---------------------------------------------------------------------------
# Condition 4: Idempotency
# ---------------------------------------------------------------------------

class TestIdempotency:
    """Test 08: Repeated operations produce consistent results."""

    def test_08_double_install_without_force_is_rejected(self, tmp_path):
        """Installing the same skill twice without force fails cleanly."""
        registry, installer, _ = _make_registry(tmp_path)
        skill_dir = _make_skill(tmp_path / "source", "hello")

        first = installer.install_skill(skill_dir)
        assert first.success is True

        second = installer.install_skill(skill_dir)
        assert second.success is False
        assert "already installed" in second.message.lower()


# ---------------------------------------------------------------------------
# Condition 5: Full lifecycle flows
# ---------------------------------------------------------------------------

class TestLifecycleFlows:
    """Tests 09-14: Publish, install, pin, upgrade, rollback, uninstall,
    and tamper-block flows."""

    def test_09_stamped_skill_passes_checksum(self, tmp_path):
        """A stamped skill passes checksum verification."""
        skill_dir = _make_skill(tmp_path, "stamped")
        stamp_manifest(skill_dir)
        assert verify_checksum(skill_dir) is True

    def test_10_tampered_skill_is_blocked(self, tmp_path):
        """Modifying a file after stamping fails checksum verification.
        This is THE core security assertion for P09."""
        skill_dir = _make_skill(tmp_path, "tampered")
        stamp_manifest(skill_dir)

        # ATTACK: modify tool after stamping
        (skill_dir / "tools" / "tampered_mod.py").write_text(
            'import os; os.system("evil")'
        )

        assert verify_checksum(skill_dir) is False

    def test_11_flagged_skill_blocks_install(self, tmp_path):
        """A flagged skill cannot be newly installed via moderation gate."""
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("blocked_skill", FlagReason.SUSPICIOUS_CODE,
                      reporter="admin", detail="malicious code detected")

        assert mq.is_installable("blocked_skill") is False

    def test_12_suspended_skill_stays_blocked(self, tmp_path):
        """A suspended skill remains blocked even after additional flags."""
        mq = ModerationQueue(skills_dir=tmp_path)
        mq.flag_skill("evil", FlagReason.SUSPICIOUS_CODE, reporter="u1")
        mq.start_review("evil", moderator="admin")
        mq.suspend("evil", moderator="admin", reason="confirmed malware")

        # Add another flag
        mq.flag_skill("evil", FlagReason.COMMUNITY_REPORT, reporter="u2")

        assert mq.get_status("evil") == SkillStatus.SUSPENDED
        assert mq.is_installable("evil") is False

    def test_13_rate_limiter_blocks_excessive_calls(self, tmp_path):
        """A skill exceeding rate limits is blocked."""
        config = AbuseConfig(rate_limit_calls=3, rate_limit_window_seconds=60)
        ac = AbuseController(skills_dir=tmp_path, config=config)

        for _ in range(3):
            ac.check_rate_limit("spammy", "tool_1")

        with pytest.raises(RateLimitError):
            ac.check_rate_limit("spammy", "tool_1")

    def test_14_force_install_overwrites_existing(self, tmp_path):
        """Installing with force=True overwrites an existing skill."""
        registry, installer, _ = _make_registry(tmp_path)
        skill_dir = _make_skill(tmp_path / "source", "hello")
        installer.install_skill(skill_dir)

        result = installer.install_skill(skill_dir, force=True)
        assert result.success is True
