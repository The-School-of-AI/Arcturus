# Oracle Project P02 Handover - Multimodal & Internal Search

Hello! I have completed the implementation of the remaining scope for the **Oracle** answer engine (Sections 2.5 and 2.6 of the charter).

This document outlines the architecture, the code we wrote, how it functions, and what needs to happen next. **All of this code is currently safely tracked on your `feature/p02-oracle-1-5` branch.**

---

## 1. What We Did
We built upon the existing Web Crawler and Deep Research iterative pipelines to give the Oracle system access to **local documents, images, datasets, and historical memories**.

Specifically, we added two new FastMCP servers and wired them into the Core Agents.

### A. Multimodal Search (`mcp_servers/server_multimodal.py`)
This server acts as the "eyes and ears" for files. It provides three tools:
- **`analyze_image(image_path, prompt)`**: 
  - *Logic*: Reads a local image file (`.png`, `.jpg`), converts it into a base64 encoded string, and sends both the specific user prompt and the encoded image to the `Gemini 2.5 Flash` model using the `langchain-google-genai` library.
  - *Use Case*: "What is written on this whiteboard picture?" or "Describe this architecture diagram."
- **`analyze_pdf_document(pdf_path, prompt)`**: 
  - *Logic*: Uses the `pymupdf4llm` package to securely and cleanly extract raw text from PDF documents. It then injects this text into a context window for Gemini to answer the user's specific prompt about the document.
  - *Use Case*: "What is the conclusion of this whitepaper?"
- **`analyze_data_file(file_path, prompt)`**: 
  - *Logic*: Uses Python's built-in `csv` and `statistics` libraries to safely parse large datasets. Instead of sending raw gigabytes to an LLM, it mathematically calculates Min, Max, Means, and counts for numeric columns, generating a "Statistical Summary" and a small 5-row "Sample". It sends those to the LLM to write a coherent answer.

### B. Internal Knowledge Search (`mcp_servers/server_internal.py`)
This server gives Oracle access to the project workspace and episodic system-memory.
- **`search_workspace_files(query, directory)`**:
  - *Logic*: Recursively walks through all text files in the project workspace (intelligently skipping binary files and `.git`/`node_modules` folders) looking for string matches. It pulls the specific line number and surrounding context lines to help agents understand code or markdown intent.
- **`search_past_conversations(query)`**:
  - *Logic*: Taps directly into the `data/user_memory.json` flat-file data store. It scans historical memory payloads and semantic tags for context matches, allowing the agent to "remember" parameters defined weeks ago.

### C. Wiring It To The Agents
Adding servers doesn't help if the agents don't know they exist.
1. **Registered the servers**: Added both servers to `mcp_servers/mcp_config.json` so the `ServerManager` boots them up globally.
2. **`RetrieverAgent` Update** (`core/skills/library/retriever/skill.py`): We updated the core instruction prompt, explicitly giving it the function signatures for the 5 new tools and giving it decision logic on *when* to use them vs normal web searches.
3. **Deep Research Update** (`core/skills/library/deep-research/skill.py`): We added a new Focus Mode constraints block. When `focus_mode: "internal"` is passed, the Deep Research pipeline forces the initial searches to use `search_workspace_files` rather than `search_web_with_text_content`.

### D. Testing (`tests/integration/test_oracle_multimodal_internal.py`)
We wrote an integration suite that tests the failure states of these new tools (ensuring they elegantly bounce bad files or missing dependencies rather than crashing the system) to fulfill the CI pipeline acceptance criteria on `P02`.

---

## 2. Testing the Implementation
Before pushing this code, we ran:
```bash
uv run pytest tests/integration/test_oracle_multimodal_internal.py
```
This verified the new internal logic. We also ensured the existing integration scopes continued working cleanly with the updated `RetrieverAgent` skill block.

## 3. Recommended Next Steps

1. **Review Code**: I have placed a copy of all the modified files in the `Oracle_Review_Code` folder so your colleague doesn't have to go hunting through the git tree. Have them review `server_multimodal.py` and `server_internal.py`.
2. **Push to GitHub**: Once reviewed, you can stage and commit these files.
   ```bash
   git add mcp_servers/server_multimodal.py mcp_servers/server_internal.py mcp_servers/mcp_config.json core/skills/library/retriever/skill.py core/skills/library/deep-research/skill.py tests/integration/test_oracle_multimodal_internal.py CAPSTONE/project_charters/P02_DELIVERY_README.md
   git commit -m "feat(oracle): integrate multimodal and internal knowledge components"
   git push origin feature/p02-oracle-1-5
   ```
3. **Pull Request**: Open a PR into `main` and let the GitHub Actions project-gates run the acceptance suite automatically.
