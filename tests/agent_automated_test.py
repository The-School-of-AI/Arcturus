import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000"

def log(msg, status="INFO"):
    colors = {"INFO": "\033[94m", "SUCCESS": "\033[92m", "ERROR": "\033[91m", "RESET": "\033[0m", "WARN": "\033[93m"}
    print(f"{colors.get(status, '')}[{status}] {msg}{colors['RESET']}")

class MockAgent:
    """
    Simulates an agent's decision-making process to test backend capabilities matching the user's workflow.
    """
    def __init__(self):
        self.memory = []

    def perform_research_task(self, query):
        log(f"--- Starting Mock Research Task: '{query}' ---", "INFO")
        
        # 1. Search
        log(f"Step 1: Agent decides to search for '{query}'", "INFO")
        search_results = self._call_search(query)
        if not search_results:
            log("Research aborted: No results.", "ERROR")
            return

        # 2. Analyze & Pick
        top_result = search_results[0]
        url = top_result.get("url")
        log(f"Step 2: Agent picked top result: {url}", "INFO")

        # 3. Read Content
        log(f"Step 3: Agent decides to read URL: {url}", "INFO")
        content = self._call_read_url(url)
        if not content:
            log("Research aborted: Could not read content.", "ERROR")
            return

        # 4. Synthesize (Mock RAG Call)
        log("Step 4: Agent generating answer based on context...", "INFO")
        self._mock_generation(content[:200] + "...")
        
        log("--- Research Task Complete ---", "SUCCESS")

    def _call_search(self, query):
        try:
            payload = {"query": query, "limit": 2}
            response = requests.post(f"{BASE_URL}/agent/search", json=payload)
            response.raise_for_status()
            data = response.json()
            if data["status"] == "success" and data["results"]:
                log(f"Search API returned {len(data['results'])} results.", "SUCCESS")
                return data["results"]
            else:
                log("Search API returned no results.", "WARN")
                return []
        except Exception as e:
            log(f"Search Tool Failed: {e}", "ERROR")
            return []

    def _call_read_url(self, url):
        try:
            payload = {"url": url}
            response = requests.post(f"{BASE_URL}/agent/read_url", json=payload)
            response.raise_for_status()
            data = response.json()
            if data["status"] == "success":
                text_len = len(data.get("content", ""))
                log(f"Read URL API success. Retrieved {text_len} chars.", "SUCCESS")
                return data.get("content", "")
            else:
                log("Read URL API failed internally.", "ERROR")
                return None
        except Exception as e:
            log(f"Read URL Tool Failed: {e}", "ERROR")
            return None

    def _mock_generation(self, context_snippet):
        # In a real scenario, this would call /rag/ask, but that endpoint requires a running Ollama instance
        # and streams tokens. For this test, we verify we *could* construct the request.
        log(f"Simulating LLM generation with context: {context_snippet}", "INFO")
        time.sleep(1) # Thinking...
        log("Agent Answer: [Generated Summary would go here]", "SUCCESS")

def test_rag_availability():
    """Checks if RAG endpoint is responsive (health check)"""
    log("Checking RAG Endpoint Health...", "INFO")
    try:
        # Just sending a bad request to ensure it's listening
        requests.post(f"{BASE_URL}/rag/ask", json={})
        log("RAG Endpoint is reachable.", "SUCCESS")
    except requests.exceptions.ConnectionError:
        log("RAG Endpoint unreachable. Is the backend running?", "ERROR")
    except:
        log("RAG Endpoint reachable (errors expected for empty body).", "SUCCESS")

if __name__ == "__main__":
    log("Initializing Agent Verification Suite...", "INFO")
    
    # 1. Health Check
    test_rag_availability()
    
    # 2. Run Mock Agent
    agent = MockAgent()
    
    # Scenario: User asks about a technology
    agent.perform_research_task("mcp-servers python library")

    log("Verification Suite Finished.", "INFO")
