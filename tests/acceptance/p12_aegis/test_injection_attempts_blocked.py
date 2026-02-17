"""Acceptance scaffold for P12 (p12_aegis).

Replace these contract tests with feature-level assertions as implementation matures.
"""

from pathlib import Path

PROJECT_ID = "P12"
PROJECT_KEY = "p12_aegis"
CI_CHECK = "p12-aegis-safety"
CHARTER = Path("CAPSTONE/project_charters/P12_aegis_guardrails_safety_trust_layer.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P12_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p12_aegis.sh")
THIS_FILE = Path("tests/acceptance/p12_aegis/test_injection_attempts_blocked.py")


def _charter_text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def test_01_charter_exists() -> None:
    assert CHARTER.exists(), f"Missing charter: {CHARTER}"


def test_02_expanded_gate_contract_present() -> None:
    assert "Expanded Mandatory Test Gate Contract (10 Hard Conditions)" in _charter_text()


def test_03_acceptance_path_declared_in_charter() -> None:
    assert f"Acceptance: " in _charter_text()


def test_04_demo_script_exists() -> None:
    assert DEMO_SCRIPT.exists(), f"Missing demo script: {DEMO_SCRIPT}"


def test_05_demo_script_is_executable() -> None:
    assert DEMO_SCRIPT.stat().st_mode & 0o111, f"Demo script not executable: {DEMO_SCRIPT}"


def test_06_delivery_readme_exists() -> None:
    assert DELIVERY_README.exists(), f"Missing delivery README: {DELIVERY_README}"


def test_07_delivery_readme_has_required_sections() -> None:
    required = [
        "## 1. Scope Delivered",
        "## 2. Architecture Changes",
        "## 3. API And UI Changes",
        "## 4. Mandatory Test Gate Definition",
        "## 5. Test Evidence",
        "## 8. Known Gaps",
        "## 10. Demo Steps",
    ]
    text = DELIVERY_README.read_text(encoding="utf-8")
    for section in required:
        assert section in text, f"Missing section {section} in {DELIVERY_README}"


def test_08_ci_check_declared_in_charter() -> None:
    assert f"CI required check: " in _charter_text()
