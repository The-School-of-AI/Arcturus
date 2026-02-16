
# Analysis & Answers to User Questions

## Core Architecture & Agents

**1. How different is our AgentLoop compared to Nanobot?**
- **Architecture**: `AgentLoop4` in `core/loop.py` is a **Graph-based** orchestrator (using `networkx`) similar to LangGraph. It explicitly models the execution as a Directed Acyclic Graph (DAG) of nodes (agents) and edges (dependencies).
- **Execution**: It supports parallel execution of non-dependent nodes and dynamic graph expansion (Planner can add new nodes mid-execution).
- **Comparison**: While Nanobot is often a linear or state-machine based agent, your `AgentLoop` is a full **DAG Planner-Executor**. It is "Code as Graph".

**2. Can we inject any Agent into Agent Loop dynamically?**
- **Dynamic Graph**: Yes, the *structure* of the execution (the graph) is dynamic. The `PlannerAgent` can add new nodes and edges at runtime.
- **Static Registry**: No, the *types* of agents (`PlannerAgent`, `CoderAgent`, etc.) are currently **hardcoded** in `config/agent_config.yaml`. The `AgentRunner` loads this file on initialization. You cannot currently "inject" a brand new Agent Class (e.g., `DiscordBotAgent`) without editing `agent_config.yaml` and restarting.

**3. Adding MCP server from frontend isn't stable, broken**
- **Findings**: The backend logic `routers/mcp.py` dynamically scans python files in `mcp_servers/` using regex. This is fragile. Use of `importlib` or a proper plugin system would be more robust. The failure likely happens during the "restart/reload" phase of `MultiMCP`, which is complex to handle without dropping active connections.

## App Engine & UI

**4. hydrate-app only fetches current data, cannot create new UI elements**
- **Confirmed**: `routers/apps.py` (line ~400) prompts the LLM to "Update the data" in `ui.json` but typically preserves the structure.
- **Limitation**: The `AppHydrationPrompt.md` (likely) restricts the model to only updating values. It lacks the freedom to "Redesign the Layout" based on new data.

**5. Generate from report usually only creates large TEXT blocks.**
- **Analysis**: The `ReportToAppPrompt.md` *explicitly* asks for "Less text, more charts". However, extracting structured data (for charts) from unstructured text is hard for smaller models.
- **Cause**: If the LLM cannot confidently extract a table/series, it falls back to the safe option: a large `markdown` card containing the text.
- **Fix**: Needs a "Data Extraction" step *before* "UI Generation".

## Skills & Agents

**6. Agents vs Skills redundancy?**
- **Architecture**: In `base_agent.py`, an "Agent" is just a **Configuration** (Prompt + Model + Set of Skills).
- **Usage**: Agents *do* use skills. The `AgentRunner` injects enabled skills into the prompt (line 120 of `base_agent.py`).
- **Redundancy**: It is not redundant, but the abstraction is thin. You could indeed convert "Agents" into just "Personas" that select "Skills" dynamically, rather than hardcoding "CoderAgent has git_commit skill".

**17. Is Skill ACTUALLY being used?**
- **Yes**. `agents/base_agent.py` imports `get_skill_manager` and calls `skill.on_run_start(full_prompt)`.
- **Mechanism**: Skills are passive *modifiers* or *tool providers*. They inject prompt instructions or context. They are not independent actors.

## Memory & Personalization

**7. Cortex-R: Placeholder or active?**
- **Placeholder**. `Cortex-R` is defined in `profiles.yaml`, but my scan of `base_agent.py` shows it only injects **Preferences**, not the full Persona/Description of Cortex-R. The "Agent Name" in the loop is derived from the DAG node (e.g., "PlannerAgent"), not the global profile name.

**8. Episodic Memory Usage?**
- **Recording**: **Yes**. `core/loop.py` (line 601) saves every run to `EpisodicMemory`.
- **Recall**: **No/Weak**. I found no evidence of *searching* Episodic Memory to inform *future* plans during the Planning Phase (except implicitly via `semantic` search of summaries). The raw graph data is saved but rarely reloaded for *planning*.

**9. Semantic Memory Usage?**
- **Yes**. `routers/runs.py` (lines 61-75) actively searches `remme_store` for relevant past memories using the run's `query`.
- **Injection**: It injects these memories ("PREVIOUS MEMORIES ABOUT USER") into the `memory_context` of the `AgentLoop`.

**10. User Profiling Usage?**
- **Passive**. It runs in the background (`background_smart_scan` in `routers/remme.py`) to build the profile.
- **Active**: The "Psychological Profile" is *not* clearly injected into every agent run. Only "Compact Preferences" are injected (`base_agent.py` line 95). The full profile seems to be for the User's viewing pleasure in the UI (`/profile` page).

**11. Preference Hub Usage?**
- **Yes**. `base_agent.py` calls `get_compact_policy(scope)` to inject specific formatting/behavior rules into the prompt.

## RAG & Tools

**12. RAG Content Usage?**
- **Yes**. `RetrieverAgent` is configured with the `rag` MCP server. It calls `rag.search` tools.
- **Skill**: It could be wrapped as a "Research Skill" to be added to *any* agent, not just Retriever.

**13/14. Previews (Scattered vs Unified)?**
- **Scattered**.
    - `routers/rag.py` has `document_preview`.
    - `ide_agent.py` has no preview logic (it just reads files).
    - `mcp_servers/browser` returns text.
    - There is no central "Preview Service" that creates a consistent UI view for PDF vs Markdown vs Webpage.

**15. BrowserMCP vs App Browser?**
- **Separate**. `mcp_servers/server_browser.py` uses `browser-use` (Playwright/Selenium) or `httpx`.
- **App Browser**: The "Talk to Browser" feature likely sends a URL to this backend service. It does *not* control the user's actual Chrome window via an extension.

**16. Code Execution Sandbox**
- **Multiple**.
    - `mcp_servers/server_sandbox.py`: Likely for `CoderAgent`.
    - `ide_agent.py`: Has its own "shell execution" prompt instructions but relies on the backend environment (not a true isolated sandbox).
    - `core/loop.py`: Has logic for `_auto_execute_code` (line 735), implying the Loop itself can execute code directly!

**Missing Features Identified:**
- **IDE Agent**: A specialized `ide_agent.py` router exists for "Chat with Codebase" using Ollama directly.
- **App Maker**: `routers/apps.py` handles creation but has legacy limitations.
- **RAG/PDF Chat**: Implemented via `rag` router but strictly backend-search based.
