# Feature Specification: Production-Ready Document Retrieval System

**Feature Branch**: `003-framework-implementation`  
**Created**: 2025-10-31  
**Status**: Draft  
**Input**: User description: "Milestone M3 - Framework-Specific Implementation Plan: Complete Docling conversion & heading-aware chunking; tighten Qdrant collections, payload indexes, and hybrid retrieval; finalize MCP behavior and contracts so editors/agents are predictable and safe."

## Clarifications

### Session 2025-10-31

- Q: What should the document conversion timeout limits be (per-document and per-page)? → A: 120 seconds per document, 10 seconds per page (very lenient, may cause long waits but ensures complex documents can be processed)
- Q: What should the chunk quality filter thresholds be (minimum length and signal-to-noise ratio)? → A: Minimum 50 tokens, signal-to-noise ratio ≥ 0.3 (moderate filtering, balances quality and coverage)
- Q: What should the default OCR language(s) be when no languages are configured? → A: English and German ('en', 'de') as default, but when Zotero metadata is available and contains a language key, use that language from Zotero metadata instead of the default

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Document Conversion with Structure Preservation (Priority: P1)

A researcher wants to ingest documents (including scanned PDFs and complex multi-column layouts) and have them converted with accurate page mapping, heading hierarchies, and normalized text so that chunks maintain precise location references and structural context.

**Why this priority**: Accurate document conversion with structure preservation is foundational. Without reliable page maps and heading trees, chunks cannot provide precise citations, and retrieval quality degrades. This must work consistently across document types including scanned materials.

**Independent Test**: Can be fully tested by ingesting a scanned PDF and a complex multi-column technical document, verifying that both produce valid page maps (page number to text span), consistent heading hierarchies, and normalized text with proper handling of line breaks and whitespace. Delivers the core capability of transforming raw documents into structured, citable content.

**Acceptance Scenarios**:

1. **Given** a researcher ingests a scanned PDF document, **When** the system processes it, **Then** it performs OCR using language from Zotero metadata (if available) or default languages (['en', 'de']), produces a page map mapping each page number to character spans, and logs any pages that could not be processed
2. **Given** a researcher ingests a document with multi-column layout, **When** the system processes it, **Then** it extracts a heading tree with hierarchical levels and page anchors for each heading, preserves code and math blocks without punctuation stripping, and normalizes whitespace while maintaining paragraph structure
3. **Given** a researcher ingests a document with hyphenated line breaks, **When** the system processes it, **Then** it repairs tokens split across lines only when appropriate and preserves intended paragraph breaks
4. **Given** a document conversion operation exceeds processing time limits, **When** timeouts occur (120s document limit or 10s per-page limit), **Then** the system logs diagnostic information with page numbers, completes what it can, and does not silently fail

---

### User Story 2 - Heading-Aware Chunking with Tokenizer Alignment (Priority: P1)

A researcher wants documents chunked using heading-aware segmentation that respects document structure, aligns with the embedding model's tokenizer for consistent sizing, and produces stable, deterministic chunk identifiers so that re-ingestion does not create duplicates.

**Why this priority**: Heading-aware chunking preserves semantic boundaries and improves retrieval quality. Tokenizer alignment ensures chunk sizes match embedding model expectations. Deterministic IDs prevent duplication on re-ingestion. These are all critical for production reliability.

**Independent Test**: Can be fully tested by chunking multiple PDFs and verifying that chunks have section headings, section paths (breadcrumb), page spans, token counts that match the embedding model's tokenizer, and deterministic IDs that remain stable across re-ingestion. Delivers predictable, high-quality chunks.

**Acceptance Scenarios**:

1. **Given** a researcher has a document with heading structure, **When** it is chunked, **Then** each chunk includes the closest section heading, a breadcrumb path from root to leaf headings, accurate page spans from the page map, and a monotonic chunk index
2. **Given** a researcher ingests documents, **When** chunks are created, **Then** token counts align with the embedding model's tokenizer family (e.g., MiniLM), chunk sizes respect configured maximums (approximately 450 tokens), and overlap is controlled (approximately 60 tokens)
3. **Given** a researcher re-ingests the same document with identical inputs, **When** chunks are created, **Then** chunk IDs are identical to previous ingestion, preventing duplicates in the vector store
4. **Given** a chunk is below minimum quality threshold (less than 50 tokens or signal-to-noise ratio < 0.3), **When** chunking occurs, **Then** the system filters it out with appropriate logging

---

### User Story 3 - Project-Isolated Vector Storage with Model Consistency (Priority: P1)

A researcher wants each project to have its own isolated vector collection with enforced embedding model consistency, indexed payload fields for fast filtering, and protection against accidental data mixing or model mismatches.

**Why this priority**: Project isolation prevents data leakage between research projects. Model consistency enforcement prevents corrupted embeddings. Indexed payload enables fast filtering. These are essential for production reliability and data integrity.

**Independent Test**: Can be fully tested by creating multiple projects with different embedding models, attempting to write chunks with mismatched models, and verifying that writes are blocked with clear errors, collections are properly isolated, and payload indexes exist for filtering. Delivers data integrity and operational safety.

**Acceptance Scenarios**:

1. **Given** a researcher creates a project with a specific embedding model, **When** the system creates the collection, **Then** it stores the model identifier in collection metadata, refuses writes if a different model is used (unless migration flag is set), and creates keyword indexes on project and tag fields
2. **Given** a researcher has multiple projects configured, **When** they query or ingest, **Then** operations are scoped to the specified project only, collections are isolated (e.g., named "proj-project-id"), and queries never return results from other projects
3. **Given** a researcher attempts to write chunks with an embedding model that differs from the collection's stored model, **When** the write is attempted, **Then** the system blocks it with an EMBEDDING_MISMATCH error and provides guidance on migration procedures
4. **Given** a researcher inspects a collection, **When** they view collection details, **Then** they see the stored embedding model identifier, payload schema with all required fields (project, source, zotero, doc, embed_model, version), and confirmation of which indexes are present

---

### User Story 4 - Hybrid Search with Query-Time Fusion (Priority: P2)

A researcher wants to perform searches that combine semantic similarity with keyword matching so that queries using exact terminology or semantic paraphrases both retrieve relevant chunks effectively.

**Why this priority**: Hybrid search improves recall and precision across different query styles. Query-time fusion (rather than storing sparse vectors) is more maintainable and flexible. This significantly improves retrieval quality for academic text with varied phrasing.

**Independent Test**: Can be fully tested by performing both dense-only and hybrid queries on a test document set, verifying that hybrid queries improve results for known lexical queries (exact terminology matches) while maintaining semantic search quality, and that results are properly scored and ranked. Delivers improved retrieval quality.

**Acceptance Scenarios**:

1. **Given** a researcher has ingested documents into a project, **When** they perform a hybrid search query, **Then** the system combines vector similarity scores with keyword relevance scores, returns up to 6 most relevant chunks, and hybrid results show improvement over dense-only for queries with exact terminology
2. **Given** a researcher enables hybrid search, **When** the collection is created, **Then** a full-text index is created over the chunk text field to support keyword matching
3. **Given** a researcher performs any query (dense or hybrid), **When** results are returned, **Then** all queries are automatically scoped to the specified project, results are limited to the configured top_k (default 6), and chunk text is trimmed to readable maximum length (e.g., 1,800 characters)
4. **Given** a researcher queries with tag filters, **When** results are returned, **Then** only chunks matching all specified tags (AND semantics) are included, and results are still scoped to the project

---

### User Story 5 - Predictable MCP Tools with Bounded Outputs (Priority: P2)

A developer using AI development environments wants to access document chunks through standardized MCP tools that have clear contracts, predictable timeouts, bounded outputs, and helpful error messages so that AI agents can reliably interact with the system.

**Why this priority**: MCP integration expands usability and enables AI workflows. Predictable contracts prevent agent confusion. Bounded outputs prevent context flooding. Timeouts and clear errors improve reliability. This is essential for production deployment in AI environments.

**Independent Test**: Can be fully tested by invoking MCP tools (ingest_from_source, query, query_hybrid, inspect_collection, list_projects) from an MCP client and verifying that they complete within timeout limits, return consistently formatted responses with trimmed content, enforce project filtering server-side, and provide clear error codes. Delivers reliable AI integration.

**Acceptance Scenarios**:

1. **Given** an MCP client calls the query tool, **When** it provides a project identifier and query text, **Then** it receives results within 8 seconds, each result includes trimmed text (render_text), score, citation metadata (citekey, page span), section information, and source metadata (title, DOI, URL)
2. **Given** an MCP client calls the ingest_from_source tool with a batch of documents, **When** documents are processed and chunks are written, **Then** the operation completes within timeout limits (15s), batches are processed efficiently (100-500 items), and errors (EMBEDDING_MISMATCH, INVALID_PROJECT) are returned with clear error codes
3. **Given** an MCP client calls any query tool, **When** it receives results, **Then** chunk text is trimmed to maximum readable length, project filtering is enforced server-side regardless of client parameters, and results never exceed the specified top_k limit
4. **Given** an MCP tool operation fails due to timeout, invalid project, or model mismatch, **When** the error occurs, **Then** it returns a standardized error taxonomy (INVALID_PROJECT, EMBEDDING_MISMATCH, INDEX_UNAVAILABLE, TIMEOUT) with human-readable messages

---

### User Story 6 - Robust Citation Metadata Resolution via pyzotero (Priority: P2)

A researcher wants document chunks automatically enriched with citation metadata (citekey, authors, year, DOI, tags, language) from their Zotero library using the pyzotero API, with Better BibTeX citekey extraction via JSON-RPC, reliable matching that handles variations, and gracefully handles missing metadata.

**Why this priority**: Citation metadata transforms chunks into citable sources. Using pyzotero provides direct API access to live Zotero data without manual exports. Better BibTeX integration ensures stable citekeys. High match rates (95%+) reduce manual work. Graceful handling of missing metadata ensures ingestion never fails due to metadata issues. This adds significant scholarly value.

**Independent Test**: Can be fully tested by ingesting documents with corresponding Zotero library entries and verifying that at least 95% match successfully using DOI-first then title-based matching, that unresolved documents are logged but still ingested, and that metadata (citekey from Better BibTeX, tags, collections, language) is correctly stored in chunk payloads. Delivers automatic citation-ready chunks.

**Acceptance Scenarios**:

1. **Given** a researcher has a configured Zotero library (library_id, library_type, API key or local=True), **When** they ingest documents, **Then** metadata is retrieved via pyzotero API using DOI exact match first, then normalized title matching (lowercase, stripped punctuation, collapsed spaces, fuzzy threshold ≥ 0.8 default), Better BibTeX citekey is extracted via JSON-RPC API when available, and matched metadata is stored in chunk payloads
2. **Given** a researcher ingests a document where metadata cannot be matched in Zotero, **When** the system processes it, **Then** it logs a MetadataMissing diagnostic but still ingests the document and chunks successfully, allowing the researcher to resolve metadata later
3. **Given** metadata matching completes, **When** chunks are stored, **Then** they include citation metadata fields (zotero.citekey (from Better BibTeX), zotero.tags[], zotero.collections[], zotero.language, source.title, source.authors[], source.year, source.doi/url) in the payload
4. **Given** Better BibTeX is installed and Zotero is running, **When** metadata is resolved, **Then** the system uses Better BibTeX JSON-RPC API (port 23119) to extract stable citekeys via `item.citationkey` method, falling back to pyzotero item data if Better BibTeX is unavailable
5. **Given** a researcher configures Zotero access via environment variables or local mode, **When** metadata resolution runs, **Then** the system uses pyzotero with appropriate configuration (library_id, library_type, api_key for remote, or local=True for local access), and gracefully handles API connection failures

---

### User Story 7 - System Validation and Operational Inspection (Priority: P3)

A researcher wants to validate that their system configuration is correct (tokenizer alignment, vector database connectivity, model consistency) and inspect collection contents to troubleshoot issues and verify data quality.

**Why this priority**: Validation catches configuration errors before they cause data corruption. Inspection enables troubleshooting and operational confidence. These capabilities reduce support burden and prevent silent failures.

**Independent Test**: Can be fully tested by running validate and inspect commands on a configured project and verifying that validation checks tokenizer-to-embedding alignment, vector database connectivity, collection presence, model lock verification, payload indexes, and Zotero library connectivity (pyzotero API connection), while inspect shows collection statistics and sample data. Delivers operational visibility.

**Acceptance Scenarios**:

1. **Given** a researcher runs the validate command, **When** validation executes, **Then** it checks that the chunking tokenizer family matches the embedding model's tokenizer, verifies vector database connectivity, confirms collections exist and have correct model locks, validates payload indexes are present, and checks that Zotero library is accessible via pyzotero API (or warns if not configured)
2. **Given** validation detects a tokenizer mismatch, **When** it fails, **Then** it provides clear guidance on how to fix the configuration to align tokenizers
3. **Given** a researcher runs the inspect command on a project, **When** inspection completes, **Then** it displays collection size (number of chunks), embedding model identifier, payload schema sample showing all required keys, list of indexes present, and optionally sample chunk data for verification
4. **Given** a researcher runs inspect and discovers a model mismatch, **When** it is detected, **Then** the system surfaces the mismatch clearly and provides guidance on migration paths (new collection suffix or migration flag)

---

### User Story 8 - Environment-Based Configuration for API Keys (Priority: P3)

A researcher or developer wants to configure API keys and sensitive settings (such as embedding service API keys, Qdrant API keys) using environment variables loaded from a `.env` file so that secrets are not stored in configuration files and can be easily managed per environment.

**Why this priority**: Environment-based configuration for API keys improves security by keeping secrets out of version-controlled configuration files. It also enables different settings for development, testing, and production environments. Some API keys are optional (e.g., OpenAI embeddings when using FastEmbed as default), so the system must handle missing keys gracefully.

**Independent Test**: Can be fully tested by creating a `.env` file with API keys, running system operations that require those keys, and verifying that keys are loaded correctly and operations work. For optional keys, verify that the system degrades gracefully when keys are missing. Delivers secure, flexible configuration management.

**Acceptance Scenarios**:

1. **Given** a researcher creates a `.env` file with API key variables (e.g., OPENAI_API_KEY, QDRANT_API_KEY), **When** the system starts, **Then** it automatically loads environment variables from the `.env` file in the project root, making them available to all components
2. **Given** a researcher configures an optional API key (e.g., OpenAI embeddings when default is FastEmbed), **When** the key is present, **Then** the system uses it for the corresponding service, and when the key is missing, **Then** the system falls back to default behavior without failing
3. **Given** a researcher runs operations that require API keys, **When** required keys are missing, **Then** the system provides clear error messages indicating which environment variables are needed and how to configure them
4. **Given** environment variables are loaded from `.env`, **When** they conflict with explicitly set environment variables, **Then** explicitly set environment variables take precedence, and `.env` files are never committed to version control (via .gitignore)

---

### Edge Cases

- What happens when a document conversion exceeds per-document or per-page timeouts? → System logs diagnostic information with page numbers when timeouts are exceeded (120s document limit or 10s per-page limit), completes what it can process, and continues with remaining pages rather than failing entirely
- How does system handle documents with image-only pages (no extractable text)? → System attempts OCR with language from Zotero metadata (if available) or default languages (['en', 'de']), or logs a diagnostic and skips those pages with a clear indication in the audit log
- How does system determine OCR language when Zotero metadata is available? → System uses the language field from Zotero metadata as the OCR language, falling back to default ['en', 'de'] if language field is missing or no Zotero metadata is matched
- What happens when tokenizer family differs from embedding model? → Validation command fails with clear error, and chunking should refuse to operate until configuration is corrected
- How does system handle concurrent writes to the same chunk (re-ingestion)? → Deterministic IDs ensure idempotency; duplicate points are not created, and audit log records added/updated/skipped counts
- What happens when a query would return more chunks than the top_k limit? → System enforces server-side limit, returns exactly top_k chunks (default 6), and trims text to maximum readable length to prevent context flooding
- How does system handle Zotero API connection failures or unavailable Better BibTeX? → System logs MetadataMissing for unmatched documents but continues ingestion; gracefully handles pyzotero API connection failures, Better BibTeX JSON-RPC unavailability (checks port 23119 with timeout), and falls back to pyzotero item data extra field parsing for citekey extraction; validation warns about Zotero configuration issues but does not block operations
- How does system extract Better BibTeX citekey when Better BibTeX is available? → System uses Better BibTeX JSON-RPC API (port 23119 for Zotero, 24119 for Juris-M) via `item.citationkey` method with the Zotero item key, falling back to parsing `item['data']['extra']` field for "Citation Key: citekey" pattern if JSON-RPC is unavailable
- What happens when hybrid search full-text index is missing but hybrid is requested? → System falls back to dense-only search with a diagnostic log, or validation flags the missing index as an error
- How does system handle Windows environments where native Docling is unavailable? → System provides clear CLI warnings suggesting WSL or Docker alternatives, documents supported path in setup guide, and gracefully degrades with helpful error messages
- How does system handle missing optional API keys (e.g., OpenAI embeddings when FastEmbed is default)? → System falls back to default behavior without failing; operations that require optional keys check for their presence and use defaults when absent
- How does system handle missing required API keys (e.g., Qdrant API key when authentication is required)? → System provides clear error messages indicating which environment variable is missing and how to configure it via `.env` file
- How does system handle environment variable precedence when both `.env` file and system environment have values? → System respects precedence: explicitly set system environment variables override `.env` file values, allowing per-session overrides

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST produce reliable page maps (page number → character span) for all supported document types to enable precise page span attribution in chunks
- **FR-002**: System MUST extract and preserve heading tree hierarchies with page anchors for each heading to enable section-aware chunking and context-rich retrieval
- **FR-003**: System MUST normalize document text (hyphen line-break repair, whitespace normalization) while preserving paragraph structure, code blocks, and math blocks
- **FR-004**: System MUST enable OCR for scanned documents with configurable language settings, using language from Zotero metadata (language key) when available, otherwise defaulting to ['en', 'de'] if not explicitly configured, and detect image-only pages with appropriate logging or skipping
- **FR-005**: System MUST enforce timeouts for document conversion (120 seconds per document, 10 seconds per page) with diagnostic logging when limits are exceeded
- **FR-006**: System MUST produce heading-aware chunks with section headings, section paths (breadcrumb), page spans, and monotonic chunk indices
- **FR-007**: System MUST align chunk tokenizer family with the embedding model's tokenizer family and validate this alignment before chunking operations
- **FR-008**: System MUST generate deterministic chunk identifiers using stable formulas (doc_id, page_span/section_path, embedding_model_id, chunk_idx) to prevent duplicates on re-ingestion
- **FR-009**: System MUST filter out low-quality chunks below minimum length (50 tokens) or signal-to-noise ratio (≥ 0.3) thresholds as defined by policy
- **FR-010**: System MUST create per-project isolated collections in the vector store (no shared mega-collection) with collection naming that clearly identifies the project
- **FR-011**: System MUST persist embedding model identifier in collection metadata upon creation and refuse writes if incoming model_id differs (unless migration flag is explicitly set)
- **FR-012**: System MUST create payload indexes on project identifier and tag fields at collection creation for fast filtering
- **FR-013**: System MUST create a full-text index over chunk text when hybrid search is enabled to support keyword matching
- **FR-014**: System MUST enforce mandatory project filtering for all queries at the server level (never trust client parameters alone) to prevent cross-project data leakage
- **FR-015**: System MUST cap query results to top_k limit (default 6) and trim chunk text to maximum readable length (e.g., 1,800 characters) to prevent context flooding
- **FR-016**: System MUST implement hybrid search using query-time fusion via named vectors with automatic RRF (Reciprocal Rank Fusion) when hybrid mode is enabled. This combines dense vector similarity with full-text keyword matching using Qdrant's named vector schema with model binding (set_model() and set_sparse_model()) for automatic RRF fusion
- **FR-017**: System MUST support payload filtering on tags with AND semantics (all specified tags must match) and optional section prefix filtering (starts-with on section_path)
- **FR-018**: System MUST write audit logs (JSONL format) for every ingest operation documenting added/updated/skipped/errors counts, duration, document IDs, and embedding model used
- **FR-019**: System MUST expose MCP tools (ingest_from_source, query, query_hybrid, inspect_collection, list_projects) with standardized names, minimal required arguments, and consistent response shapes
- **FR-020**: System MUST enforce per-tool timeouts (8-15 seconds) for MCP operations and return standardized error codes (INVALID_PROJECT, EMBEDDING_MISMATCH, HYBRID_NOT_SUPPORTED, INDEX_UNAVAILABLE, TIMEOUT) with human-readable messages
- **FR-021**: System MUST process batched writes efficiently (100-500 items per batch) in MCP ingest_from_source operations
- **FR-022**: System MUST retrieve citation metadata from Zotero library using pyzotero API (library_id, library_type, api_key for remote access, or local=True for local Zotero), matching by DOI exact match first, then normalized title matching (lowercase, stripped punctuation, collapsed spaces, fuzzy threshold ≥ 0.8 default) with at least 95% match rate on test sets
- **FR-022a**: System MUST extract Better BibTeX citekey via JSON-RPC API (port 23119 for Zotero, 24119 for Juris-M) when Better BibTeX is installed and Zotero is running, using `item.citationkey` method, falling back to pyzotero item data `extra` field parsing if Better BibTeX is unavailable
- **FR-023**: System MUST handle missing or unmatched metadata gracefully by logging MetadataMissing diagnostics but continuing ingestion without failure, and gracefully handle pyzotero API connection failures or unavailable Better BibTeX JSON-RPC API
- **FR-024**: System MUST validate tokenizer-to-embedding alignment, vector database connectivity, collection presence, model lock consistency, payload indexes, and Zotero library connectivity (pyzotero API connection) in the validate command
- **FR-025**: System MUST provide clear, actionable error messages when validation fails (e.g., tokenizer mismatch guidance, migration instructions for model changes)
- **FR-026**: System MUST display collection statistics (size, embedding model, payload keys, indexes) and sample chunk data in the inspect command
- **FR-027**: System MUST document Windows compatibility strategy (WSL or Docker) for Docling operations and provide CLI warnings when native Docling is unavailable. Warnings MUST include a single-line actionable remediation message (e.g., "Docling unavailable on Windows: use WSL or Docker. See docs/windows-setup.md") that directly guides users to resolution
- **FR-028**: System MUST support loading environment variables from a `.env` file in the project root using environment variable loading capabilities, making API keys and sensitive configuration accessible to all system components
- **FR-029**: System MUST handle optional API keys gracefully by falling back to default behavior when optional keys (e.g., OpenAI embeddings when FastEmbed is default, Better BibTeX JSON-RPC when unavailable) are missing, without failing or raising errors
- **FR-030**: System MUST provide clear error messages when required API keys are missing, indicating which environment variables are needed and how to configure them via `.env` file (e.g., ZOTERO_LIBRARY_ID, ZOTERO_API_KEY for remote access, or ZOTERO_LOCAL=true for local access)
- **FR-031**: System MUST respect precedence where explicitly set environment variables (from shell/system) override values from `.env` files

### Key Entities *(include if feature involves data)*

- **ConversionResult**: Represents a converted document with doc_id, structure (heading_tree and page_map), and plain_text. Structure includes hierarchical headings with levels and page anchors, and page_map maps page numbers to character spans in the text.
- **Chunk**: Represents a segmented piece of a document with deterministic id, doc_id, text content, page_span (start/end page numbers), section_heading (closest heading), section_path (breadcrumb array), chunk_idx (monotonic order), and metadata payload.
- **Collection**: Represents a project-specific vector store collection with metadata including embed_model (locked identifier), payload schema (project, source, zotero, doc, embed_model, version, optional fulltext), and indexes (keyword on project/tags, optional fulltext index).
- **Project Configuration**: Represents project settings including collection name, Zotero library configuration (library_id, library_type, api_key or local mode), embedding_model identifier, hybrid_enabled flag, and chunking policy parameters (max_tokens, overlap_tokens, heading_context, tokenizer_id).
- **Citation Metadata**: Represents reference information including zotero fields (citekey from Better BibTeX, tags array, collections array, language) and source fields (title, authors array, year, doi, url) used for enriching chunks and enabling proper citations. The language field (when present) is used to determine OCR language settings for scanned documents.
- **Zotero Configuration**: Represents Zotero library access settings including library_id (personal or group library identifier), library_type ('user' or 'group'), api_key (for remote access), and local mode flag (local=True for local Zotero instance via local API server). Better BibTeX JSON-RPC API configuration (port 23119 for Zotero, 24119 for Juris-M) when Better BibTeX is installed.
- **Environment Configuration**: Represents sensitive settings and API keys loaded from `.env` files, including optional embedding service API keys (e.g., OPENAI_API_KEY), Qdrant API keys (QDRANT_API_KEY), Zotero configuration (ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY, ZOTERO_LOCAL), and other service credentials that should not be stored in version-controlled configuration files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: System successfully converts at least 95% of test documents (including scanned PDFs and multi-column layouts) with valid page maps, consistent heading hierarchies, and normalized text where OCR or structure extraction is applicable
- **SC-002**: Chunking operations produce stable, deterministic chunk identifiers such that re-ingestion of identical documents results in zero duplicate chunks in the vector store
- **SC-003**: Heading-aware chunking maintains section context with at least 90% of chunks having valid section headings and section paths extracted from document structure
- **SC-004**: Collection isolation prevents 100% of cross-project data leakage (verified by querying one project never returns results from another project)
- **SC-005**: Embedding model consistency enforcement blocks 100% of writes with mismatched models (unless migration flag is set) and provides clear error messages
- **SC-006**: Hybrid search queries complete within 3 seconds for typical document collections (up to 10,000 chunks) and show measurable improvement over dense-only search for at least 20% of test queries that use exact terminology
- **SC-007**: MCP tools complete operations within specified timeout limits (8-15 seconds) in 95% of test cases, and all operations enforce project filtering server-side
- **SC-008**: Citation metadata matching achieves at least 95% match rate on standard test document sets when Zotero library is properly configured (pyzotero API access working, Better BibTeX available when citekey extraction is needed)
- **SC-009**: Validation command successfully identifies 100% of configuration errors (tokenizer mismatches, missing indexes, model inconsistencies) and provides actionable guidance for resolution
- **SC-010**: System handles ingestion failures gracefully with at least 90% of documents successfully processed even when individual pages timeout or metadata cannot be matched, logging diagnostics for manual review
- **SC-011**: System successfully loads environment variables from `.env` files for 100% of configured API keys when `.env` file exists, and gracefully handles missing optional keys by falling back to defaults without operation failures
- **SC-012**: System successfully connects to Zotero library via pyzotero API (remote or local) for 100% of properly configured libraries (library_id, library_type, api_key or local=True), and gracefully handles Better BibTeX JSON-RPC unavailability by falling back to pyzotero item data parsing
