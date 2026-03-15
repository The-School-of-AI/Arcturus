import json
import sys
import time

import requests

BASE_URL = "http://127.0.0.1:8000"

def test_location_query():
    print(f"🚀 Testing API at {BASE_URL}...")

    # 1. Start a new run
    query = "where is the user located?"
    print(f"📡 Sending query: '{query}'")
    try:
        response = requests.post(f"{BASE_URL}/runs", json={"query": query}, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to reach API: {e}")
        print("💡 Make sure 'uv run api.py' is running on port 8000.")
        return

    run_data = response.json()
    run_id = run_data["id"]
    print(f"✅ Run started! ID: {run_id}")

    # 2. Poll for completion
    max_retries = 30
    status = "starting"

    print("⏳ Polling for completion...")
    for i in range(max_retries):
        try:
            resp = requests.get(f"{BASE_URL}/runs/{run_id}", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]

            print(f"   [{i}] Status: {status}")

            if status == "completed":
                print("✅ Run Completed!")
                verify_output(data)
                return
            elif status == "failed":
                print("❌ Run Failed!")
                print(json.dumps(data, indent=2))
                return

        except Exception as e:
            print(f"   ⚠️ Polling error: {e}")

        time.sleep(3)

    print("🛑 Timeout waiting for completion.")

def verify_output(data):
    print("🔍 Verifying Output Graph...")
    graph = data.get("graph", {})
    nodes = graph.get("nodes", [])

    found_bangalore = False
    for node in nodes:
        node_data = node.get("data", {})
        output = node_data.get("output")
        if output:
            output_str = str(output).lower()
            if "bangalore" in output_str or "bengaluru" in output_str:
                print(f"✅ SUCCESS: Found location reference in node {node.get('id')}")
                found_bangalore = True
                break

    if not found_bangalore:
        print("❌ FAILURE: 'Bangalore' not found in any node output.")
        # print(json.dumps(nodes, indent=2))

if __name__ == "__main__":
    test_location_query()
