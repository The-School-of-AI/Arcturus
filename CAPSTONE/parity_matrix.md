
# Nanobot Parity Matrix

**Goal**: Align Arcturus with the lightweight, dynamic, and tool-centric architecture of Nanobot while retaining Arcturus's superior graph planning capabilities.

| Feature | Nanobot (Target) | Arcturus (Current) | Status | Gap / Solution |
| :--- | :--- | :--- | :--- | :--- |
| **Execution Flow** | Simple Iterative Loop (While-loop) | Graph-Based DAG (`networkx`) | ⚠️ Diverse | Arcturus is *more* powerful but less dynamic. **Goal**: Keep DAG but make nodes dynamically injectable. |
| **Agent Definition** | Dynamic (Class + Config) | Static (Hardcoded Classes) | ❌ Gap | Nanobot agents are config-driven. Arcturus agents are Python classes. **Solution**: `AgentRegistry`. |
| **Tooling** | Native MCP First | Mixed (Internal + MCP) | ⚠️ Partial | Arcturus has MCP but integration is fragile (Regex). **Solution**: `tools_manifest.json` & Importlib. |
| **Context/Memory** | Modular Builder | Tightly Coupled | ⚠️ Partial | **Solution**: Decouple `ContextManager` from Loop logic. |
| **Proactivity** | Cron / Heartbeat | Cron Router (Exist) | ✅ Match | Arcturus already has a Cron router. Need to verify it wakes up agents. |
| **State Serialization**| Full JSON Dump | Partial | ❌ Gap | Nanobot can pause/resume easily. Arcturus graph state is complex. **Solution**: Ensure all node data is JSON serializable. |
| **Dependency Injection**| Service Locator / Registry | Hardcoded Imports | ❌ Gap | `loop.py` imports `CoderAgent` directly. **Solution**: Registry Pattern. |
| **Browser Control** | Headless / Extension | Headless (Browser Use) | ⚠️ Partial | **Solution**: Add CDP / Extension bridge for "Real" browser control. |
| **Skill Loading** | Dynamic Plugin | Static Prompt Files | ❌ Gap | **Solution**: Full "Prompt-to-Skill" migration. |
| **Orchestration** | Bus-driven | HTTP/REST-driven | ✅ Acceptable | HTTP is fine for our use case, but internal Event Bus exists. |

## Parity Goals
1.  **Injectability**: Be able to add a new "Agent Type" without restarting the server.
2.  **Resumability**: Be able to serialize the entire `AgentLoop` state to disk and resume.
3.  **Lightweight**: Reduce the boilerplate required to define a new agent.
