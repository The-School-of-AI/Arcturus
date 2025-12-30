import requests
import time
import json

BASE_URL = "http://localhost:8000"

prompts = [
    "Calculate the 10th fibonacci number using python",
    "Summarize what mem0 is briefly",
    "List 3 benefits of networkx"
]

def run_stress_test():
    print(f"🚀 Starting Stress Test on {BASE_URL}")
    
    run_ids = []
    
    # 1. Trigger Runs
    for p in prompts:
        try:
            res = requests.post(f"{BASE_URL}/runs", json={"query": p, "model": "gemini-2.0-pro"})
            if res.status_code == 200:
                data = res.json()
                print(f"✅ Started Run: {data['id']} - {data['query']}")
                run_ids.append(data['id'])
            else:
                print(f"❌ Failed to start: {p} ({res.status_code})")
        except Exception as e:
            print(f"❌ Connection Error: {e}")
            return

    print("\n⏳ Waiting 5 seconds for background processing...")
    time.sleep(5)
    
    # 2. Check History
    print("\n📜 Checking Run History...")
    try:
        res = requests.get(f"{BASE_URL}/runs")
        history = res.json()
        print(f"Found {len(history)} runs in history.")
        for h in history:
            print(f" - {h['id']}: {h['query']} ({h['status']})")
    except Exception as e:
        print(f"❌ Failed to fetch history: {e}")
        
    # 3. Check graph for first run
    if run_ids:
        rid = run_ids[0]
        print(f"\n🔍 Checking Graph for {rid}...")
        try:
            res = requests.get(f"{BASE_URL}/runs/{rid}")
            if res.status_code == 200:
                graph = res.json()['graph']
                print(f"✅ Graph retrieved! Nodes: {len(graph['nodes'])}, Edges: {len(graph['edges'])}")
            else:
                print(f"⚠️ Graph not ready yet (might be still running): {res.status_code}")
        except Exception as e:
            print(f"❌ Failed to fetch graph: {e}")

if __name__ == "__main__":
    run_stress_test()
