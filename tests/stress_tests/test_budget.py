import pytest
from core.loop import AgentLoop4
from .conftest import require_stress_opt_in


pytestmark = [pytest.mark.stress]


def test_budget_respect():
    require_stress_opt_in()

    loop = AgentLoop4(multi_mcp=None)
    assert isinstance(loop.max_steps, int)
    assert loop.max_steps > 0

    # Force max_steps to a small number and ensure override sticks.
    loop.max_steps = 3
    assert loop.max_steps == 3

if __name__ == "__main__":
    test_budget_respect()
