"""Acceptance scaffold for P02 (p02_oracle).

Replace these contract tests with feature-level assertions as implementation matures.
"""

from pathlib import Path

PROJECT_ID = "P02"
PROJECT_KEY = "p02_oracle"
CI_CHECK = "p02-oracle-research"
CHARTER = Path("CAPSTONE/project_charters/P02_oracle_ai_powered_search_research_engine.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P02_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p02_oracle.sh")
THIS_FILE = Path("tests/acceptance/p02_oracle/test_citations_back_all_claims.py")


def _charter_text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def test_01_charter_exists() -> None:
    assert CHARTER.exists(), "Missing charter: " + str(CHARTER)


def test_02_expanded_gate_contract_present() -> None:
    assert "Expanded Mandatory Test Gate Contract (10 Hard Conditions)" in _charter_text()


def test_03_acceptance_path_declared_in_charter() -> None:
    assert THIS_FILE.as_posix() in _charter_text()


def test_04_demo_script_exists() -> None:
    assert DEMO_SCRIPT.exists(), "Missing demo script: " + str(DEMO_SCRIPT)


def test_05_demo_script_is_executable() -> None:
    assert DEMO_SCRIPT.stat().st_mode & 0o111, "Demo script not executable: " + str(DEMO_SCRIPT)


def test_06_delivery_readme_exists() -> None:
    assert DELIVERY_README.exists(), "Missing delivery README: " + str(DELIVERY_README)


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
        assert section in text, "Missing section " + section + " in " + str(DELIVERY_README)


def test_08_ci_check_declared_in_charter() -> None:
    assert CI_CHECK in _charter_text()
