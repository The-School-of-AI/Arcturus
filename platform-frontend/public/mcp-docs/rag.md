# RAG MCP

## Overview
The RAG (Retrieval-Augmented Generation) MCP server manages your local document knowledge base. It allows indexing of various document formats (PDF, DOCX, TXT, etc.) and semantic searching.

## Tools

### `search_stored_documents_rag`
Search old stored documents to get relevant extracts.
- **query**: The semantic search query.
- **doc_path**: (Optional) Filter search to a specific document.

### `preview_document`
Preview a document using the AI-enhanced extraction logic used for indexing.
- **path**: Path to the document.

### `ask_document`
Ask a question about a specific document using its context.
- **query**: The question.
- **doc_id**: The document ID/path.
