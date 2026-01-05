
# 🚀 S16 NetworkX: The Modern Agent Architecture

Welcome to the new **NetworkX-First** implementation. 
This version replaces the manual graph management with a robust DAG structure and integrates modern tools.

## 🏗️ Architecture

### 1. The Core (Graph Engine)
*   **File**: `core/loop.py`
*   **Logic**: Uses `networkx.DiGraph` to manage the plan.
*   **Context**: Strictly isolated. Node B only sees Node A's output if `A -> B`.
*   **Summarizer**: Special agent with **Global Read Access** to synthsize everything.

### 2. The Tools (Hybrid Stack)
*   **Browser**: **Hybrid Mode**.
    *   Fast Search: `duckduckgo` (Text).
    *   Deep Action: `browser-use` (Vision).
*   **Memory**: **Dual Layer**.
    *   Short-term: Session Context (NetworkX attributes).
    *   Long-term: `mem0` (User Profile, Local).
*   **Sandbox**: `e2b` capable (currently wrapped in `tools/sandbox.py`).

### 3. Folder Structure
```text
Arcturus/
├── agents/             # AgentRunners (Logic)
├── config/             # YAML Configs + Models
├── core/               # Main Loop & Utils
├── memory/             # Context & Mem0 Store
├── mcp_servers/        # Tool Servers (Browser, RAG)
├── prompts/            # System Prompts (Markdown)
├── tools/              # Helper Scripts
└── app.py              # Entry Point
```

## 🏃‍♂️ How to Run

### Interactive Mode
```bash
uv run Arcturus/app.py
```
Type your query (e.g., "Plan a 3 day trip to Tokyo").

### Automated Test
```bash
uv run Arcturus/test_run.py
```

## 🛠️ Configuration
*   **Agents**: `config/agent_config.yaml` maps Agents -> Prompts -> Tools.
*   **Models**: `config/models.json` defines LLMs (Gemini, Ollama).
*   **Prompts**: Edit `prompts/*.md` to change agent behavior.

## 🔮 Next Steps (Roadmap)
1.  **UI**: Connect `ui/visualizer.py` to a React Flow frontend.
2.  **E2B**: Fully replace `tools/sandbox.py` with E2B SDK.
3.  **Mem0**: Enable active learning in `SummarizerAgent`.
