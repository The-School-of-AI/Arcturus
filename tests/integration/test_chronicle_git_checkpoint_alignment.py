"""Integration scaffold for P05 (p05_chronicle).

These tests enforce contract-level integration gates across repo structure and CI wiring.
"""

from pathlib import Path

PROJECT_ID = "P05"
PROJECT_KEY = "p05_chronicle"
CI_CHECK = "p05-chronicle-replay"
CHARTER = Path("CAPSTONE/project_charters/P05_chronicle_ai_session_tracking_reproducibility.md")
ACCEPTANCE_FILE = Path("tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py")
INTEGRATION_FILE = Path("tests/integration/test_chronicle_git_checkpoint_alignment.py")
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
