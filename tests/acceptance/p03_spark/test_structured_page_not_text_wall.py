"""Acceptance scaffold for P03 (p03_spark).

Replace these contract tests with feature-level assertions as implementation matures.
"""

from pathlib import Path

PROJECT_ID = "P03"
PROJECT_KEY = "p03_spark"
CI_CHECK = "p03-spark-pages"
CHARTER = Path("CAPSTONE/project_charters/P03_spark_synthesized_content_pages_sparkpages.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P03_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p03_spark.sh")
THIS_FILE = Path("tests/acceptance/p03_spark/test_structured_page_not_text_wall.py")


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
