"""Integration scaffold for P15 (p15_gateway).

These tests enforce contract-level integration gates across repo structure and CI wiring.
"""

from pathlib import Path

PROJECT_ID = "P15"
PROJECT_KEY = "p15_gateway"
CI_CHECK = "p15-gateway-api"
CHARTER = Path("CAPSTONE/project_charters/P15_gateway_api_platform_integration_hub.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p15_gateway/test_public_api_webhook_cron_flow.py")
INTEGRATION_FILE = Path("tests/integration/test_gateway_to_oracle_spark_forge.py")
WORKFLOW_FILE = Path(".github/workflows/project-gates.yml")
BASELINE_SCRIPT = Path("scripts/test_all.sh")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_01_integration_file_is_declared_in_charter() -> None:
    assert f"Integration: " in _read(CHARTER)


def test_02_acceptance_and_integration_files_exist() -> None:
    assert ACCEPTANCE_FILE.exists(), f"Missing acceptance file: {ACCEPTANCE_FILE}"
    assert INTEGRATION_FILE.exists(), f"Missing integration file: {INTEGRATION_FILE}"


def test_03_baseline_script_exists_and_is_executable() -> None:
    assert BASELINE_SCRIPT.exists(), "Missing baseline script scripts/test_all.sh"
    assert BASELINE_SCRIPT.stat().st_mode & 0o111, "scripts/test_all.sh must be executable"


def test_04_project_ci_check_is_wired_in_workflow() -> None:
    assert WORKFLOW_FILE.exists(), "Missing workflow .github/workflows/project-gates.yml"
    assert CI_CHECK in _read(WORKFLOW_FILE), f"CI check {CI_CHECK} not found in workflow"


def test_05_charter_requires_baseline_regression() -> None:
    assert "scripts/test_all.sh quick" in _read(CHARTER)
