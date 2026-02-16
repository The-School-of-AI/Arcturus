# Arcturus Platform Architecture

Arcturus is a unified agentic OS designed for deep workspace integration and secure execution.

## System Overview

```mermaid
graph TD
    User([User]) --> UI[Vite Frontend]
    UI --> API[FastAPI Server]
    API --> Router[Routers: RAG, Git, IDE, Explorer]
    Router --> Loop[AgentLoop4]
    Loop --> Runner[AgentRunner]
    Runner --> Registry[Agent Registry]
    Runner --> MCP[MultiMCP Client]
    Registry --> Skills[Skill Manager: Coder, Browser, etc.]
    MCP --> Sbox[UniversalSandbox]
    MCP --> SRag[RAG Server]
    MCP --> SBrowser[Browser Server]
    Skills --> Episodic[Episodic Memory]
    Episodic --> Disk[(JSON Storage)]
```

## Key Components

### 1. AgentLoop4 (The Heart)
- Manages the ReAct execution loop.
- Handles retries, token budgets, and step-level state management.
- Integrates with the `UserProfiler` for real-time personalization.

### 2. Universal Sandbox
- Secure execution environment for AI-generated code.
- AST-based safety checks and auto-awaiting for MCP tools.
- Capture/Serialization of real-time logs and results.

### 3. Skill & Agent Registry
- Decentralized skill management (library-based).
- Dynamic prompt compilation based on current agent context.
- Support for "Skills-on-Demand".

### 4. Unified Preview Interface
- Standardized rendering for Code, Markdown, PDF, CSV, and Images.
- Integrated across RAG, Browser, and IDE agents.

### 5. MultiMCP Hub
- High-level client for concurrent interaction with multiple MCP servers.
- Automatic routing and discovery of capabilities.
