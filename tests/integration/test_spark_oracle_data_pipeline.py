"""Integration scaffold for P03 (p03_spark).

These tests enforce contract-level integration gates across repo structure and CI wiring.
"""

from pathlib import Path

PROJECT_ID = "P03"
PROJECT_KEY = "p03_spark"
CI_CHECK = "p03-spark-pages"
CHARTER = Path("CAPSTONE/project_charters/P03_spark_synthesized_content_pages_sparkpages.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p03_spark/test_structured_page_not_text_wall.py")
INTEGRATION_FILE = Path("tests/integration/test_spark_oracle_data_pipeline.py")
WORKFLOW_FILE = Path(".github/workflows/project-gates.yml")
BASELINE_SCRIPT = Path("scripts/test_all.sh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_01_integration_file_is_declared_in_charter() -> None:
    assert INTEGRATION_FILE.as_posix() in _read(CHARTER)


def test_02_acceptance_and_integration_files_exist() -> None:
    assert ACCEPTANCE_FILE.exists(), "Missing acceptance file: " + str(ACCEPTANCE_FILE)
    assert INTEGRATION_FILE.exists(), "Missing integration file: " + str(INTEGRATION_FILE)


def test_03_baseline_script_exists_and_is_executable() -> None:
    assert BASELINE_SCRIPT.exists(), "Missing baseline script scripts/test_all.sh"
    assert BASELINE_SCRIPT.stat().st_mode & 0o111, "scripts/test_all.sh must be executable"


def test_04_project_ci_check_is_wired_in_workflow() -> None:
    assert WORKFLOW_FILE.exists(), "Missing workflow .github/workflows/project-gates.yml"
    assert CI_CHECK in _read(WORKFLOW_FILE), "CI check not found in workflow: " + CI_CHECK


def test_05_charter_requires_baseline_regression() -> None:
    assert "scripts/test_all.sh quick" in _read(CHARTER)
