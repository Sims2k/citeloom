# Quick Start Guide: Production-Ready Document Retrieval System

**Date**: 2025-10-31  
**Feature**: 003-framework-implementation  
**Status**: Design Complete

This guide provides a quick start for implementing the production-ready document retrieval system with Docling v2, Qdrant named vectors, FastMCP, and enhanced Zotero integration.

## Prerequisites

- Python 3.12.x (via pyenv)
- uv package manager
- Qdrant server running (local or remote)
- Zotero with Better BibTeX installed (optional, for citation metadata)

## Setup

1. **Install dependencies**:
   ```bash
   uv sync
   uv add python-dotenv  # For .env file support
   ```

2. **Configure environment variables** (create `.env` file in project root):
   ```bash
   # Optional API keys (gracefully degrade if missing)
   OPENAI_API_KEY=sk-...  # For OpenAI embeddings (optional)
   QDRANT_API_KEY=...     # For authenticated Qdrant (optional)
   
   # Optional configuration
   CITELOOM_CONFIG=citeloom.toml  # Custom config path (optional)
   ```

3. **Configure project** (`citeloom.toml`):
   ```toml
   [project."citeloom/clean-arch"]
   collection = "proj-citeloom-clean-arch"
   references_json = "references/clean-arch.json"
   embedding_model = "fastembed/BAAI/bge-small-en-v1.5"
   sparse_model = "Qdrant/bm25"  # Optional: for hybrid search
   hybrid_enabled = true

   [chunking]
   max_tokens = 450
   overlap_tokens = 60
   heading_context = 2
   tokenizer = "minilm"  # Must match embedding model tokenizer family

   [qdrant]
   url = "http://localhost:6333"
   create_fulltext_index = true  # Required for hybrid search
   ```

## Implementation Checklist

### 1. Docling Conversion (DocumentConverter)

- [ ] Implement `DoclingConverterAdapter.convert()` with:
  - [ ] Docling v2 `DocumentConverter` initialization
  - [ ] OCR language selection: Zotero metadata `language` → explicit config → default ['en', 'de']
  - [ ] Timeout handling: 120s document, 10s per-page
  - [ ] Page map extraction: `page_number → (start_offset, end_offset)`
  - [ ] Heading tree extraction with page anchors
  - [ ] Text normalization: hyphen repair, whitespace normalization, code/math block preservation
  - [ ] Diagnostic logging for timeout/page failures

### 2. Docling Chunking (HybridChunker)

- [ ] Implement `DoclingHybridChunkerAdapter.chunk()` with:
  - [ ] Tokenizer alignment: Use tokenizer matching embedding model family
  - [ ] Heading-aware chunking with `heading_context` ancestors
  - [ ] Quality filtering: Minimum 50 tokens, signal-to-noise ratio ≥ 0.3
  - [ ] Deterministic chunk IDs: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`
  - [ ] Section path breadcrumb extraction
  - [ ] Page span mapping from page_map

### 3. Qdrant Collection Setup (Named Vectors)

- [ ] Implement `QdrantIndexAdapter.ensure_collection()` with:
  - [ ] Named vector creation: `dense` (FastEmbed model) and `sparse` (BM25/SPLADE/miniCOIL)
  - [ ] Model binding: `set_model()` for dense, `set_sparse_model()` for sparse
  - [ ] Payload indexes: Keyword on `project_id`, `doc_id`, `citekey`, `year`, `tags`
  - [ ] Full-text index on `chunk_text` (if hybrid enabled, tokenizer: `word`)
  - [ ] On-disk storage flags for large projects (configurable)
  - [ ] Model ID storage in collection metadata for write-guard

### 4. Zotero Metadata Resolution (Language Field)

- [ ] Enhance `ZoteroCslJsonResolver.resolve()` with:
  - [ ] Extract `language` field from Zotero CSL-JSON metadata
  - [ ] Map Zotero language codes to OCR language codes
  - [ ] Pass language to converter for OCR language selection
  - [ ] Fallback hierarchy: Zotero language → explicit config → default

### 5. FastMCP Server Setup

- [ ] Create `fastmcp.json` configuration:
  ```json
  {
    "dependencies": ["python-dotenv"],
    "transport": "stdio",
    "entrypoint": "src.infrastructure.mcp.server:create_mcp_server"
  }
  ```
- [ ] Implement FastMCP server with tools:
  - [ ] `ingest_from_source`: Docling → chunk → embed → upsert
  - [ ] `query`: Dense-only search with model binding
  - [ ] `query_hybrid`: RRF fusion (dense + sparse)
  - [ ] `inspect_collection`: Collection stats and model bindings
  - [ ] `list_projects`: Project enumeration

### 6. Environment Variable Loading

- [ ] Add `python-dotenv` to dependencies via `uv add python-dotenv`
- [ ] Load `.env` file on startup (project root)
- [ ] Implement precedence: system env > `.env` file values
- [ ] Handle optional keys gracefully (fallback to defaults)
- [ ] Provide clear errors for required missing keys

### 7. Validation & Inspection Commands

- [ ] Implement `validate` command:
  - [ ] Tokenizer-to-embedding alignment check
  - [ ] Vector database connectivity
  - [ ] Collection presence and model locks
  - [ ] Payload indexes verification
  - [ ] Reference JSON file accessibility
  - [ ] Clear error messages with actionable guidance

- [ ] Implement `inspect` command:
  - [ ] Collection size and statistics
  - [ ] Model bindings (dense and sparse)
  - [ ] Payload schema sample
  - [ ] Index presence confirmation
  - [ ] Sample chunk data (optional)

## Testing Approach

### Unit Tests
- Domain models: Chunk ID determinism, quality filter thresholds
- Policy validation: Tokenizer alignment checks

### Integration Tests
- Docling conversion: Page maps, heading trees, OCR with language selection
- Qdrant operations: Named vectors, model binding, RRF fusion, on-disk storage
- Zotero metadata: Language field extraction, OCR language mapping
- FastMCP tools: Timeouts, error codes, project filtering

### Architecture Tests
- Dependency direction: Port implementations, no framework imports in domain/application
- Clean Architecture compliance

## Common Patterns

### Creating Collection with Named Vectors

```python
# In QdrantIndexAdapter
collection_name = f"proj-{project_id.replace('/', '-')}"
qdrant_client.create_collection(
    collection_name=collection_name,
    vectors_config={
        "dense": VectorParams(size=384, distance=Distance.COSINE),
        "sparse": SparseVectorParams()
    }
)
# Bind models
qdrant_client.set_model(collection_name, dense_model_id)
if sparse_model_id:
    qdrant_client.set_sparse_model(collection_name, sparse_model_id)
```

### Hybrid Query with RRF

```python
# RRF fusion is automatic when both models are bound
results = qdrant_client.query(
    collection_name=collection_name,
    query_text=query_text,  # Text-based (model binding handles embedding)
    query_filter=project_filter,
    using="dense"  # Named vector
)
# Qdrant automatically fuses with sparse results using RRF
```

### OCR Language Selection

```python
# Priority: Zotero metadata language → explicit config → default
ocr_languages = None
if citation_meta and citation_meta.language:
    ocr_languages = [map_zotero_to_ocr_lang(citation_meta.language)]
elif explicit_config:
    ocr_languages = explicit_config
else:
    ocr_languages = ['en', 'de']  # Default
```

## Next Steps

1. Complete Docling adapter implementations
2. Implement Qdrant named vector collection setup
3. Add FastMCP server with tool definitions
4. Integrate environment variable loading
5. Add validation and inspection commands
6. Write comprehensive integration tests

