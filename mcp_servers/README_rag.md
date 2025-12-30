# Local Storage RAG MCP Server

This MCP server manages a local Retrieval-Augmented Generation (RAG) system, allowing you to index documents, search them using semantic vectors (embeddings), and ask questions about them.

## Features
- **Local Indexing**: Indexes documents from the `data/` directory using FAISS.
- **Semantic Search**: Uses embeddings (Ollama) to find relevant chunks.
- **Image Captioning**: Automatically captions images within documents using vision models.
- **Semantic Chunking**: Smartly splits text based on topic shifts.

## Tools

### `preview_document(path: str) -> MarkdownOutput`
Preview a document using AI-enhanced extraction logic. Supports PDF, HTML, DOCX, and more.
- **path**: Relative path to the document in the `data/` directory.

### `ask_document(query: str, doc_id: str, history: list = [], image: str = None) -> str`
Ask a question about a specific document. Uses RAG to find relevant context before answering.
- **query**: Your question.
- **doc_id**: The path of the document to query (optional context filter).
- **history**: Chat history for context.
- **image**: Optional image to include in the query.

### `search_stored_documents_rag(query: str, doc_path: str = None) -> list[str]`
Search stored documents using vector similarity.
- **query**: The search string.
- **doc_path**: Optional filter to search only within a specific document.

### `keyword_search(query: str) -> list[str]`
Search for exact keyword matches across all indexed document chunks.
- **query**: The keyword to search for.

### `caption_image(img_url_or_path: str) -> str`
Generate a description/caption for an image using a Vision LLM.
- **img_url_or_path**: URL or relative path to the image.
