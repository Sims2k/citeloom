# Research: Production-Ready Document Retrieval System

**Date**: 2025-10-31  
**Feature**: 003-framework-implementation  
**Status**: Complete

This document consolidates research findings and technical decisions for the framework-specific implementation milestone, focusing on production-hardening of Docling conversion, Qdrant collections, hybrid retrieval, and MCP integration.

## 1. Qdrant Named-Vector Schema (Dense + Sparse Hybrid)

### Decision: Use Qdrant named vectors with model binding for hybrid search (RRF fusion)

**Rationale**:
- Qdrant's named vector schema supports both dense and sparse vectors in a single collection
- Model binding via `set_model()` and `set_sparse_model()` enables text-based queries without manual embedding
- RRF (Reciprocal Rank Fusion) provides automatic fusion of dense + sparse results
- Recommended approach for modern vector databases (2024-2025 best practice)
- Better for large documents (1000+ pages) than storing separate sparse index

**Alternatives Considered**:
- **Query-time manual fusion (previous M2 approach)**: Works but requires manual score combination logic, less efficient than native RRF
- **Ingest-time sparse vectors stored separately**: More storage overhead, requires separate sparse index management, less flexible
- **Dense-only search**: Simpler but misses keyword relevance, less effective for technical documents

**Implementation Notes**:
- Create one collection per project with two named vectors:
  - `dense`: Bind FastEmbed model (e.g., `BAAI/bge-small-en-v1.5`) via `set_model()`
  - `sparse`: Bind sparse model (BM25/SPLADE/miniCOIL) via `set_sparse_model()`
- Qdrant client automatically fuses results using RRF when both vectors are set
- Default sparse model: `Qdrant/bm25` for classic lexical search
- Optional: `prithivida/Splade_PP_en_v1` for neural sparse, `Qdrant/miniCOIL` for BM25-like with semantics

**Key Requirements**:
- Per-project collections with named vectors configuration
- Model IDs stored in collection metadata for write-guard validation
- Payload schema: `project_id`, `doc_id`, `section_path`, `page_start`, `page_end`, `citekey`, `doi`, `year`, `authors[]`, `title`, `tags[]`, `source_path`, `chunk_text`, `heading_chain`
- Payload indexes on high-cardinality filters: `project_id`, `doc_id`, `citekey`, `year`, `tags`
- Full-text index on `chunk_text` with appropriate tokenizer (`word` default, `prefix` optional for prefix matches)

**Storage Optimization**:
- Enable `vectors.on_disk: true` and HNSW on-disk for large projects (memory savings)
- Optional: on-disk payload & payload indices for very large metadata sets
- Optimizer thresholds for segment merging at appropriate scale
- Scalar quantization (int8) with memmap for throughput-critical scenarios

**References**:
- Qdrant documentation: Named vectors, model binding, RRF fusion
- Qdrant FastEmbed integration: `set_model()`, `set_sparse_model()` API
- Best practices: Hybrid search with RRF for robust retrieval on technical texts

---

## 2. Docling v2 Conversion & Chunking Completion

### Decision: Complete Docling DocumentConverter and HybridChunker with production features

**Rationale**:
- Docling v2 provides robust document conversion with OCR support
- HybridChunker preserves document structure (headings, sections, page numbers)
- Heading-aware chunking improves retrieval quality over naive text splitting
- Structured output enables precise citation references

**Alternatives Considered**:
- **Placeholder implementation (M2)**: Insufficient for production use, lacks OCR, structure extraction
- **Alternative libraries (PyPDF2, pdfplumber)**: Limited structure extraction, no heading tree
- **Unstructured.io**: Good structure but less fine-grained control

**Implementation Notes**:

**DocumentConverter Configuration**:
- Use Docling v2 `DocumentConverter` with `allowed_formats`: PDF, DOCX, PPTX, HTML, images
- Enable OCR (Tesseract/RapidOCR) for scanned documents
- Per-project conversion profiles: OCR engine choice, image extraction, code/formula enrichment
- Timeouts: 120 seconds per document, 10 seconds per page (from clarifications)
- Language selection: Use Zotero metadata `language` field when available, otherwise default to ['en', 'de']
- Windows support: Document WSL/Docker path, surface precise error with remediation

**HybridChunker Configuration**:
- Tokenizer alignment: Use tokenizer matching dense embedding model (e.g., tiktoken for OpenAI-style, HF tokenizer for BGE/MiniLM)
- Target policy: 300-500 tokens per chunk (pre-embedding), 10-15% soft overlap
- Token window: Approximately 450 tokens max, 60 tokens overlap (from spec FR-006)
- Quality filtering: Minimum 50 tokens, signal-to-noise ratio ≥ 0.3 (from clarifications)
- Serialization: Use `contextualize()` to include `heading_chain` + figure/table captions
- Provenance: Map `page_start/page_end` and `section_path` from Docling hierarchy to payload

**Key Requirements**:
- Reliable page maps (page number → character span) for all document types
- Heading tree hierarchies with page anchors
- Text normalization (hyphen line-break repair, whitespace normalization) preserving code/math blocks
- OCR with language detection from Zotero metadata
- Deterministic chunk IDs: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`

**References**:
- Docling v2 documentation: DocumentConverter, HybridChunker, OCR configuration
- Docling examples: RapidOCR with custom models
- Best practices: Heading-aware chunking preserves semantic boundaries

---

## 3. FastEmbed Model Binding & Sparse Models

### Decision: Use FastEmbed with model binding for dense embeddings and sparse models

**Rationale**:
- FastEmbed integrates directly with Qdrant via `set_model()` for text-based queries
- Local embeddings (no API costs, privacy-preserving)
- Supports sparse models (BM25, SPLADE, miniCOIL) via `SparseTextEmbedding`
- Optional cross-encoder rerankers for high-precision queries

**Alternatives Considered**:
- **Manual embedding generation**: More code, less integration with Qdrant
- **OpenAI embeddings**: Higher quality but API dependency and cost
- **Sentence transformers**: Similar to FastEmbed, alternative if needed

**Implementation Notes**:
- Default dense model: `BAAI/bge-small-en-v1.5` (384-dim, fast, good baseline)
- Sparse model selection per project:
  - `Qdrant/bm25`: Classic lexical search
  - `prithivida/Splade_PP_en_v1`: Neural sparse (better semantics)
  - `Qdrant/miniCOIL`: BM25-like with semantic awareness
- List supported models via `SparseTextEmbedding.list_supported_models()`
- Optional cross-encoder rerankers via `TextCrossEncoder.list_supported_models()`
- Model write-guards: Store `embedding_model_id` in collection/app metadata, reject writes if model changes without migration

**Key Requirements**:
- Bind models at collection level using `set_model()` and `set_sparse_model()`
- Store model IDs in application metadata for write-guard validation
- Block ingest if project's collection is bound to different model (unless migration flag)
- Support model listing and selection per project

**References**:
- FastEmbed documentation: Model binding, sparse models, rerankers
- Qdrant FastEmbed integration: Text-based queries without manual embedding
- Best practices: Model governance prevents embedding drift

---

## 4. Zotero Integration via pyzotero with Better BibTeX (Language & Metadata)

### Decision: Use pyzotero API for direct Zotero library access with Better BibTeX JSON-RPC for citekey extraction

**Rationale**:
- **pyzotero** ([GitHub](https://github.com/urschrei/pyzotero)) is the standard Python client for Zotero API, providing direct access to live library data
- Eliminates need for manual CSL-JSON exports, enabling real-time metadata retrieval
- Supports both remote API access (library_id, library_type, api_key) and local access (local=True via Zotero local API server)
- Better BibTeX JSON-RPC API provides stable citekeys via `item.citationkey` method (port 23119 for Zotero, 24119 for Juris-M)
- Zotero metadata includes `language` field per document, improving OCR accuracy
- Better BibTeX citekeys are more reliable than auto-generated keys

**Alternatives Considered**:
- **CSL-JSON file exports**: Requires manual export/update cycles, not real-time, adds workflow friction
- **Reading zotero.sqlite directly**: High risk of database corruption when Zotero is running, not recommended
- **Zotero Web API only**: Works but misses Better BibTeX citekeys without JSON-RPC integration
- **Fixed default languages**: Less accurate for non-English/German documents

**Implementation Notes**:
- Use pyzotero to initialize Zotero client: `zotero.Zotero(library_id, library_type, api_key)` for remote, or `zotero.Zotero(library_id, library_type, api_key=None, local=True)` for local
- Configuration via environment variables: `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE` ('user' or 'group'), `ZOTERO_API_KEY` (remote), `ZOTERO_LOCAL=true` (local)
- Extract Better BibTeX citekey via JSON-RPC: Check if Better BibTeX is running (port 23119), use `item.citationkey` method with item key, fallback to parsing `item['data']['extra']` field for "Citation Key: citekey" pattern
- Extract `language` field from `item['data']['language']` in pyzotero item response
- Map Zotero language codes to OCR language codes (e.g., 'en-US' → 'en', 'de-DE' → 'de')
- Fallback hierarchy: Zotero metadata language → explicit config → default ['en', 'de']
- Normalize to OCR-supported language list (common: 'en', 'de', 'fr', 'es', 'it', etc.)
- Match by DOI first (exact match, normalized), then normalized title matching (fuzzy threshold ≥ 0.8)

**Metadata Acquisition Flow**:
1. Initialize pyzotero client with configuration (from env vars or zotero_config parameter)
2. Search items by DOI (if available in source_hint), then by title
3. If Better BibTeX is available, extract citekey via JSON-RPC API (`item.citationkey` method)
4. Fallback to parsing `item['data']['extra']` for "Citation Key: citekey" if JSON-RPC unavailable
5. Extract all metadata fields: citekey, title, creators → authors, year from date, DOI, URL, tags, collections, language
6. Map language to OCR codes and use for document conversion

**Fields to Extract from pyzotero**:
- `citekey`: From Better BibTeX JSON-RPC or `item['data']['extra']` field
- `title`: `item['data']['title']`
- `authors`: Format `item['data']['creators']` array (extract firstName, lastName, or name)
- `year`: Extract from `item['data']['date']` (e.g., '2023' from '2023-01-15')
- `doi`: `item['data'].get('DOI')` or `item['data'].get('doi')`
- `url`: `item['data'].get('url')` or `item['data'].get('URL')`
- `language`: `item['data'].get('language')` (maps to OCR language codes)
- `tags`: Extract from `item['data']['tags']` array (list of tag objects with 'tag' key)
- `collections`: Extract from `item['data'].get('collections', [])` or fetch via `zot.collections()` and match by collection keys
- Keep both raw Zotero JSON and normalized subset for payload

**Error Handling**:
- Gracefully handle pyzotero API connection failures (network issues, invalid credentials, library not found)
- Gracefully handle Better BibTeX JSON-RPC unavailability (Zotero not running, Better BibTeX not installed, port not accessible)
- Timeout Better BibTeX JSON-RPC requests (5-10 seconds)
- Log `MetadataMissing` warnings for unmatched documents but continue ingestion
- Return None if metadata cannot be resolved (non-blocking)

**References**:
- [pyzotero GitHub](https://github.com/urschrei/pyzotero) - Python client for Zotero API
- [pyzotero Documentation](https://pyzotero.readthedocs.io/) - Full API reference
- [Zotero Web API Documentation](https://www.zotero.org/support/dev/web_api/v3/basics) - Item fields, authentication
- [Better BibTeX JSON-RPC](https://retorque.re/zotero-better-bibtex/) - Citation key API
- [zotero-mcp](https://github.com/54yyyu/zotero-mcp) - Example Better BibTeX JSON-RPC integration
- Best practices: Language-aware OCR improves accuracy, direct API access reduces workflow friction

---

## 5. FastMCP Server Configuration & Tool Design

### Decision: Use FastMCP with `fastmcp.json` declarative configuration

**Rationale**:
- FastMCP 2.12+ uses `fastmcp.json` as canonical configuration (dependencies, transport, entrypoint)
- Declarative config enables consistent deployment and environment pre-builds with uv
- STDIO transport for Cursor/Claude Desktop integration
- Simpler than MCP SDK manual server setup

**Alternatives Considered**:
- **MCP SDK manual setup (M2 approach)**: Works but more boilerplate, less declarative
- **HTTP/SSE variants**: Future option, STDIO simpler for initial implementation

**Implementation Notes**:
- Create `fastmcp.json` as single source of truth
- Configure dependencies, transport (STDIO), entrypoint
- Enable `fastmcp run` with uv environment integration
- Tool surface: `ingest_from_source`, `query`, `query_hybrid`, `inspect`, `list_projects`
- Per-tool timeouts: 8-15 seconds (from spec FR-020)
- Standardized error codes: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `INDEX_UNAVAILABLE`, `TIMEOUT`
- Correlation IDs in responses for tracing

**Tool Contracts**:
- `ingest_from_source(project_id, source, options)`: Drive Docling → chunk → embed → upsert; return counts + model IDs + warnings
- `query(project_id, text, top_k, filters)`: Dense-only vector search
- `query_hybrid(project_id, text, top_k, filters)`: RRF fused dense+sparse (requires `set_model` and `set_sparse_model`)
- `inspect(project_id)`: Collection stats, sample payload schema, bound model IDs
- `list_projects()`: Discoverability

**Key Requirements**:
- Declarative `fastmcp.json` configuration
- STDIO transport for editor integration
- Time-bounded operations (8-15s per tool)
- Correlation IDs for observability
- Standardized error taxonomy with human-readable messages

**References**:
- FastMCP documentation: Project configuration, server setup
- Best practices: Declarative config enables consistent deployment

---

## 6. Environment Variable Management (.env Files)

### Decision: Use python-dotenv for `.env` file loading with precedence rules

**Rationale**:
- Keeps secrets out of version-controlled configuration files
- Enables per-environment configuration (dev/test/prod)
- Standard practice for Python applications
- python-dotenv integrates cleanly with uv dependency management

**Alternatives Considered**:
- **Configuration file secrets**: Security risk, version control exposure
- **System environment variables only**: Less convenient for local development
- **Secrets management services**: Overkill for single-user local system

**Implementation Notes**:
- Add `python-dotenv` via `uv add python-dotenv`
- Load `.env` file from project root on startup
- Environment variable precedence: System/shell env variables override `.env` file values
- Required API keys: Provide clear error messages when missing (e.g., QDRANT_API_KEY for authenticated Qdrant)
- Optional API keys: Gracefully degrade when missing (e.g., OPENAI_API_KEY, falls back to FastEmbed default)
- `.env` file must be in `.gitignore` (never committed)
- Configuration keys: `OPENAI_API_KEY` (optional), `QDRANT_API_KEY` (optional), `CITELOOM_CONFIG` (optional)

**Key Requirements**:
- Automatic `.env` file loading on startup
- Precedence: system env > `.env` file values
- Optional keys degrade gracefully
- Required keys provide clear error messages
- No secrets in version control

**References**:
- python-dotenv documentation: Environment variable loading
- Best practices: Security via environment variables

---

## 7. Storage & Performance Optimization (Large Projects)

### Decision: Enable on-disk vectors and HNSW for large projects

**Rationale**:
- Reduces RAM usage for collections with many vectors
- Enables handling of very large document libraries (1000+ pages, 10,000+ chunks)
- Trades some cold-query latency for memory efficiency
- Qdrant supports on-disk vectors and on-disk HNSW natively

**Alternatives Considered**:
- **In-memory only**: Limited by RAM, not scalable for large projects
- **Partial on-disk**: Less consistent behavior, more complex configuration

**Implementation Notes**:
- Enable `vectors.on_disk: true` for large projects (configurable threshold)
- Enable HNSW on-disk when vectors are on-disk
- Optional: on-disk payload & payload indices for very large metadata sets
- Optimizer thresholds: Configure memmap and indexing thresholds for segment merging
- Scalar quantization (int8): Consider for throughput-critical scenarios with memmap
- Per-project configuration: Allow users to specify storage strategy based on project size

**Key Requirements**:
- Configurable on-disk storage per project
- Performance targets: Query ≤3s for hybrid search on ≤10,000 chunks
- Memory optimization for large collections
- Maintain query performance within acceptable limits

**References**:
- Qdrant documentation: Storage optimization, on-disk vectors, quantization
- Best practices: Memory-efficient storage for large vector collections

---

## 8. Hybrid Retrieval Default Strategy

### Decision: Make hybrid (RRF) the default query mode with per-project sparse model selection

**Rationale**:
- Hybrid search improves recall and precision across query styles
- RRF fusion is automatic when using Qdrant model binding
- Per-project sparse model selection allows optimization (BM25 for lexical, SPLADE for neural, miniCOIL for hybrid)
- Optional cross-encoder rerank tier for maximum precision

**Alternatives Considered**:
- **Dense-only default**: Simpler but less effective for technical documents
- **Manual fusion (M2 approach)**: Works but less efficient than native RRF

**Implementation Notes**:
- Default: Hybrid (RRF) with top-k dense+sparse
- Return trimmed chunk text and `heading_chain` for context
- When keywords matter (e.g., "C4 diagram", "UoW"): Use BM25 or miniCOIL sparse model
- Optional reranking: Apply FastEmbed cross-encoder reranker to top N for maximum precision
- Per-project configuration: Allow sparse model selection (BM25 vs SPLADE vs miniCOIL)

**Key Requirements**:
- Hybrid search as default query mode
- RRF fusion via Qdrant model binding
- Per-project sparse model selection
- Optional cross-encoder reranking tier
- Performance: ≤3 seconds for hybrid queries on ≤10,000 chunks

**References**:
- Qdrant documentation: Hybrid search, RRF fusion, sparse models
- Best practices: Default to hybrid for robust retrieval

---

## 9. Production Readiness Patterns

### Decision: Implement comprehensive error handling, validation, and observability

**Rationale**:
- Production systems require robust error handling and validation
- Observability enables troubleshooting and operational confidence
- Standardized error codes improve user experience
- Validation catches configuration errors before data corruption

**Implementation Notes**:

**Error Taxonomy**:
- Standardized codes: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `INDEX_UNAVAILABLE`, `TIMEOUT`, `HYBRID_NOT_SUPPORTED`
- Human-readable error messages with actionable guidance
- Timeout handling: Per-tool timeouts (8-15s), clear timeout error messages

**Validation Command**:
- Check tokenizer-to-embedding alignment
- Verify vector database connectivity
- Confirm collections exist with correct model locks
- Validate payload indexes present
- Check reference JSON files accessible
- Provide clear guidance on fixing issues

**Inspect Command**:
- Display collection size (number of chunks)
- Show embedding model identifier
- Payload schema sample (all required keys)
- List indexes present
- Optional sample chunk data for verification

**Observability**:
- JSON logs with correlation IDs for every MCP call
- Record chunk counts, durations, model IDs
- Audit logs (JSONL format) per ingest operation
- Diagnostic logging for timeout/page failures with page numbers

**Key Requirements**:
- Comprehensive error handling with standardized codes
- Validation catches all configuration errors
- Inspection provides operational visibility
- Observability enables troubleshooting

**References**:
- Best practices: Production-ready error handling and observability
- Qdrant MCP server: Administrative tools and inspection patterns

