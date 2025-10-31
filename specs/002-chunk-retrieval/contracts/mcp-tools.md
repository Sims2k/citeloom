# MCP Tool Contracts

**Date**: 2025-01-27  
**Feature**: 002-chunk-retrieval  
**Status**: Design Complete

This document defines the Model Context Protocol (MCP) tool contracts for editor/agent integration. All tools are time-bounded, project-scoped, and return trimmed, citation-ready outputs.

## Tool: store_chunks

Batched upsert of chunks into a project collection.

**Tool Name**: `store_chunks`

**Parameters**:
- `project` (string, required): Project identifier (e.g., `citeloom/clean-arch`)
- `items` (array, required): Array of chunk objects with:
  - `id` (string): Deterministic chunk ID
  - `text` (string): Chunk text
  - `embedding` (array[float]): Embedding vector
  - `metadata` (object): Payload with project, source, zotero, doc, embed_model, version, fulltext

**Returns**:
```json
{
  "chunks_written": 42,
  "project": "citeloom/clean-arch",
  "embed_model": "fastembed/all-MiniLM-L6-v2",
  "warnings": []
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `EMBEDDING_MISMATCH`: Embedding model doesn't match collection (unless migration flag set)
- `TIMEOUT`: Operation exceeded timeout (15s)

**Constraints**:
- Batch size: 100-500 chunks per call
- Timeout: 15 seconds
- Idempotent: Deterministic chunk IDs prevent duplicates

---

## Tool: find_chunks

Vector search for chunks in a project.

**Tool Name**: `find_chunks`

**Parameters**:
- `project` (string, required): Project identifier
- `query` (string, required): Natural language query text
- `top_k` (integer, optional): Maximum results (default 6, max configurable)
- `filters` (object, optional): Additional filters (e.g., `{"tags": ["architecture"]}`)

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
  "count": 6
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `TIMEOUT`: Operation exceeded timeout (8s for vector search)

**Constraints**:
- Always enforces project filter (no cross-project results)
- Text trimmed to `max_chars_per_chunk` policy (default ~1800 chars)
- `full_text` only provided if explicitly requested
- Timeout: 8 seconds

---

## Tool: query_hybrid

Hybrid search (full-text + vector fusion) for chunks.

**Tool Name**: `query_hybrid`

**Parameters**:
- `project` (string, required): Project identifier
- `query` (string, required): Query text for BM25 and vector search
- `top_k` (integer, optional): Maximum results (default 6)
- `filters` (object, optional): Additional filters

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
  "hybrid_enabled": true
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `HYBRID_NOT_SUPPORTED`: Hybrid search not enabled for project
- `TIMEOUT`: Operation exceeded timeout (15s)

**Constraints**:
- Only available if `hybrid_enabled=True` for project
- Combines BM25 (full-text) and vector scores with fusion policy
- Timeout: 15 seconds (longer than vector-only due to full-text indexing)

---

## Tool: inspect_collection

Inspect project collection metadata and structure.

**Tool Name**: `inspect_collection`

**Parameters**:
- `project` (string, required): Project identifier
- `sample` (integer, optional): Number of sample payloads to return (default 0)

**Returns**:
```json
{
  "project": "citeloom/clean-arch",
  "collection": "proj-citeloom-clean-arch",
  "size": 1250,
  "embed_model": "fastembed/all-MiniLM-L6-v2",
  "payload_keys": ["project", "source", "zotero", "doc", "embed_model", "version", "fulltext"],
  "indexes": {
    "keyword": ["project", "zotero.tags"],
    "fulltext": ["fulltext"]
  },
  "sample": [
    {
      "id": "chunk-abc123",
      "project": "citeloom/clean-arch",
      "source": {"path": "docs/clean-arch.pdf", "title": "Clean Architecture"},
      "zotero": {"citekey": "cleanArchitecture2023", "tags": ["architecture"]},
      "doc": {"page_span": [45, 46], "section": "Entities", "section_path": ["Part I", "Chapter 3"]}
    }
  ]
}
```

**Errors**:
- `INVALID_PROJECT`: Project doesn't exist
- `INDEX_UNAVAILABLE`: Collection indexes not accessible

**Constraints**:
- Does not expose sensitive data (no full text unless in sample)
- Sample limited to 5 payloads max

---

## Tool: list_projects

List all configured projects with basic metadata.

**Tool Name**: `list_projects`

**Parameters**: None

**Returns**:
```json
{
  "projects": [
    {
      "id": "citeloom/clean-arch",
      "collection": "proj-citeloom-clean-arch",
      "embed_model": "fastembed/all-MiniLM-L6-v2",
      "hybrid_enabled": true
    },
    {
      "id": "citeloom/ddd",
      "collection": "proj-citeloom-ddd",
      "embed_model": "fastembed/all-MiniLM-L6-v2",
      "hybrid_enabled": false
    }
  ]
}
```

**Errors**: None (always succeeds, may return empty list)

**Constraints**:
- Returns all projects from configuration
- No timeout (fast read operation)

---

## Error Taxonomy

All tools return standardized error codes with human-readable messages:

| Error Code | Description | HTTP-like Status |
|------------|-------------|------------------|
| `INVALID_PROJECT` | Project identifier doesn't exist | 404 Not Found |
| `EMBEDDING_MISMATCH` | Embedding model doesn't match collection | 409 Conflict |
| `HYBRID_NOT_SUPPORTED` | Hybrid search not enabled for project | 400 Bad Request |
| `INDEX_UNAVAILABLE` | Required indexes not present | 503 Service Unavailable |
| `TIMEOUT` | Operation exceeded time limit | 504 Gateway Timeout |

**Error Response Format**:
```json
{
  "error": {
    "code": "INVALID_PROJECT",
    "message": "Project 'citeloom/unknown' not found. Available projects: ['citeloom/clean-arch', 'citeloom/ddd']",
    "details": {
      "project_id": "citeloom/unknown",
      "available_projects": ["citeloom/clean-arch", "citeloom/ddd"]
    }
  }
}
```

---

## Output Shaping Rules

All retrieval tools (`find_chunks`, `query_hybrid`) follow these rules:

1. **Text Trimming**: `render_text` is trimmed to `max_chars_per_chunk` (default ~1800 chars)
2. **Citation Ready**: Always include `citekey`, `page_span`, `section`, `section_path`
3. **Metadata Preservation**: Include `doi`/`url` if available
4. **No Full Text by Default**: `full_text` only returned if explicitly requested
5. **Score Normalization**: Scores normalized to [0, 1] range

**Example Trimmed Output**:
```json
{
  "render_text": "Clean Architecture emphasizes the separation of concerns across layers. The domain layer contains pure business logic, while the application layer orchestrates use cases...",
  "full_text": null  // Only included if requested
}
```

---

## Timeout Policy

| Tool | Timeout | Rationale |
|------|---------|------------|
| `store_chunks` | 15s | Batch upsert can take time for large batches |
| `find_chunks` | 8s | Vector search is fast, shorter timeout |
| `query_hybrid` | 15s | Full-text + vector fusion requires more processing |
| `inspect_collection` | 5s | Metadata read is fast |
| `list_projects` | 2s | Configuration read is very fast |

**Timeout Behavior**:
- Cancel operation immediately on timeout
- Return `TIMEOUT` error with context
- Log incomplete operation for debugging

---

## Rate Limiting & Batch Limits

- `store_chunks`: 100-500 chunks per batch (enforced)
- `find_chunks`: `top_k` capped at 6 by default (configurable, max 20)
- `query_hybrid`: Same limits as `find_chunks`
- Concurrent operations: Optimistic concurrency (last-write-wins)

---

## Security & Authentication

- **CLI**: No authentication required (single-user local system)
- **MCP Tools**: Optional authentication (configurable via MCP server settings)
- **Secrets**: Never logged or exposed in tool outputs
- **Project Isolation**: Strict project filtering enforced (no cross-project access)

---

## Testing Requirements

- Unit tests: Mock MCP server responses
- Integration tests: Test against real MCP server
- Performance tests: Verify timeout behavior
- Error handling: Verify all error codes are returned correctly

