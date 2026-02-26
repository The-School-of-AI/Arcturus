import requests
import json
import time

API_BASE = "http://localhost:8000/api"

def test_multi_canvas_sync():
    print("[START] Starting Multi-Canvas Synchronization Test\n")

    # 1. Fetch Surfaces
    print("1. Fetching available surfaces...")
    try:
        r = requests.get(f"{API_BASE}/canvas/surfaces")
        r.raise_for_status()
        surfaces = r.json()
        print(f"   Found {len(surfaces)} surfaces: {[s['id'] for s in surfaces]}\n")
    except Exception as e:
        print(f"[FAIL] Failed to fetch surfaces: {e}")
        return

    test_component = {
        "id": "diagnostic_sync_marker",
        "component": "DiagnosticWidget",
        "props": {
            "test_run_id": f"sync_{int(time.time())}",
            "marker_color": "#FFD700"
        },
        "position": {"x": 10, "y": 10},
        "size": {"width": 100, "height": 50}
    }

    # 2. Push test component to all surfaces
    print("2. Pushing diagnostic marker to all surfaces...")
    for surface in surfaces:
        surface_id = surface['id']
        print(f"   -> Pushing to {surface_id}...")
        try:
            r = requests.post(
                f"{API_BASE}/canvas/test-update/{surface_id}",
                json={"components": [test_component]}
            )
            r.raise_for_status()
        except Exception as e:
            print(f"   [FAIL] Failed to push to {surface_id}: {e}")

    # 3. Verify state for each surface
    print("\n3. Verifying state consistency...")
    time.sleep(1) # Wait for processing
    
    all_ok = True
    for surface in surfaces:
        surface_id = surface['id']
        try:
            r = requests.get(f"{API_BASE}/canvas/state/{surface_id}")
            r.raise_for_status()
            state = r.json()
            components = state.get('components', [])
            
            # Check if marker exists
            marker = next((c for c in components if c['id'] == "diagnostic_sync_marker"), None)
            if marker:
                print(f"   [PASS] Surface {surface_id}: Marker found")
            else:
                print(f"   [FAIL] Surface {surface_id}: Marker MISSING")
                all_ok = False
        except Exception as e:
            print(f"   [FAIL] Failed to verify {surface_id}: {e}")
            all_ok = False

    # 4. Cleanup (Remove marker)
    print("\n4. Cleaning up diagnostic markers...")
    for surface in surfaces:
        surface_id = surface['id']
        try:
            # We "push" an update without the marker or with a deletion flag if supported
            # For this simple test, we just update the surface state to remove it
            r = requests.get(f"{API_BASE}/canvas/state/{surface_id}")
            state = r.json()
            new_components = [c for c in state.get('components', []) if c['id'] != "diagnostic_sync_marker"]
            
            requests.post(
                f"{API_BASE}/canvas/test-update/{surface_id}",
                json={"components": new_components}
            )
            print(f"   [PASS] Cleaned {surface_id}")
        except:
            pass

    if all_ok:
        print("\n[OK] ALL TESTS PASSED: Multi-canvas synchronization is healthy.")
    else:
        print("\n[WARN] SOME TESTS FAILED: Please check individual surface logs.")

if __name__ == "__main__":
    test_multi_canvas_sync()
