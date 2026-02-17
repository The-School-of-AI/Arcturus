import os
import pytest


def require_stress_opt_in() -> None:
    if os.getenv("RUN_STRESS_TESTS") != "1":
        pytest.skip("Set RUN_STRESS_TESTS=1 to run stress tests")


def require_integration_opt_in() -> None:
    if os.getenv("RUN_STRESS_INTEGRATION") != "1":
        pytest.skip("Set RUN_STRESS_INTEGRATION=1 to run stress integration tests")
