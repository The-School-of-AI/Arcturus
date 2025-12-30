import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def debug_api():
    print("🔍 -- Debugging API Response --")
    
    # 1. Check Runs List
    try:
        res = requests.get(f"{BASE_URL}/runs")
        runs = res.json()
        print(f"✅ /runs returned {len(runs)} runs.")
        for r in runs[:3]:
            print(f"   ID: {r['id']} | Query: {r['query']} | Created: {r['created_at']}")
    except Exception as e:
        print(f"❌ Failed to fetch /runs: {e}")
        return

    # 2. Check Graph Layout
    if not runs:
        print("⚠️ No runs to check.")
        return

    run_id = runs[0]['id']
    print(f"\nmagnifying glass -- Checking Graph for Run: {run_id} --")
    try:
        res = requests.get(f"{BASE_URL}/runs/{run_id}")
        data = res.json()
        nodes = data['graph']['nodes']
        
        zero_pos_count = 0
        for n in nodes:
            pos = n.get('position', {})
            x = pos.get('x', 0)
            y = pos.get('y', 0)
            print(f"   Node {n['id']}: x={x}, y={y}, type={n['type']}")
            if x == 0 and y == 0:
                zero_pos_count += 1
                
        if zero_pos_count == len(nodes) and len(nodes) > 0:
            print("❌ ALL NODES ARE AT (0,0)! Layout fix NOT working.")
        else:
            print("✅ Nodes have overlapping positions? No, coordinates look distributed.")
            
    except Exception as e:
        print(f"❌ Failed to fetch graph: {e}")

if __name__ == "__main__":
    debug_api()
