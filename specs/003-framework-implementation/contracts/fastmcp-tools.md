# FastMCP Tool Contracts

**Date**: 2025-10-31  
**Feature**: 003-framework-implementation  
**Status**: Design Complete

This document defines the FastMCP tool contracts for editor/agent integration. All tools are time-bounded, project-scoped, and return trimmed, citation-ready outputs. Tools use declarative `fastmcp.json` configuration and support named vector hybrid search.

## Server Configuration

**FastMCP Configuration File**: `fastmcp.json`

```json
{
  "dependencies": ["python-dotenv"],
  "transport": "stdio",
  "entrypoint": "src.infrastructure.mcp.server:create_mcp_server"
}
```

**Transport**: STDIO for Cursor/Claude Desktop integration (HTTP/SSE optional for future)

**Environment Integration**: Supports `fastmcp run` with uv environment pre-builds

---

## Tool: ingest_from_source

Ingest documents from source files or Zotero collections into a project collection.

**Tool Name**: `ingest_from_source`

**Parameters**:
- `project` (string, required): Project identifier (e.g., `citeloom/clean-arch`)
- `source` (string, required): Path to source document/directory OR `source=zotero` with collection/tag filters
- `options` (object, optional): Additional options:
  - `ocr_languages` (array[string]): Explicit OCR language codes (overrides Zotero/default)
  - `references_path` (string): Override CSL-JSON references file path
  - `force_rebuild` (boolean): Force collection rebuild for model migration

**Returns**:
```json
{
  "chunks_written": 42,
  "documents_processed": 2,
  "project": "citeloom/clean-arch",
  "dense_model": "fastembed/BAAI/bge-small-en-v1.5",
  "sparse_model": "Qdrant/bm25",
  "duration_seconds": 45.2,
  "warnings": ["Metadata not found for document 'paper.pdf'"]
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `EMBEDDING_MISMATCH`: Embedding model doesn't match collection (unless force_rebuild)
- `TIMEOUT`: Operation exceeded timeout (15s)

**Constraints**:
- Timeout: 15 seconds
- Idempotent: Deterministic chunk IDs prevent duplicates
- OCR language priority: Zotero metadata language → explicit config → default ['en', 'de']

---

## Tool: query

Dense-only vector search using named vector 'dense' with model binding.

**Tool Name**: `query`

**Parameters**:
- `project` (string, required): Project identifier
- `text` (string, required): Query text (model binding handles embedding automatically)
- `top_k` (integer, optional): Maximum results (default 6, max configurable)
- `filters` (object, optional): Additional filters (e.g., `{"tags": ["architecture"], "section_prefix": "Part I"}`)

**Returns**:
```json
{
  "items": [
    {
      "render_text": "Entities and value objects are distinct...",
      "score": 0.87,
      "citekey": "cleanArchitecture2023",
      "section": "Entities and Value Objects",
      "page_span": [45, 46],
      "section_path": ["Part I", "Chapter 3"],
      "doi": "10.1000/xyz123",
      "full_text": null
    }
  ],
  "count": 6,
  "model": "fastembed/BAAI/bge-small-en-v1.5"
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `TIMEOUT`: Operation exceeded timeout (8s)

**Constraints**:
- Always enforces project filter (server-side, no cross-project results)
- Text trimmed to `max_chars_per_chunk` policy (default 1,800 chars)
- `full_text` only provided if explicitly requested
- Timeout: 8 seconds
- Uses named vector 'dense' with model binding (text-based queries)

---

## Tool: query_hybrid

Hybrid search using RRF fusion (named vectors: dense + sparse).

**Tool Name**: `query_hybrid`

**Parameters**:
- `project` (string, required): Project identifier
- `text` (string, required): Query text for both sparse (BM25) and dense search
- `top_k` (integer, optional): Maximum results (default 6)
- `filters` (object, optional): Additional filters with AND semantics for tags

**Returns**:
```json
{
  "items": [
    {
      "render_text": "Clean Architecture emphasizes...",
      "score": 0.92,
      "citekey": "cleanArchitecture2023",
      "section": "Introduction",
      "page_span": [1, 2],
      "section_path": ["Part I"],
      "doi": "10.1000/xyz123"
    }
  ],
  "count": 6,
  "hybrid_enabled": true,
  "dense_model": "fastembed/BAAI/bge-small-en-v1.5",
  "sparse_model": "Qdrant/bm25",
  "fusion": "RRF"
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `HYBRID_NOT_SUPPORTED`: Hybrid search not enabled or sparse model not bound
- `INDEX_UNAVAILABLE`: Full-text index missing on chunk_text
- `TIMEOUT`: Operation exceeded timeout (15s)

**Constraints**:
- Only available if both dense and sparse models are bound (via `set_model()` and `set_sparse_model()`)
- RRF fusion is automatic when both named vectors are configured
- Combines BM25 (full-text) and vector scores using Reciprocal Rank Fusion
- Timeout: 15 seconds (longer than vector-only due to dual search)

---

## Tool: inspect_collection

Inspect project collection metadata, model bindings, and structure.

**Tool Name**: `inspect_collection`

**Parameters**:
- `project` (string, required): Project identifier
- `sample` (integer, optional): Number of sample payloads to return (default 0, max 5)

**Returns**:
```json
{
  "project": "citeloom/clean-arch",
  "collection": "proj-citeloom-clean-arch",
  "size": 1250,
  "dense_model": "fastembed/BAAI/bge-small-en-v1.5",
  "sparse_model": "Qdrant/bm25",
  "named_vectors": ["dense", "sparse"],
  "payload_keys": ["project_id", "doc_id", "section_path", "page_start", "page_end", "citekey", "doi", "year", "authors", "title", "tags", "source_path", "chunk_text", "heading_chain", "embed_model", "version"],
  "indexes": {
    "keyword": ["project_id", "doc_id", "citekey", "year", "tags"],
    "fulltext": ["chunk_text"]
  },
  "storage": {
    "on_disk_vectors": false,
    "on_disk_hnsw": false
  },
  "sample_payloads": []
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `INDEX_UNAVAILABLE`: Collection exists but indexes not available

**Constraints**:
- Timeout: 5 seconds
- Sample payloads limited to 5 max (for performance)
- Shows model bindings (dense and sparse) and named vector configuration

---

## Tool: list_projects

List all configured projects with metadata.

**Tool Name**: `list_projects`

**Parameters**: None

**Returns**:
```json
{
  "projects": [
    {
      "id": "citeloom/clean-arch",
      "collection": "proj-citeloom-clean-arch",
      "dense_model": "fastembed/BAAI/bge-small-en-v1.5",
      "sparse_model": "Qdrant/bm25",
      "hybrid_enabled": true
    }
  ],
  "count": 1
}
```

**Errors**: None (always succeeds, may return empty list)

**Constraints**:
- No timeout (fast enumeration)
- Always succeeds even if no projects configured

---

## Error Taxonomy

All tools return standardized error responses:

```json
{
  "error": {
    "code": "INVALID_PROJECT",
    "message": "Project 'invalid-project' not found. Available projects: citeloom/clean-arch",
    "details": {}
  }
}
```

**Error Codes**:
- `INVALID_PROJECT`: Project identifier doesn't exist
- `EMBEDDING_MISMATCH`: Embedding model doesn't match collection (unless migration flag)
- `HYBRID_NOT_SUPPORTED`: Hybrid search requested but sparse model not bound or disabled
- `INDEX_UNAVAILABLE`: Required index (full-text) missing or not ready
- `TIMEOUT`: Operation exceeded per-tool timeout limit

---

## Operational Policy

**Timeouts**:
- `ingest_from_source`: 15 seconds
- `query`: 8 seconds
- `query_hybrid`: 15 seconds
- `inspect_collection`: 5 seconds
- `list_projects`: No timeout (fast enumeration)

**Project Filtering**:
- All query operations enforce server-side project filtering
- Client-provided project filters are ignored (server enforces from tool parameter)
- Prevents cross-project data leakage

**Output Limits**:
- `top_k` capped at 6 by default (configurable per project)
- `render_text` trimmed to max_chars_per_chunk (default 1,800 characters)
- `full_text` only included if explicitly requested

**Correlation IDs**:
- All tool responses include correlation ID for observability
- Enables tracing across MCP calls and audit logs

