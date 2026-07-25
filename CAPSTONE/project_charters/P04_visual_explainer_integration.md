# Visual Explainer Integration

This document describes how the **visual-explainer** skill is integrated into the generation/render pipeline: setup, usage paths, limitations, and integration decisions.

---

## Overview

Visual Explainer produces self-contained HTML for diagrams (architecture, Mermaid, data tables). It is available in three ways:

1. **Skill (prompt path)** — The agent follows `core/skills/library/visual_explainer/SKILL.md` and writes HTML to `~/.agent/diagrams/` and opens in browser.
2. **Canvas** — HTML can be pushed to the Canvas via WebSocket (`updateHtml`); the user sees it in-app without opening a file.
3. **Apps** — Dashboard cards of type `html_diagram` / `visual_explainer` render that HTML in a sandboxed iframe.

A **service** (`core/visual_explainer_service.py`) and **REST API** (`POST /api/visual-explainer/generate`) allow pipelines (or the frontend) to generate HTML without going through the skill’s prompt path.

---

## Setup

### Backend

- **Canvas**: Ensure the canvas router is mounted (e.g. under `/api`). The WebSocket is at `ws://<host>/api/canvas/ws/<surface_id>` (default surface: `main-canvas`). The runtime must support `push_html(surface_id, html, title)` and the schema must include `UpdateHtmlMessage`.
- **Visual Explainer API**: The router in `routers/visual_explainer.py` must be included (e.g. `app.include_router(visual_explainer_router.router, prefix="/api")`). Endpoint: `POST /api/visual-explainer/generate` with body `{ "type": "table"|"mermaid"|"architecture"|"raw", "title": "...", "content": {...} }`.
- **Skills**: The visual_explainer skill is registered in `core/skills/registry.json` and can be enabled in `config/agent_config.yaml` for agents that should prefer HTML diagrams over ASCII.

### Frontend

- **Canvas**: Open the **Canvas** tab in the sidebar (e.g. “Canvas” or “canvas” tab). The host connects to `ws://localhost:8000/api/canvas/ws/main-canvas` and listens for `updateHtml`; when received, it shows the HTML in the sandbox iframe.
- **Apps**: The **Apps** builder supports card types `html_diagram` and `visual_explainer`. Add the card from the sidebar (if added to the component palette) or via app generation; card `data` should include `html` (preferred) or `url`.

### Optional: MCP tool for agent → Canvas

To let the agent push diagrams to the Canvas, add an MCP tool (e.g. `canvas_push_html`) that accepts `html` and optional `title` and `surface_id`, and calls `get_canvas_runtime().push_html(surface_id, html, title)`. The agent can then call this tool when it would have written to `~/.agent/diagrams/`, so the diagram appears in the Canvas tab.

---

## Usage Paths (UI / Workflow)

### 1. Canvas: “Show diagram in Canvas”

- **Who**: User or agent.
- **Flow**:  
  - **Agent**: Agent has visual_explainer in config; when it generates a diagram it can (a) write to `~/.agent/diagrams/` and open in browser (current behavior), and/or (b) call an MCP tool or backend API that calls `push_html("main-canvas", html, title)` so the same HTML appears in the Canvas tab.  
  - **User / API**: Any client can POST to the canvas test endpoint with `{ "html": "<!DOCTYPE html>...", "title": "My Diagram" }` to push HTML to a surface, or use the MCP tool once implemented.
- **UI**: User opens the **Canvas** tab in the sidebar; content appears when the backend sends `updateHtml`.

### 2. Apps: “Embed diagram in a dashboard”

- **Who**: User building an app, or app-from-report generator.
- **Flow**:  
  - Add an **HTML Diagram** (or “Visual Explainer”) card from the Apps sidebar (Basics or Dev & Feed).  
  - Set card `data.html` (or `data.url`) in the inspector — e.g. paste HTML, or call `POST /api/visual-explainer/generate` and paste the returned `html` into the card data.  
  - For report→app generation, the pipeline can call the visual-explainer service and inject one or more `html_diagram` cards with `data.html` set.
- **UI**: **Apps** tab → create or edit app → drag “HTML Diagram” onto the grid → in the right panel (inspector), set **HTML** (or URL). The card renders the content in a sandboxed iframe.

### 3. API-only: “Generate HTML for use elsewhere”

- **Who**: Frontend, MCP, or another service.
- **Flow**: `POST /api/visual-explainer/generate` with `type`, `title`, and `content`. Use the returned `html` in Canvas (push via canvas API), in an app card (`data.html`), or save/serve as a file.
- **UI**: No direct UI; used by other flows or scripts.

---

## Integration Decisions

| Decision | Rationale |
|----------|-----------|
| **Prefer `data.html` over `data.url` in app cards** | Security and offline: inline HTML is under app control; URLs can load third-party content. |
| **Sandbox iframe attributes** | Use `allow-scripts allow-forms allow-popups allow-modals` to match Canvas SandboxFrame; no `allow-same-origin` when using `srcdoc` to keep isolation. |
| **Service in `core/` not inside skill package** | The service is callable from API, MCP, and app pipeline without importing the skill class; the skill remains prompt-only. |
| **Canvas and Apps both supported** | Canvas is for live, session-based viewing (e.g. agent output); Apps are for persisted dashboards. |
| **Two card type names** | `html_diagram` and `visual_explainer` both map to the same render branch so existing or generated apps can use either name. |

---

## Limitations

- **Canvas**: Requires the frontend to be open and the Canvas tab selected (or at least the WebSocket connected) to receive `updateHtml`. No built-in “history” of past diagrams on a surface; only the latest HTML is stored per surface.
- **Apps**: Large `data.html` can make app state large; consider a size limit or switching to `data.url` for very big content if you add a safe diagram-serving route.
- **CSP / iframe**: Content in the iframe runs with the sandbox above; external scripts in the HTML may be blocked depending on CSP. Self-contained HTML with inline scripts and CDN fonts (as in the service output) is the supported pattern.
- **No built-in “Insert from API” in Apps UI**: The inspector does not yet have a “Generate diagram” button that calls `/api/visual-explainer/generate` and fills `data.html`; that can be added as a workflow improvement.

---

## File Reference

| Area | File(s) |
|------|--------|
| Service | `core/visual_explainer_service.py` |
| REST API | `routers/visual_explainer.py` |
| Canvas schema | `canvas/schema.py` (UpdateHtmlMessage) |
| Canvas runtime | `canvas/runtime.py` (push_html, surface state html/html_title) |
| Canvas router | `routers/canvas.py` (initial state + test-update html) |
| Canvas frontend | `platform-frontend/src/features/canvas/CanvasHost.tsx` (updateHtml case) |
| App card render | `platform-frontend/src/features/apps/components/AppGrid.tsx` (html_diagram / visual_explainer case) |
| Skill | `core/skills/library/visual_explainer/` (SKILL.md, templates, skill.py) |