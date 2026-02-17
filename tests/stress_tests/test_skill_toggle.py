import requests
import time
import pytest
from .conftest import require_stress_opt_in, require_integration_opt_in


pytestmark = [pytest.mark.stress, pytest.mark.integration, pytest.mark.external]

def test_toggle_stress():
    require_stress_opt_in()
    require_integration_opt_in()

    url = "http://localhost:8000/api/agent/toggle_skill"
    payload = {
        "agent_name": "CoderAgent",
        "skill_name": "python_coding",
        "enabled": True
    }
    
    print("Starting Skill Toggle Stress Test (50 iterations)...")
    successes = 0
    for i in range(50):
        # Toggle
        payload["enabled"] = not payload["enabled"]
        try:
            resp = requests.post(url, json=payload, timeout=2)
            if resp.status_code == 200:
                print(f"Iteration {i+1}: Success ({'Enabled' if payload['enabled'] else 'Disabled'})")
                successes += 1
            else:
                pytest.fail(f"Iteration {i+1} failed with status {resp.status_code}: {resp.text}")
        except Exception as e:
            pytest.fail(f"Iteration {i+1}: Error - {e}")
        # Small sleep
        time.sleep(0.05)
    
    assert successes == 50
    print("✅ Stress test completed.")

if __name__ == "__main__":
    test_toggle_stress()
