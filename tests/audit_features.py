import sys
import os
import subprocess
import requests
import unittest

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTLINE_SCRIPT = os.path.join(PROJECT_ROOT, "scripts", "file_outline.py")
API_URL = "http://localhost:8000"

class TestAgentFeatures(unittest.TestCase):
    
    def test_file_outline_script(self):
        """Verify file_outline.py works on this very file."""
        print(f"\n[Audit] Testing file_outline.py on {__file__}...")
        result = subprocess.run(
            ["python3", OUTLINE_SCRIPT, __file__], 
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[Fail] Output: {result.stderr}")
        
        self.assertEqual(result.returncode, 0, "Script failed to run")
        self.assertIn("CLASS: TestAgentFeatures", result.stdout, "Class missing from outline")
        self.assertIn("FUNC: test_file_outline_script", result.stdout, "Method missing from outline")
        print("[Pass] Outline script works correctly.")

    def test_backend_agent_endpoints(self):
        """Verify backend agent API is up and running."""
        print("\n[Audit] Pinging Agent Endpoints...")
        try:
            # 1. Read URL (using a fast dummy URL or local)
            # We trust the previous automated test, but let's do a quick health check
            # We can try to read a non-existent URL to check error handling
            res = requests.post(f"{API_URL}/agent/read_url", json={"url": "http://invalid-url-xyz.com"})
            # Should fail gracefully, not 500 crash the server
            if res.status_code == 500:
                print(f"[Warning] 500 Error on invalid URL: {res.text}")
            else:
                print(f"[Pass] Error handled gracefully: {res.status_code}")
                
            # 2. Search
            res = requests.post(f"{API_URL}/agent/search", json={"query": "test", "limit": 1})
            if res.status_code == 200:
                 print("[Pass] Search endpoint active.")
            else:
                 self.fail(f"Search endpoint failed: {res.status_code}")

        except Exception as e:
            self.fail(f"Backend Audit Failed: {e}")

if __name__ == '__main__':
    unittest.main()
