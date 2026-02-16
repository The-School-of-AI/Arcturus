
# Arcturus Viewer Inventory

This document tracks all existing preview and data visualization components across the Arcturus platform.

## 1. Document & File Viewers (RAG / Local)
- **DocumentViewer** (`src/components/rag/DocumentViewer.tsx`)
    - **PDF**: Uses `@react-pdf-viewer/core`. Supports page jumping and text search.
    - **DOCX**: Uses `docx-preview`.
    - **Markdown**: Uses `react-markdown` with GFM.
    - **Code**: Uses `react-syntax-highlighter` (Prism). Supports line numbering and highlighting.
    - **Images**: Native `<img>` rendering with premium shadows/borders.
    - **AI Chunks**: Custom view for indexed RAG chunks with drill-down and code highlighting.

## 2. Web & Research Viewers
- **NewsArticleViewer** (`src/features/news/components/NewsArticleViewer.tsx`)
    - **Iframe Mode**: Renders proxied HTML. Injects scripts for text selection (for context adding) and link interception.
    - **Reader Mode**: Clean Markdown-only view for articles.
    - **GitHub Viewer**: Specialized auto-detection for GitHub URLs; renders README.md as the primary view.
    - **PDF Mode**: Bridges to `PDFViewer` for academic papers or online reports.

## 3. Agent Execution Viewers
- **Execution Graph** (`src/components/graph/GraphCanvas.tsx` & `FlowStepNode.tsx`)
    - Uses React Flow.
    - Visualizes the execution DAG (Plan Graph).
    - Status indicators: Pending, Running, Completed, Failed.
    - Integration: `FlowWorkspace.tsx`.

## 4. UI & Business Component Viewers
- **App Generator Previews** (Generated via `core/ui_generator.py`)
    - Renders dynamic React components from a Pydantic schema.
- **Data Cards** (`src/features/apps/components/cards/`)
    - **JSONViewerCard**: Formatted JSON display with optional line numbering.
    - **ChartCard** (Suspected, needs verification): Likely wraps Chart.js or Recharts.

## 5. Console/Terminal Viewers
- **Rich Visualizer** (`ui/visualizer.py`)
    - Terminal-based DAG rendering using Rich.
    - Used for background execution monitoring.
