# Stronger Backbone: The Exhaustive Pre-Overhaul Plan

**Objective:** Execute a surgical hardening of Arcturus to achieve Nanobot-parity, dynamic injectability, and proven memory active usage.
**Constraint:** Every task must have a binary Pass/Fail verification criteria.
**Total Tasks:** 62

---

## Phase 1: Core Architecture & Nanobot Parity
*Goal: Move from static configuration to dynamic injection and define strict parity metrics.*

1.  **[x] Define Nanobot Parity Matrix**: Create `CAPSTONE/parity_matrix.md` listing every specific capability of Nanobot (State machine, Loop behavior, Tool usage) vs Arcturus.
    * *Verify:* Matrix exists with at least 10 specific capability rows and current status (Match/Gap).
2.  **[x] Create Agent Registry Singleton**: Implement `core/registry.py` with `register(name, agent_class)` and `get(name)`.
    * *Verify:* Unit test: Register "MockAgent", retrieve it, assert instances are identical.
3.  **[x] Decouple Config Loading**: Refactor `settings_loader.py` to parse `agent_config.yaml` and *push* to Registry, ensuring no hardcoded imports remain in `loop.py`.
    * *Verify:* Delete `import CoderAgent` from `loop.py`; app still starts.
4.  **[x] Dynamic Agent Injection Endpoint**: Add API/CLI `inject_agent(yaml_def)` that adds a new agent definition to the runtime Registry without restart.
    * *Verify:* curl POST a new agent definition; `get_all_agents()` returns n+1 agents.
5.  **[x] Runtime Hot-Swap Interface**: Implement logic to update an *existing* agent's prompt/tools in the Registry while the system is running.
    * *Verify:* Change Planner prompt via API; next run uses new text (proven by log output).
6.  **[x] Abstract Planner Dependencies**: Modify `PlannerAgent` to discover "worker" agents via Registry query, not a hardcoded string list.
    * *Verify:* Add "SpecialistX" to Registry; Planner automatically lists "SpecialistX" in available delegation targets.
7.  **[x] Loop State Serialization**: Ensure the `AgentLoop` state (current step, history) is fully serializable to JSON (Nanobot parity requirement).
    * *Verify:* Pause loop, save state, restart app, load state, resume execution exactly where left off.

## Phase 2: MCP & Tooling Stability (The "Fix It" Phase)
*Goal: Replace fragile Regex with AST and ensure connection stability.*

8.  **[x] AST Tool Parser**: Create `core/mcp_inspector.py` using `ast` module to extract tool definitions (name, docstring, args).
    * *Verify:* Parser correctly identifies tools in a file with complex decorators and type hints (no regex failures).
9.  **[x] Strict Tool Schema Validation**: Wrap all extracted tools in a Pydantic model. Fail hard on missing docstrings.
    * *Verify:* Attempt to load a tool with missing docstring; system throws `InvalidToolDefinition` error.
10. **[x] Safe Process Management**: Implement `MCPManager` that tracks process PIDs and connection states.
    * *Verify:* `manager.list_active_servers()` returns PIDs; `kill` command actually terminates the OS process.
11. **[x] Connection Draining Protocol**: Implement logic to "drain" active requests before reloading an MCP server.
    * *Verify:* Start a long-running tool call, trigger reload. Reload waits for call to finish before swapping.
12. **[x] BrowserMCP via CDP**: Refactor `server_browser.py` to connect to Chrome DevTools Protocol (port 9222) instead of launching a new headless instance.
    * *Verify:* Open a tab in local Chrome; run `browser_tool.get_current_url()`; returns the URL of your local tab.
13. **[x] Browser Context Reuse**: Ensure the BrowserMCP attaches to the existing *User Data Dir* to access cookies/history (avoiding the SQLite lock trap).
    * *Verify:* Login to a site in local Chrome; BrowserMCP can access a dashboard on that site without re-login.

## Phase 3: Skills & Prompt Consolidation (The "No Modification" Phase)
*Goal: Zero redundancy. Prompts become executable Skills.*

14. **[x] Skill Class Definition**: Create `core/skills/base.py` holding `prompt_text`, `tool_definitions`, and `memory_config`.
    * *Verify:* Class instantiation works.
15. **[x] Prompt-to-Skill Migration (Strict)**: Move `prompts/*.md` into `core/skills/library/*/skill.py`.
    * *Verify:* **CHECKSUM TEST**: `md5(original_md_file) == md5(skill.prompt_text)`. Zero deviation allowed.
16. **[x] Skill Injection Logic**: Modify `BaseAgent` to compose its System Prompt by concatenating enabled Skills.
    * *Verify:* Agent with [Coder, Researcher] skills has a System Prompt containing both text blocks.
17. **[x] Tool-Call verification**: Prove that enabling a Skill actually registers its tools.
    * *Verify:* Test: Enable `RAGSkill`. Agent `tools` list now contains `search_knowledge_base`. Disable Skill -> Tool disappears.
18. **[x] Runtime Skill Toggle**: Allow agents to dynamically enable/disable skills based on task complexity (steerability).
    * *Verify:* Planner decides "This needs research"; enables `ResearchSkill` for the worker; worker now has search tools.
19. **[x] RAG Pluggability Test**: Verify a *non-retriever* agent (e.g., Coder) can use the RAG Skill.
    * *Verify:* Give Coder `RAGSkill`; ask it to "find docs and code"; Coder calls `search` tool successfully.
20. **[x] Delete Legacy Prompts**: Remove `prompts/` directory only after all Checksum tests pass.
    * *Verify:* CI/Build passes without `prompts/` folder.

## Phase 4: Active Memory Systems (The "Missing Link")
*Goal: Memory must be searched BEFORE planning, not just stored.*

21. **[x] Episodic Retrieval Implementation**: Implement `search_episodes(query)` in `memory/episodic.py` (Vector or Keyword based, must be retrievable).
    * *Verify:* Save episode "Don't use library X"; Search "library X"; returns warning.
22. **[x] Pre-Plan Retrieval Hook**: Modify `PlannerAgent.run()` to execute `search_episodes` *before* generating the plan.
    * *Verify:* Log trace shows: `[Memory] Retrieved 3 relevant past mistakes` -> `[LLM] Generating Plan`.
23. **[x] Semantic Injection Proof**: Create a regression test for `routers/runs.py` semantic search.
    * *Verify:* Mock the Vector DB. Run a query. Assert `context` variable strictly contains "Relevant Memory: ...".
24. **[x] Cortex-R Profile Loader**: Implement parser for `profiles.yaml` that enforces structure (biases, recursion limits).
    * *Verify:* Load profile; access `profile.biases.conciseness`; returns value.
25. **[x] Steerability Implementation**: Connect Cortex-R `recursion_limit` to `AgentLoop` config.
    * *Verify:* Profile limit=2. Loop stops at step 2.
26. **[x] Preference Enforcement Test**: Verify `get_compact_policy()` is actually modifying agent behavior.
    * *Verify:* Add preference "Always start response with 'Captain:'". Run agent. Output starts with "Captain:".
27. **[x] User Profiling Loop**: Ensure `UserProfiler` agent runs *asynchronously* after tasks to update `user_profile.json`.
    * *Verify:* Finish task. Wait 5s. Check `last_updated` timestamp on profile JSON.

## Phase 5: Frontend & App Generation (Fixing the "Text Block" Issue)
*Goal: Structured UI generation with hydration limits removed.*

28. **[x] Define App Schema**: Create strict JSON schema (Pydantic) for UI generation (Layout, Components, Data).
    * *Verify:* Validate existing `ui.json`; fails if fields missing.
29. **[x] Structured Output Enforcement**: Update `ReportToApp` skill to use *JSON Mode* or strict schema prompting.
    * *Verify:* Send vague prompt. Response is valid JSON, no markdown text blocks.
30. **[x] Data Extraction Agent**: Implement `DataExtractor` step that runs *between* Report and UI Gen.
    * *Verify:* Input: Text Report. Output: `data.json` with extracted metrics.
    * *Constraint:* UI Gen must use this `data.json`, not raw text.
31. **[x] Hydrate-App Layout Rewrite**: Allow `hydrate-app` to modify the `layout` array in `ui.json`.
    * *Verify:* Request "Move header to bottom". Layout array order updates.
32. **[x] Component Awareness**: Inject list of available UI components (Charts, Tables) into the generator's context.
    * *Verify:* Generator uses `<BarChart>` (valid) instead of `<MyChart>` (hallucinated).

## Phase 6: Visuals & Unified Previews
*Goal: One viewer logic for everything. No scattered implementations.*

33. **[x] Preview Viewer Inventory**: Audit and list every file currently rendering content (PDFViewer, MarkdownViewer, RAGCard, etc.).
    * *Verify:* `CAPSTONE/viewer_inventory.md` created.
34. **[x] Unified Preview Interface**: Create `core/previews.py` -> `generate_preview(content, type)`.
    * *Verify:* Unit test: Pass PDF -> returns PDF component config. Pass MD -> returns MD component config.
35. **[x] Route RAG to Unified**: Refactor `routers/rag.py` to use `generate_preview`.
    * *Verify:* RAG search results render via the unified path.
36. **[x] Route Browser to Unified**: Refactor `server_browser.py` to use `generate_preview` for snapshots.
    * *Verify:* Browser screenshot renders via the unified path.
37. **[x] Route IDE to Unified**: Refactor `ide_agent.py` to use `generate_preview` for file reads.
    * *Verify:* `read_file` output renders via the unified path.
38. **[x] Routing Guarantee Test**: A test that fails if a new content type is added without a registered preview handler.
    * *Verify:* Add "NewType"; system warns "No preview handler defined".

## Phase 7: Unified Sandboxing (Single Execution Path)
*Goal: Merge `AgentLoop` execution and `MCP` execution.*

39. **[x] Universal Sandbox Class**: Create `core/sandbox/executor.py` (The single source of truth).
    * *Verify:* Execute `print(1+1)`.
40. **[x] Refactor Loop Execution**: Point `AgentLoop._auto_execute_code` to `Universal Sandbox`.
    * *Verify:* Loop runs code successfully.
41. **[x] Refactor MCP Execution**: Point `server_sandbox.py` to `Universal Sandbox`.
    * *Verify:* MCP tool runs code successfully.
42. **[x] Trace Verification**: Add logging to `Universal Sandbox`.
    * *Verify:* Run Loop; Run MCP. Both logs appear in the *same* log stream/file.
43. **[x] Deprecate Legacy Executors**: Delete old `_auto_execute` and standalone sandbox logic.
    * *Verify:* Grep for `subprocess.run` inside `loop.py` returns 0 matches.

## Phase 8: IDE Agent Integration
*Goal: Bring the "Outlier" into the fold.*

44. **[x] IDE Agent Wrapper**: Wrap the `ide_agent.py` logic into a standard `Agent` class that implements `step()`.
    * *Verify:* IDE Agent can be loaded by `AgentLoop`.
45. **[x] Model Standardization**: Force IDE Agent to use `models.json` config, removing hardcoded Ollama calls.
    * *Verify:* Change config to GPT-4; IDE Agent traces show GPT-4 usage.
46. **[x] Memory Stream Integration**: Ensure IDE Agent chats are saved to `EpisodicMemory`.
    * *Verify:* Chat with IDE Agent. Check `memory/episodes.json`. Chat is present.
47. **[x] File Reader Skill**: Extract file reading logic into a reusable `FileReadSkill`.
    * *Verify:* Give `FileReadSkill` to General Agent. It can now read files.

## Phase 9: Verification & Stress Testing
*Goal: Prove robustness.*

48. **[x] E2E Plan-to-Code**: Script: "Create a snake game".
    * *Verify:* Code is generated, saved, executed, and preview link generated.
49. **[x] E2E RAG-to-Report**: Script: "Research X".
    * *Verify:* Report generated with citations (from RAG skill).
50. **[x] Skill Toggle Stress Test**: Script: Enable/Disable skills 50 times in a loop.
    * *Verify:* No crash. Memory usage stable.
51. **[x] MCP Hot-Reload Stress Test**: Script: Reload BrowserMCP while navigating.
    * *Verify:* No orphan Chrome processes. Connection recovers.
52. **[x] Token Budget Test**: Verify `AgentLoop` respects token limits defined in `profiles.yaml`.
    * *Verify:* Set low limit. Loop aborts with "Token Limit Exceeded".
53. **[x] Context Window Protection**: Verify "File Reader" summarizes large files instead of crashing.
    * *Verify:* Read 100k line file. Agent receives summary, not crash.

## Phase 10: Final Cleanup
54. **[x] Dead Code Sweep**: Aggressive deletion of unused imports/functions.
55. **[x] Config Validation**: Startup script checks `agent_config.yaml`, `profiles.yaml`, `ui.json` against schemas.
56. **[x] Secret Scan**: Ensure no keys in code.
57. **[x] Logger Unification**: All modules use `core.logger`.
58. **[x] Dependency Pruning**: `pip freeze` cleanup.
59. **[x] Documentation Update**: `README.md` reflects Registry/Skill architecture.
60. **[x] Architecture Diagram**: Generate a Mermaid diagram of the new unified flow.
61. **[x] Final Build**: Clean install & run.
62. **User Sign-off**: Review `parity_matrix.md` with user.