# Data Model: Production-Ready Document Retrieval System

**Date**: 2025-10-31  
**Feature**: 003-framework-implementation  
**Status**: Design Complete

This document defines the domain entities, value objects, and their relationships for the production-ready document retrieval system, building on the foundation established in milestone M2.

## Domain Entities

### ConversionResult

Represents the structured output of document conversion, containing document structure, converted text, and conversion metadata.

**Fields**:
- `doc_id` (str): Stable document identifier (content hash or file path hash)
- `structure` (dict): Document structure containing:
  - `heading_tree` (dict): Hierarchical heading structure with levels, titles, page anchors, and parent-child relationships
  - `page_map` (dict[int, tuple[int, int]]): Mapping from page numbers to character span tuples `(start_offset, end_offset)` in converted text
- `plain_text` (str, optional): Converted plain text content with normalized whitespace and hyphen-repaired line breaks
- `ocr_languages` (list[str], optional): OCR languages used during conversion (if OCR was performed)

**Validation Rules**:
- `doc_id` must be stable and deterministic (same document → same doc_id)
- `structure` must contain both `heading_tree` and `page_map`
- `page_map` entries must map to valid offsets in `plain_text` (if provided)
- `heading_tree` must preserve hierarchical structure with page anchors

**State Transitions**: None (immutable value object)

---

### Chunk

Represents a semantically meaningful segment of a document with structure, citation metadata, and quality metrics.

**Fields**:
- `id` (str): Deterministic chunk identifier
  - Derived from: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)` via SHA256 hash (first 16 hex chars)
- `doc_id` (str): Source document identifier
- `text` (str): Chunk text content (normalized, heading-aware)
- `page_span` (tuple[int, int]): Page span `(start_page, end_page)` from page_map
- `section_heading` (str, optional): Immediate section heading containing this chunk
- `section_path` (list[str]): Hierarchical section path (breadcrumb from root to current section)
- `chunk_idx` (int): Sequential chunk index within document (monotonic)
- `token_count` (int, optional): Token count according to embedding model's tokenizer (for validation)
- `signal_to_noise_ratio` (float, optional): Quality metric (≥ 0.3 threshold)

**Validation Rules**:
- `id` must be deterministic (same inputs → same id)
- `page_span[0] <= page_span[1]` (valid page range)
- `section_path` is ordered list from root to leaf
- `chunk_idx >= 0`
- `text` length must be ≥ 50 tokens (quality filter threshold)
- `signal_to_noise_ratio >= 0.3` if provided (quality filter threshold)

**State Transitions**: None (immutable value object)

**Relationships**:
- Belongs to one `ConversionResult` (via `doc_id`)

---

### CitationMeta

Represents bibliographic metadata for a document, extracted from Zotero CSL-JSON with language information for OCR.

**Fields**:
- `citekey` (str): Citation key from Better BibTeX (e.g., `cleanArchitecture2023`)
- `title` (str): Document title
- `authors` (list[str]): List of author names
- `year` (int, optional): Publication year
- `doi` (str, optional): DOI identifier
- `url` (str, optional): URL if DOI not available
- `tags` (list[str]): Tags from Zotero collection
- `collections` (list[str]): Collection names from Zotero
- `language` (str, optional): Language code from Zotero metadata (e.g., 'en', 'de', 'en-US') - used for OCR language selection

**Validation Rules**:
- Either `doi` or `url` should be present (at least one identifier)
- `authors` is non-empty list
- `year` must be positive integer if provided
- `language` must be valid ISO language code if provided

**State Transitions**: None (immutable value object)

**Relationships**:
- Attached to `Chunk` entities (via chunk payload)

---

### Collection

Represents a Qdrant vector collection with named vectors and model bindings.

**Fields**:
- `name` (str): Collection name (e.g., `proj-citeloom-clean-arch`)
- `project_id` (str): Associated project identifier
- `dense_model_id` (str): Bound dense embedding model identifier (e.g., `fastembed/BAAI/bge-small-en-v1.5`)
- `sparse_model_id` (str, optional): Bound sparse model identifier (e.g., `Qdrant/bm25`, `prithivida/Splade_PP_en_v1`, `Qdrant/miniCOIL`)
- `vector_config` (dict): Named vector configuration:
  - `dense`: Dense vector parameters (size, distance metric)
  - `sparse`: Sparse vector parameters (if hybrid enabled)
- `on_disk_vectors` (bool): Whether vectors are stored on-disk (for large projects)
- `on_disk_hnsw` (bool): Whether HNSW index is on-disk
- `created_at` (datetime, optional): Collection creation timestamp

**Validation Rules**:
- `name` must be unique across all collections
- `dense_model_id` must match embedding model used for chunking (write-guard enforced)
- If `sparse_model_id` is set, hybrid search is enabled
- `on_disk_hnsw` requires `on_disk_vectors` to be true

**State Transitions**:
- Created: When project is first initialized
- Model migration: When `dense_model_id` changes (requires migration flag or new collection)

**Relationships**:
- Belongs to one `Project` (via `project_id`)

---

### Project

Represents a user's document collection scope with configuration and model bindings.

**Fields**:
- `id` (str): Project identifier (e.g., `citeloom/clean-arch`)
- `collection_name` (str): Qdrant collection name (e.g., `proj-citeloom-clean-arch`)
- `references_json` (Path): Path to CSL-JSON references file
- `embedding_model` (str): Dense embedding model identifier (e.g., `fastembed/BAAI/bge-small-en-v1.5`)
- `sparse_model` (str, optional): Sparse model identifier for hybrid search (default: `Qdrant/bm25`)
- `hybrid_enabled` (bool): Whether hybrid search is enabled for this project
- `chunking_policy` (ChunkingPolicy): Chunking configuration (max_tokens, overlap_tokens, heading_context, tokenizer_id)
- `retrieval_policy` (RetrievalPolicy): Retrieval configuration (top_k, hybrid_enabled, min_score, max_chars_per_chunk)

**Validation Rules**:
- `id` must be unique across all projects
- `collection_name` must be valid collection name (no special characters)
- `references_json` must be readable file path
- `embedding_model` must match tokenizer family used in chunking (enforced in validation)
- If `hybrid_enabled`, `sparse_model` must be set

**State Transitions**:
- Created: When project is configured in `citeloom.toml`
- Model migration: When embedding model changes (requires collection rebuild)

**Relationships**:
- Has one `Collection` (via `collection_name`)
- Contains many `Chunk` entities (via collection)

---

## Value Objects

### ChunkingPolicy

Represents chunking configuration policy with tokenizer alignment requirements.

**Fields**:
- `max_tokens` (int): Maximum tokens per chunk (default: 450)
- `overlap_tokens` (int): Overlap tokens between chunks (default: 60)
- `heading_context` (int): Number of ancestor headings to include (default: 1-2)
- `tokenizer_id` (str, optional): Tokenizer identifier (must match embedding model's tokenizer family)
- `min_chunk_length` (int): Minimum chunk length in tokens (default: 50)
- `min_signal_to_noise` (float): Minimum signal-to-noise ratio (default: 0.3)

**Validation Rules**:
- `max_tokens >= min_chunk_length`
- `overlap_tokens < max_tokens`
- `min_signal_to_noise >= 0.0 and <= 1.0`

---

### RetrievalPolicy

Represents retrieval configuration policy with project filtering and output limits.

**Fields**:
- `top_k` (int): Maximum number of results (default: 6)
- `hybrid_enabled` (bool): Whether hybrid search is enabled (default: True)
- `min_score` (float, optional): Minimum similarity score threshold
- `require_project_filter` (bool): Whether project filtering is mandatory (default: True, server-side enforcement)
- `max_chars_per_chunk` (int): Maximum characters in trimmed chunk text (default: 1,800)

**Validation Rules**:
- `top_k > 0`
- `max_chars_per_chunk > 0`

---

### OCRConfiguration

Represents OCR language configuration with Zotero metadata integration.

**Fields**:
- `languages` (list[str]): Language codes for OCR (e.g., ['en', 'de'])
- `source` (str): Source of language configuration:
  - `zotero_metadata`: From Zotero metadata `language` field
  - `explicit_config`: From explicit configuration
  - `default`: Default languages ['en', 'de']

**Validation Rules**:
- `languages` must contain valid ISO language codes
- Priority: zotero_metadata > explicit_config > default

---

## Qdrant Payload Schema

### Chunk Payload (Stable Schema)

The payload stored in Qdrant for each chunk point:

**Required Fields**:
- `project_id` (str): Project identifier (indexed)
- `doc_id` (str): Document identifier (indexed)
- `section_path` (list[str]): Hierarchical section path
- `page_start` (int): Start page number
- `page_end` (int): End page number
- `citekey` (str): Citation key from Zotero (indexed)
- `doi` (str, optional): DOI identifier
- `year` (int, optional): Publication year (indexed)
- `authors` (list[str]): Author names
- `title` (str): Document title
- `tags` (list[str]): Tags from Zotero (indexed)
- `source_path` (str): Source file path
- `chunk_text` (str): Full chunk text (full-text indexed if hybrid enabled)
- `heading_chain` (str): Stringified heading path (e.g., "Introduction > Section 1 > Subsection")
- `embed_model` (str): Embedding model identifier (for write-guard validation)
- `version` (str): Schema version identifier

**Legacy Compatibility**:
- Also supports nested structure: `project`, `source`, `zotero`, `doc` for backward compatibility with M2

**Indexes**:
- Keyword indexes: `project_id`, `doc_id`, `citekey`, `year`, `tags`
- Full-text index: `chunk_text` (if hybrid search enabled, tokenizer: `word` default, `prefix` optional)

---

## Relationships Summary

```
Project
  ├── has one Collection
  │     └── stored in Qdrant with named vectors (dense + sparse)
  │
  └── contains many Chunks (via Collection)
        ├── derived from ConversionResult
        │     └── converted from source document via Docling
        │
        └── enriched with CitationMeta
              └── matched from Zotero CSL-JSON references
```

**Identity & Uniqueness**:
- `Project.id`: Unique across all projects
- `Collection.name`: Unique across all collections (1:1 with Project)
- `Chunk.id`: Deterministic hash ensures uniqueness and idempotency
- `ConversionResult.doc_id`: Stable document identifier (content-based)

**Lifecycle**:
1. **Project Creation**: User configures project in `citeloom.toml` → Project entity created
2. **Collection Creation**: On first ingest → Collection created with named vectors and model bindings
3. **Document Ingestion**: Source document → Docling conversion → ConversionResult → Chunking → Chunks with CitationMeta
4. **Storage**: Chunks stored in Qdrant collection with payload schema
5. **Retrieval**: Query with project filter → Hybrid search (RRF) → Results with trimmed text

