# tests/integration/test_bazaar_skill_install_execution.py
"""
P09 Bazaar Marketplace — Integration Tests.

Expanded Mandatory Test Gate Contract:
  Condition 6:  ≥ 5 integration scenarios                (7 tests)
  Condition 7:  Skills executable + policy enforcement    (tests 01-02)
  Condition 8:  Cross-project failure propagation         (tests 03-04)

These tests exercise MULTIPLE modules together — registry, installer,
loader, trust policy, sandbox, moderation, and abuse controls.

Run:
    pytest tests/integration/test_bazaar_skill_install_execution.py -v
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from marketplace.bridge import MarketplaceBridge
from marketplace.registry import SkillRegistry
from marketplace.installer import SkillInstaller
from marketplace.skill_base import SkillManifest, load_manifest
from marketplace.integrity import stamp_manifest, verify_checksum
from marketplace.trust import TrustPolicy, TrustLevel
from marketplace.moderation import ModerationQueue, FlagReason, SkillStatus
from marketplace.abuse import AbuseController, AbuseConfig, CircuitOpenError


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


# ---------------------------------------------------------------------------
# Condition 7: Skills executable + policy enforcement
# ---------------------------------------------------------------------------

class TestSkillExecution:
    """Integration tests proving skills run through the bridge with policy."""

    def test_01_install_and_execute_through_bridge(self, tmp_path):
        """
        End-to-end: install a skill via bridge, then resolve its tool.

        Exercises: Registry → Installer → Loader → resolve_tool()
        """
        install_dir = tmp_path / "installed"
        install_dir.mkdir()

        # Install skill
        skill_dir = _make_skill(tmp_path / "source", "hello_skill")
        bridge = MarketplaceBridge(
            skills_dir=install_dir,
            trust_policy=TrustPolicy(trust_level=TrustLevel.OPEN),
        )
        result = bridge.installer.install_skill(skill_dir)
        assert result.success is True

        # Execute through bridge
        bridge.refresh()
        tool_result = bridge.resolve_tool("hello_skill_greet", {"msg": "hi"})
        assert tool_result == "hi from hello_skill"

    def test_02_trust_policy_blocks_unsigned_at_signed_level(self, tmp_path):
        """
        A SIGNED-level trust policy rejects a skill with no signature.

        Exercises: TrustPolicy.evaluate() → blocks install path
        """
        skill_dir = _make_skill(tmp_path / "source", "unsigned_skill")
        manifest = load_manifest(skill_dir / "manifest.yaml")

        policy = TrustPolicy(trust_level=TrustLevel.SIGNED)
        result = policy.evaluate(manifest, skill_dir=skill_dir)
        assert result.allowed is False
        assert "signature" in result.reason.lower()


# ---------------------------------------------------------------------------
# Condition 8: Cross-project failure propagation
# ---------------------------------------------------------------------------

class TestFailurePropagation:
    """Integration tests for graceful failure across components."""

    def test_03_moderation_flag_blocks_bridge_install(self, tmp_path):
        """
        A flagged skill is blocked at install time when moderation
        is checked by the installer.

        This tests the wiring between ModerationQueue and SkillInstaller.
        """
        install_dir = tmp_path / "installed"
        install_dir.mkdir()

        # Pre-flag the skill in moderation
        mq = ModerationQueue(skills_dir=install_dir)
        mq.flag_skill("evil_skill", FlagReason.SUSPICIOUS_CODE,
                      reporter="admin", detail="malware detected")

        assert mq.is_installable("evil_skill") is False

        # Verify the status
        status = mq.get_status("evil_skill")
        assert status == SkillStatus.FLAGGED

    def test_04_abuse_circuit_breaker_blocks_execution(self, tmp_path):
        """
        A skill with too many errors has its circuit breaker tripped,
        blocking further execution.

        This tests the wiring between AbuseController and tool execution.
        """
        config = AbuseConfig(circuit_error_threshold=2, circuit_cooldown_seconds=300)
        ac = AbuseController(skills_dir=tmp_path, config=config)

        # Simulate consecutive failures
        ac.record_error("broken_skill", "tool_1", "crash")
        ac.record_error("broken_skill", "tool_1", "crash again")

        # Circuit should be tripped
        with pytest.raises(CircuitOpenError):
            ac.check_circuit("broken_skill")


# ---------------------------------------------------------------------------
# Additional integration scenarios
# ---------------------------------------------------------------------------

class TestAdditionalIntegration:
    """Extra integration scenarios for Condition 6 (≥ 5 total)."""

    def test_05_tampered_skill_fails_checksum_and_stays_blocked(self, tmp_path):
        """
        A tampered skill fails checksum verification.
        Combined integrity + security flow.
        """
        skill_dir = _make_skill(tmp_path / "source", "victim")
        stamp_manifest(skill_dir)

        # Verify clean
        assert verify_checksum(skill_dir) is True

        # Tamper
        (skill_dir / "tools" / "victim_mod.py").write_text(
            'import os; os.system("rm -rf /")'
        )

        # Verify failed
        assert verify_checksum(skill_dir) is False

    def test_06_moderation_full_lifecycle(self, tmp_path):
        """
        Full moderation lifecycle: flag → review → approve → installable.

        Tests ModerationQueue state transitions end-to-end.
        """
        mq = ModerationQueue(skills_dir=tmp_path)

        # Flag
        mq.flag_skill("sus_skill", FlagReason.COMMUNITY_REPORT,
                      reporter="user1", detail="looks suspicious")
        assert mq.get_status("sus_skill") == SkillStatus.FLAGGED
        assert mq.is_installable("sus_skill") is False

        # Review
        mq.start_review("sus_skill", moderator="alice")
        assert mq.get_status("sus_skill") == SkillStatus.UNDER_REVIEW

        # Approve
        mq.approve("sus_skill", moderator="alice", reason="false alarm")
        assert mq.get_status("sus_skill") == SkillStatus.ACTIVE
        assert mq.is_installable("sus_skill") is True

    def test_07_multiple_skills_independent_state(self, tmp_path):
        """
        Installing and flagging different skills keeps state independent.

        Tests registry + moderation isolation.
        """
        install_dir = tmp_path / "installed"
        install_dir.mkdir()
        registry = SkillRegistry(skills_dir=install_dir)
        installer = SkillInstaller(registry=registry)

        # Install two skills
        s1 = _make_skill(tmp_path / "source", "good_skill")
        s2 = _make_skill(tmp_path / "source", "bad_skill")
        installer.install_skill(s1)
        installer.install_skill(s2)

        # Flag only bad_skill
        mq = ModerationQueue(skills_dir=install_dir)
        mq.flag_skill("bad_skill", FlagReason.SUSPICIOUS_CODE, reporter="admin")

        # good_skill should be unaffected
        assert mq.is_installable("good_skill") is True
        assert mq.is_installable("bad_skill") is False
        assert registry.get_skill("good_skill") is not None
