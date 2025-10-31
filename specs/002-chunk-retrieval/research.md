# Research: Project-Scoped Citable Chunk Retrieval

**Date**: 2025-01-27  
**Feature**: 002-chunk-retrieval  
**Status**: Complete

This document consolidates research findings and technical decisions for the chunk retrieval milestone.

## 1. Docling Integration (Document Conversion & Chunking)

### Decision: Use Docling for heading-aware conversion and chunking

**Rationale**: 
- Docling provides structured document conversion with heading tree extraction and page mapping
- Supports OCR for scanned documents
- Heading-aware chunking preserves document structure and enables better retrieval context
- Active development and good Python integration

**Alternatives Considered**:
- **PyPDF2/pdfplumber**: Limited structure extraction, no heading tree
- **Unstructured.io**: Good structure but less fine-grained control over chunking
- **LangChain document loaders**: Higher-level abstraction, less control over page mapping

**Implementation Notes**:
- Enable OCR explicitly with language configuration
- Extract page map (page → text offsets) for accurate page spans
- Build heading tree with hierarchical structure
- Normalize whitespace and fix hyphen breaks
- Preserve code/math blocks where possible

**Key Requirements**:
- Return `ConversionResult` with `doc_id`, `structure` (heading tree + page map), `plain_text`
- Configure timeouts for pathological PDFs
- Log fallbacks for image-heavy pages

**References**:
- Docling documentation: Structure extraction, OCR configuration
- Best practices: Heading-aware chunking preserves semantic boundaries

---

## 2. Qdrant Hybrid Retrieval Strategy

### Decision: Query-time hybrid retrieval (full-text + vector fusion)

**Rationale**:
- Recommended best practice for modern vector databases (2024-2025)
- Simpler implementation (no sparse vector storage)
- Flexible scoring combination at query time
- Qdrant supports full-text indexing and hybrid search natively
- Better for large documents (1000+ pages) where storing sparse vectors would be expensive

**Alternatives Considered**:
- **Ingest-time sparse vectors (BM25/TF-IDF stored)**: More storage overhead, requires separate sparse index management, less flexible for scoring adjustments
- **Dense-only search**: Simpler but misses keyword relevance, less effective for technical documents with specific terminology

**Implementation Notes**:
- Create full-text index on `fulltext` payload field in Qdrant
- Use Qdrant's hybrid search API to combine BM25 (full-text) and vector similarity
- Simple fusion policy: weighted combination of scores (e.g., 0.3 * BM25 + 0.7 * vector)
- Document fusion policy in ADR

**Key Requirements**:
- Per-project collections (e.g., `proj-citeloom-clean-arch`)
- Store `embed_model` in collection metadata
- Write-guard: Block upserts if `embed_model` mismatches (unless migration flag)
- Payload schema: `project`, `source`, `zotero`, `doc`, `embed_model`, `version`, `fulltext`
- Indexes: Keyword on `project` and `zotero.tags`, full-text on `fulltext`

**References**:
- Qdrant documentation: Hybrid search, full-text indexing, payload filters
- Best practices: Query-time fusion for flexibility and storage efficiency

---

## 3. Zotero CSL-JSON Metadata Matching

### Decision: DOI-first matching with normalized title fallback

**Rationale**:
- DOI is most reliable identifier (exact match, persistent)
- Normalized title matching handles cases without DOI
- Better BibTeX auto-export provides stable citekeys
- CSL-JSON is standard format, independent of Zotero app runtime

**Alternatives Considered**:
- **Zotero API direct queries**: Requires Zotero app running, adds runtime dependency, slower
- **Manual metadata entry**: Not scalable, error-prone
- **External metadata APIs (CrossRef, etc.)**: Good for DOI lookup but doesn't provide user's custom citekeys/tags

**Implementation Notes**:
- Per-project CSL-JSON file: `references/<project>.json`
- Match order: DOI → normalized title (lowercase, strip punctuation, collapse spaces) → `source_hint`
- Fuzzy threshold for title matching (configurable, default 0.8)
- Extract: `citekey`, `title`, `authors[]`, `year`, `doi/url`, `tags[]`, `collections[]`
- Non-blocking: Log `MetadataMissing` but proceed with ingest

**Key Requirements**:
- Normalize titles consistently (lowercase, punctuation removal, whitespace collapse)
- Handle Unicode/diacritics in author names
- Support multiple editions with DOI priority
- Log confidence scores for fuzzy matches

**References**:
- CSL-JSON specification: Standard citation format
- Better BibTeX: Auto-export, stable citekeys
- Best practices: DOI-first matching for scholarly documents

---

## 4. Embedding Model & Tokenizer Alignment

### Decision: FastEmbed (MiniLM) default with tokenizer parity enforcement

**Rationale**:
- FastEmbed provides local embeddings (no API costs, privacy-preserving)
- MiniLM (`all-MiniLM-L6-v2`) is efficient and performs well for semantic search
- Tokenizer alignment ensures chunk size accuracy (tokens counted during chunking match embedding tokenization)
- Optional OpenAI adapter for users who prefer cloud embeddings

**Alternatives Considered**:
- **OpenAI text-embedding-ada-002/3**: Higher quality but API dependency and cost
- **Sentence transformers**: Similar to FastEmbed, good alternative
- **Custom embedding models**: Too complex for initial implementation

**Implementation Notes**:
- FastEmbed adapter surfaces `model_id` (e.g., `fastembed/all-MiniLM-L6-v2`)
- Chunking must use same tokenizer family as embeddings (MiniLM tokenizer for MiniLM embeddings)
- Validate tokenizer-embedding alignment in `validate` command
- Block ingest if mismatch detected (unless migration flag)
- Batch size tuning for throughput vs memory tradeoff

**Key Requirements**:
- `ChunkingPolicy.tokenizer_id` must match `EmbeddingPort.model_id` tokenizer family
- Validation check: Tokenizer family == Embedding model tokenizer family
- Document tokenizer requirements in policy configuration

**References**:
- FastEmbed documentation: Model selection, tokenization
- Best practices: Tokenizer alignment for accurate chunk sizing

---

## 5. MCP Tool Design Patterns

### Decision: Expose minimal, safe, time-bounded MCP tools

**Rationale**:
- MCP (Model Context Protocol) provides standardized integration for AI editors
- Small, focused tools are easier to reason about and prompt
- Time-bounded operations prevent hangs
- Strict project filtering prevents cross-project data leakage

**Implementation Notes**:
- Tool names: `store_chunks`, `find_chunks`, `query_hybrid`, `inspect_collection`, `list_projects`
- Output shaping: Always return trimmed `render_text` + metadata, never full text by default
- Timeouts: 8-15 seconds per operation
- Error taxonomy: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `INDEX_UNAVAILABLE`, `TIMEOUT`
- Batch limits: 100-500 chunks per `store_chunks` batch

**Key Requirements**:
- Enforce project filter in all retrieval operations
- Trim output text to `max_chars_per_chunk` policy
- Return citation-ready metadata: `citekey`, `page_span`, `section`, `section_path`, `doi/url`
- Time-bounded with clear timeout errors

**References**:
- MCP specification: Tool contracts, error handling
- Best practices: Minimal tools with clear boundaries

---

## 6. Chunking Strategy for Large Documents

### Decision: Heading-aware chunking with configurable overlap and context

**Rationale**:
- Large documents (1000+ pages) require effective chunking to fit in LLM context windows
- Heading-aware segmentation preserves semantic boundaries
- Overlap ensures context continuity across chunk boundaries
- Heading context in chunks improves retrieval relevance

**Implementation Notes**:
- Default policy: `max_tokens=450`, `overlap_tokens=60`, `heading_context=1-2` ancestors
- Tokenizer alignment critical for accurate sizing
- Quality filter: Drop ultra-short/noisy chunks (minimum functional length)
- Preserve section hierarchy in `section_path` breadcrumb

**Key Requirements**:
- Deterministic chunk IDs: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`
- Heading tree extraction from Docling
- Overlap at semantic boundaries (section ends) when possible
- Page span accuracy for citation

**References**:
- Best practices: Semantic chunking with overlap for retrieval quality
- Tokenizer alignment: Accurate token counting for chunk sizing

---

## 7. Configuration & Operations

### Decision: TOML-based configuration with environment variable overrides

**Rationale**:
- TOML is human-readable and supports structured configuration
- Per-project configuration blocks enable multiple project management
- Environment variables for sensitive data (API keys)
- Clear separation of concerns (paths, Qdrant, chunking, project-specific)

**Implementation Notes**:
- `citeloom.toml` structure:
  - `[project."<id>"]`: collection, references_json, embedding_model, hybrid_enabled
  - `[chunking]`: max_tokens, overlap_tokens, heading_context, tokenizer
  - `[qdrant]`: url, timeout_ms, create_fulltext_index
  - `[paths]`: raw_dir, audit_dir
- Pydantic settings for validation
- Secrets via environment variables only (never in config files)

**Key Requirements**:
- Validate configuration on load
- Provide sensible defaults
- Document all configuration keys

**References**:
- TOML specification: Configuration format
- Pydantic settings: Configuration validation

---

## 8. Audit & Observability

### Decision: JSONL audit logs with structured logging and correlation IDs

**Rationale**:
- JSONL enables easy parsing and aggregation
- Correlation IDs enable tracing across operations
- Structured logs improve debuggability
- Minimal logging reduces overhead

**Implementation Notes**:
- Audit JSONL per ingest: counts, durations, doc_id, embed_model, warnings
- Correlation ID per ingest run (UUID)
- Structured logs in adapters (no PII)
- Log levels: DEBUG (dev), INFO (prod)

**Key Requirements**:
- Correlation ID emitted in CLI output for testable tracing
- Audit logs in `var/audit/` directory
- No sensitive data in logs

**References**:
- Best practices: Structured logging, correlation IDs for distributed tracing
- JSONL format: Line-delimited JSON for streaming logs

---

## Summary

All research items resolved. Key decisions:
1. Docling for structured conversion and heading-aware chunking
2. Query-time hybrid retrieval (full-text + vector fusion)
3. DOI-first Zotero CSL-JSON matching
4. FastEmbed default with tokenizer alignment enforcement
5. Minimal, safe MCP tools with time-bounded operations
6. Heading-aware chunking with overlap for large documents
7. TOML configuration with environment variable overrides
8. JSONL audit logs with correlation IDs

**Status**: ✅ Ready for Phase 1 (Design & Contracts)

