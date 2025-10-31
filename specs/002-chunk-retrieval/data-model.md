# Data Model: Project-Scoped Citable Chunk Retrieval

**Date**: 2025-01-27  
**Feature**: 002-chunk-retrieval  
**Status**: Design Complete

This document defines the core domain entities, value objects, and their relationships for the chunk retrieval feature.

## Domain Entities

### ConversionResult

Represents the structured output of document conversion, containing document structure and converted text.

**Fields**:
- `doc_id` (str): Stable document identifier (content hash or file path hash)
- `structure` (dict): Document structure containing:
  - `heading_tree` (dict): Hierarchical heading structure with spans
  - `page_map` (dict): Mapping from page numbers to text offsets in converted text
- `plain_text` (str, optional): Converted plain text content (may be omitted if only structure needed)

**Validation Rules**:
- `doc_id` must be stable and deterministic (same document → same doc_id)
- `structure` must contain both `heading_tree` and `page_map`
- `page_map` entries must map to valid offsets in `plain_text` (if provided)

**State Transitions**: None (immutable value object)

---

### Chunk

Represents a semantically meaningful segment of a document with structure and citation metadata.

**Fields**:
- `id` (str): Deterministic chunk identifier
  - Derived from: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`
- `doc_id` (str): Source document identifier
- `text` (str): Chunk text content
- `page_span` (tuple[int, int]): Page span `(start_page, end_page)`
- `section_heading` (str, optional): Immediate section heading containing this chunk
- `section_path` (list[str]): Hierarchical section path (breadcrumb from root to current section)
- `chunk_idx` (int): Sequential chunk index within document

**Validation Rules**:
- `id` must be deterministic (same inputs → same id)
- `page_span[0] <= page_span[1]` (valid page range)
- `section_path` is ordered list from root to leaf
- `chunk_idx >= 0`

**State Transitions**: None (immutable value object)

**Relationships**:
- Belongs to one `ConversionResult` (via `doc_id`)

---

### CitationMeta

Represents bibliographic metadata for a document, extracted from Zotero CSL-JSON.

**Fields**:
- `citekey` (str): Citation key from Better BibTeX (e.g., `cleanArchitecture2023`)
- `title` (str): Document title
- `authors` (list[str]): List of author names
- `year` (int, optional): Publication year
- `doi` (str, optional): DOI identifier
- `url` (str, optional): URL if DOI not available
- `tags` (list[str]): Tags from Zotero collection
- `collections` (list[str]): Collection names from Zotero

**Validation Rules**:
- Either `doi` or `url` should be present (at least one identifier)
- `authors` is non-empty list
- `year` must be positive integer if provided

**State Transitions**: None (immutable value object)

**Relationships**:
- Attached to `Chunk` entities (via chunk payload)

---

### Project

Represents a user's document collection scope with configuration.

**Fields**:
- `id` (str): Project identifier (e.g., `citeloom/clean-arch`)
- `collection` (str): Qdrant collection name (e.g., `proj-citeloom-clean-arch`)
- `references_json` (Path): Path to CSL-JSON references file
- `embedding_model` (str): Embedding model identifier (e.g., `fastembed/all-MiniLM-L6-v2`)
- `hybrid_enabled` (bool): Whether hybrid search is enabled for this project

**Validation Rules**:
- `id` must be unique across all projects
- `collection` must be valid collection name (no special characters)
- `references_json` must be readable file path
- `embedding_model` must match tokenizer family used in chunking

**State Transitions**:
- Created: Project initialized with collection
- Updated: Configuration changes (requires validation)
- Migration: Embedding model change (requires `--force-rebuild` flag)

**Relationships**:
- Contains many `Chunk` entities (via collection)
- References one CSL-JSON file (via `references_json`)

---

## Value Objects

### ProjectId

Project identifier value object.

**Fields**:
- `value` (str): Project identifier string

**Validation Rules**:
- Non-empty string
- Format: `namespace/name` (e.g., `citeloom/clean-arch`)

**Immutability**: Yes

---

### CiteKey

Citation key value object (from Better BibTeX).

**Fields**:
- `value` (str): Citation key string

**Validation Rules**:
- Non-empty string
- Alphanumeric with optional underscores/dashes

**Immutability**: Yes

---

### PageSpan

Page span tuple value object.

**Fields**:
- `start` (int): Start page number
- `end` (int): End page number

**Validation Rules**:
- Both `start` and `end` must be positive integers
- `start <= end`

**Immutability**: Yes

---

### SectionPath

Hierarchical section path value object (breadcrumb).

**Fields**:
- `segments` (list[str]): Ordered list of section segments from root to leaf

**Validation Rules**:
- Non-empty list
- Each segment is non-empty string
- Ordered from root (index 0) to leaf (index -1)

**Immutability**: Yes

---

## Application Layer DTOs

### IngestRequest

Request DTO for document ingestion use case.

**Fields**:
- `source_path` (str): Path to source document or directory
- `project_id` (str): Target project identifier
- `references_path` (str): Path to CSL-JSON references file
- `embedding_model` (str): Embedding model identifier

**Validation Rules**:
- `source_path` must be readable file or directory
- `project_id` must be valid ProjectId format
- `references_path` must be readable JSON file

---

### IngestResult

Result DTO for document ingestion use case.

**Fields**:
- `chunks_written` (int): Number of chunks successfully written to index
- `documents_processed` (int): Number of documents processed
- `duration_seconds` (float): Processing duration
- `embed_model` (str): Embedding model used
- `warnings` (list[str]): Non-fatal warnings (e.g., metadata not found)

**Validation Rules**:
- `chunks_written >= 0`
- `documents_processed >= 0`
- `duration_seconds >= 0.0`

---

### QueryRequest

Request DTO for chunk query use case.

**Fields**:
- `project_id` (str): Project identifier (mandatory filter)
- `query_text` (str): Natural language query text
- `top_k` (int): Maximum number of results (default 6, max configurable)
- `hybrid` (bool): Whether to use hybrid search (default False)
- `filters` (dict, optional): Additional filters (e.g., tags)

**Validation Rules**:
- `project_id` must be valid ProjectId format
- `query_text` must be non-empty
- `top_k` must be positive integer (typically ≤ 6)
- Filters must be valid Qdrant filter format

---

### QueryResult

Result DTO for chunk query use case.

**Fields**:
- `items` (list[QueryResultItem]): List of retrieved chunks with metadata

**Validation Rules**:
- `len(items) <= top_k` from request
- Each item has trimmed text and citation metadata

---

### QueryResultItem

Individual chunk result item.

**Fields**:
- `text` (str): Trimmed chunk text (≤ max_chars_per_chunk)
- `score` (float): Relevance score (dense or hybrid)
- `citekey` (str, optional): Citation key
- `section` (str, optional): Section heading
- `page_span` (tuple[int, int], optional): Page span `(start, end)`
- `section_path` (list[str], optional): Section path breadcrumb
- `doi` (str, optional): DOI identifier
- `url` (str, optional): URL if DOI not available

**Validation Rules**:
- `text` length ≤ `max_chars_per_chunk` policy
- `score >= 0.0` (normalized relevance score)
- Either `doi` or `url` present if citation metadata available

---

## Domain Errors

### EmbeddingModelMismatch

Raised when embedding model doesn't match project's stored model.

**Fields**:
- `project_id` (str): Project identifier
- `expected_model` (str): Expected embedding model
- `provided_model` (str): Provided embedding model

---

### ProjectNotFound

Raised when project identifier doesn't exist.

**Fields**:
- `project_id` (str): Non-existent project identifier

---

### HybridNotSupported

Raised when hybrid search is requested but not enabled for project.

**Fields**:
- `project_id` (str): Project identifier
- `reason` (str): Why hybrid is not supported

---

### MetadataMissing

Raised when citation metadata cannot be resolved (non-blocking warning).

**Fields**:
- `doc_id` (str): Document identifier
- `hint` (str): Actionable hint for resolution

---

## Relationships Summary

```
Project (1) ──< contains >── (*) Chunk
Project (1) ──< references >── (1) CSL-JSON file
ConversionResult (1) ──< produces >── (*) Chunk
Chunk (*) ──< enriched_with >── (0..1) CitationMeta
```

## Validation Rules Summary

1. **Deterministic IDs**: Chunk IDs must be deterministic (same inputs → same ID)
2. **Model Consistency**: Embedding model must match tokenizer family
3. **Project Filtering**: All retrieval operations must include project filter
4. **Text Trimming**: Retrieved chunk text must be ≤ max_chars_per_chunk
5. **Top-k Limit**: Query results must be ≤ top_k (default 6)
6. **Page Span Validity**: Page spans must have start ≤ end
7. **Section Path Order**: Section paths must be ordered from root to leaf

