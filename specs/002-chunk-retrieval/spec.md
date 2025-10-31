# Feature Specification: Project-Scoped Citable Chunk Retrieval

**Feature Branch**: `002-chunk-retrieval`  
**Created**: 2025-01-27  
**Status**: Draft  
**Input**: User description: "Milestone M2: Project-scoped citable chunk retrieval. Ingest long sources into heading-aware chunks. Store per-project vectors in Qdrant. Retrieve top-k chunks with project filters. Expose MCP tools for Cursor/Claude."

## Clarifications

### Session 2025-01-27

- Q: What access control and security model should be enforced (single-user local, multi-user with auth, or open access)? → A: Single-user local system (no authentication for CLI), optional authentication for MCP tools only
- Q: How should concurrent operations (simultaneous ingests, queries during ingest) be handled? → A: Optimistic concurrency (last write wins, idempotent deduplication prevents conflicts)
- Q: What data retention and deletion policy should be enforced (automatic retention, quota-based deletion, or manual-only)? → A: No automatic deletion; manual deletion commands required
- Q: Which hybrid search implementation strategy should be used (query-time fusion or ingest-time sparse vectors)? → A: Query-time hybrid (full-text search + vector fusion, no stored sparse vectors) - best practice for modern vector databases with large documents
- Q: Should batch operations (directory ingestion, reindexing) have explicit size limits? → A: No explicit limits; process all items in batch (user controls scope via directory selection)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest Documents into Project-Scoped Chunks (Priority: P1)

A researcher wants to ingest long-form documents (PDFs, books, web content) into their project so they can later search and retrieve relevant chunks with proper citations. The system must break documents into semantically meaningful chunks that preserve document structure (headings, page numbers, sections) and store them in a project-specific vector database.

**Why this priority**: This is the foundational capability that enables all downstream features. Without the ability to ingest and chunk documents properly, users cannot search or retrieve content. It must work reliably with accurate page spans and section paths.

**Independent Test**: Can be fully tested by ingesting two varied PDFs (scanned document and complex layout) and verifying that chunks are created with correct page spans, section headings, and are stored in the project's vector store. Delivers the core value of transforming long documents into searchable chunks.

**Acceptance Scenarios**:

1. **Given** a researcher has a project configured with an embedding model, **When** they ingest a PDF document, **Then** the system creates heading-aware chunks with page spans and section paths, generates embeddings, and stores them in the project's vector database
2. **Given** a researcher ingests a directory of documents, **When** the system processes all documents, **Then** each document is chunked separately with its own stable document ID and chunks are deduplicated if already indexed
3. **Given** a researcher ingests a document with complex layouts (columns, footnotes, headers), **When** the system processes it, **Then** chunks preserve logical reading order, maintain page number accuracy, and capture hierarchical section structure
4. **Given** a researcher runs an ingest operation, **When** the operation completes, **Then** an audit log is created documenting the number of chunks created, document IDs processed, embedding model used, and processing duration

---

### User Story 2 - Enrich Chunks with Citation Metadata (Priority: P2)

A researcher wants their document chunks automatically enriched with citation metadata (author, title, year, DOI, citation key) from their reference management system so that retrieved chunks include proper attribution information ready for citations.

**Why this priority**: Citation metadata transforms chunks from raw text into citable sources. This enables users to properly attribute information and build bibliographies without manual data entry. It builds on the ingest capability to add scholarly value.

**Independent Test**: Can be fully tested by ingesting documents with corresponding entries in a reference management export file and verifying that chunks are enriched with correct citation metadata (citekey, authors, year, DOI). Delivers the value of automatic citation-ready chunks.

**Acceptance Scenarios**:

1. **Given** a researcher has a reference management export file (CSL-JSON) with document metadata, **When** they ingest a document that matches an entry (by DOI or title), **Then** all chunks from that document are enriched with citation metadata including citekey, authors, year, and DOI
2. **Given** a researcher ingests a document where metadata cannot be matched, **When** the system processes it, **Then** chunks are still created and stored successfully, with a log entry indicating metadata was not found but providing actionable hints for resolution
3. **Given** a researcher has multiple documents with similar titles, **When** the system matches metadata, **Then** it prioritizes DOI matching over title matching, and uses configurable fuzzy matching thresholds for title-based matching
4. **Given** metadata enrichment completes, **When** chunks are stored, **Then** citation metadata is included in each chunk's stored payload and is available for all retrieval operations

---

### User Story 3 - Query and Retrieve Relevant Chunks (Priority: P2)

A researcher wants to search their project's document collection using natural language queries and retrieve the most relevant chunks that include proper citation information, page references, and section context so they can use the information in their work.

**Why this priority**: Search and retrieval is the primary user-facing value proposition. Users need to find relevant information from their ingested documents. It must respect project boundaries, return manageable result sets, and include all necessary citation context.

**Independent Test**: Can be fully tested by performing semantic search queries on an ingested project and verifying that results are limited to that project, include proper citation metadata, are trimmed to readable lengths, and contain page spans and section headings. Delivers immediate value of finding relevant information.

**Acceptance Scenarios**:

1. **Given** a researcher has ingested multiple documents into their project, **When** they search with a natural language query, **Then** they receive up to 6 most relevant chunks from only that project, each with trimmed text, citation metadata, page spans, and section headings
2. **Given** a researcher enables hybrid search (semantic + keyword), **When** they perform a query, **Then** results combine semantic similarity scores with keyword relevance scores to improve retrieval quality
3. **Given** a researcher queries with specific tags or filters, **When** they receive results, **Then** only chunks matching those filters are returned, and all results remain scoped to the specified project
4. **Given** a researcher receives query results, **When** they view each chunk, **Then** text is trimmed to a readable maximum length, citation information is formatted as "(citekey, pp. x–y)", and section context is clearly displayed
5. **Given** a researcher queries across multiple projects, **When** they search, **Then** they must specify a project identifier, and results never mix content from different projects

---

### User Story 4 - Access Chunks via MCP Tools (Priority: P2)

A developer or researcher using AI development environments (Cursor, Claude Desktop) wants to access their project's document chunks through standardized MCP (Model Context Protocol) tools so they can integrate document search into their AI-assisted workflow.

**Why this priority**: MCP integration expands the user base and enables integration with AI development tools. It provides a standardized API that works across different environments and makes the system accessible to users who prefer programmatic interfaces.

**Independent Test**: Can be fully tested by exposing MCP tools (store_chunks, find_chunks, query_hybrid, inspect_collection, list_projects) and verifying that they can be invoked from an MCP client, return properly formatted results with trimmed content, and enforce project scoping. Delivers integration value for AI workflows.

**Acceptance Scenarios**:

1. **Given** an MCP client connects to the system, **When** it calls the list_projects tool, **Then** it receives a list of all configured projects with their collection names and embedding models
2. **Given** an MCP client queries chunks, **When** it calls find_chunks with a project identifier and query text, **Then** it receives up to the requested number of chunks with trimmed text, citation metadata, and section information, all scoped to that project
3. **Given** an MCP client performs a hybrid search, **When** it calls query_hybrid, **Then** it receives results that combine semantic and keyword relevance, with operation completing within 15 seconds or returning a clear timeout error
4. **Given** an MCP client requests collection inspection, **When** it calls inspect_collection with a project identifier, **Then** it receives collection statistics (size, embedding model, payload schema sample, indexes present) without exposing sensitive data
5. **Given** any MCP tool operation encounters an error, **When** it fails, **Then** it returns a standardized error code (INVALID_PROJECT, EMBEDDING_MISMATCH, INDEX_UNAVAILABLE, TIMEOUT) with a human-readable error message

---

### User Story 5 - Inspect and Validate Project Index (Priority: P3)

A researcher or administrator wants to inspect their project's vector index to verify it is correctly configured, validate that tokenizers match embedding models, and ensure all dependencies (vector database, reference files) are available and consistent.

**Why this priority**: Operational visibility and validation ensure system reliability and catch configuration errors before they cause data corruption or retrieval failures. It enables users to troubleshoot issues and verify their setup is correct.

**Independent Test**: Can be fully tested by running inspect and validate commands on a configured project and verifying that they report collection statistics, embedding model information, and pass all validation checks (tokenizer alignment, vector database connectivity, reference file presence). Delivers operational confidence.

**Acceptance Scenarios**:

1. **Given** a researcher has an indexed project, **When** they run the inspect command, **Then** they see collection size, embedding model identifier, sample payload structure, and which indexes are present
2. **Given** a researcher runs the validate command, **When** validation executes, **Then** it checks and reports on: tokenizer family matches embedding model family, vector database is reachable, project collection exists, collection's embedding model matches configuration, required payload indexes exist, and reference metadata file is present
3. **Given** validation detects a mismatch (e.g., tokenizer doesn't match embedding model), **When** it reports the issue, **Then** it provides actionable guidance on how to resolve the mismatch
4. **Given** a researcher inspects a project with sample chunks, **When** they request a sample, **Then** they see example payloads that demonstrate the structure of stored chunks including citation metadata and document structure fields

---

### User Story 6 - Reindex Projects and Handle Model Migrations (Priority: P3)

A researcher wants to reindex their project documents (e.g., after updating chunking policies) or migrate to a new embedding model while preserving existing work and avoiding duplicate chunks or model mismatches.

**Why this priority**: Maintenance operations enable users to evolve their projects over time. Reindexing supports policy changes, and migration supports model upgrades. These must be safe operations that prevent data corruption and model mismatches.

**Independent Test**: Can be fully tested by reindexing a project directory and verifying that chunks are updated without duplicates, and by attempting to change embedding models and verifying that the system blocks the change unless explicitly authorized. Delivers maintenance and evolution capabilities.

**Acceptance Scenarios**:

1. **Given** a researcher has an indexed project, **When** they run reindex on the source directory, **Then** the system processes all documents, uses deterministic chunk IDs to avoid duplicates, and updates only chunks that have changed
2. **Given** a researcher attempts to ingest with a different embedding model than the project's existing model, **When** the operation runs, **Then** it is blocked with a clear error message explaining the mismatch, unless a migration flag is explicitly set
3. **Given** a researcher initiates a forced rebuild with migration, **When** the rebuild completes, **Then** a new collection is created (or existing one migrated), old data is preserved until migration is verified, and the system logs all migration steps
4. **Given** a researcher reindexes with a limit on document count, **When** reindexing runs, **Then** only the specified number of documents are processed, and the operation can be resumed to process remaining documents

---

### Edge Cases

- What happens when a document cannot be converted (corrupted file, unsupported format)? System logs error with document path, skips the document, and continues processing remaining documents in the batch
- What happens when metadata matching finds multiple potential matches? System uses DOI match if available, otherwise selects the best title match based on fuzzy threshold and logs the selection
- What happens when a query returns no results? System returns empty result set with a clear message, and does not fail the operation
- What happens when vector database is temporarily unavailable during ingest? System retries with exponential backoff up to a configurable limit, then fails with clear error and preserves partial progress
- What happens when chunk text exceeds maximum characters after trimming? System truncates at word boundaries and appends indicator (e.g., "..."), ensuring citation metadata remains complete
- What happens when project identifier doesn't exist during query? System returns INVALID_PROJECT error code with guidance on available projects
- What happens when embedding model changes but migration isn't authorized? System blocks the operation, logs the attempt, and provides instructions for safe migration path
- What happens when reference metadata file is missing or unreadable? System logs a warning, continues with ingest using available document metadata, and alerts user that citation enrichment may be incomplete
- What happens when chunking produces zero chunks for a document? System logs the document as processed with 0 chunks, includes it in audit log, and continues without failing the entire batch
- What happens when MCP tool operation exceeds timeout? System cancels the operation, returns TIMEOUT error code, and logs the incomplete operation for debugging
- What happens when multiple ingest operations run simultaneously on the same project? System allows concurrent operations using optimistic concurrency, with deterministic chunk IDs ensuring idempotent deduplication and last-write-wins semantics resolving any conflicts

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest long-form documents (PDFs, books, web content) and convert them into structured text with preserved page mapping and heading hierarchy
- **FR-002**: System MUST chunk documents using heading-aware segmentation that respects document structure and maintains logical reading order
- **FR-003**: System MUST generate deterministic chunk identifiers based on document ID, page span, section path, embedding model, and chunk index to enable idempotent operations
- **FR-004**: System MUST store chunks in project-scoped collections in the vector database, ensuring strict isolation between projects
- **FR-005**: System MUST enforce embedding model consistency by validating that new chunks use the same model as existing project chunks, unless migration is explicitly authorized
- **FR-006**: System MUST enrich chunks with citation metadata from reference management exports, prioritizing DOI matching, then normalized title matching with configurable fuzzy thresholds
- **FR-007**: System MUST handle missing or unmatched citation metadata gracefully by logging warnings and proceeding with ingest, ensuring chunks remain usable without full metadata
- **FR-008**: System MUST support semantic vector search with project filtering, returning up to a configurable maximum number of results (default 6)
- **FR-009**: System MUST support optional hybrid search using query-time fusion (full-text search combined with vector search), without storing separate sparse vectors, enabling efficient retrieval for large documents (1000+ pages) that exceed LLM context windows
- **FR-010**: System MUST trim retrieved chunk text to a configurable maximum character limit (enforced by retrieval policy) while preserving citation metadata and structure information
- **FR-011**: System MUST expose MCP tools (store_chunks, find_chunks, query_hybrid, inspect_collection, list_projects) with consistent interfaces, project scoping, and time-bounded operations (8-15 second timeouts)
- **FR-012**: System MUST return standardized error codes (INVALID_PROJECT, EMBEDDING_MISMATCH, HYBRID_NOT_SUPPORTED, INDEX_UNAVAILABLE, TIMEOUT) from MCP tools with human-readable error messages
- **FR-013**: System MUST create audit logs for each ingest operation documenting chunk counts, document IDs, embedding models used, and processing durations
- **FR-014**: System MUST support directory-based ingestion that recursively processes all documents in the specified directory without explicit batch size limits, respecting idempotency via deterministic chunk IDs (user controls scope through directory selection)
- **FR-015**: System MUST validate tokenizer family alignment with embedding model family before chunking operations
- **FR-016**: System MUST create required payload indexes (keyword indexes for project and tags, optional full-text index for hybrid search) when initializing project collections
- **FR-017**: System MUST provide inspection capabilities that report collection size, embedding model, payload schema samples, and index presence without exposing sensitive data
- **FR-018**: System MUST provide validation capabilities that check tokenizer-embedding alignment, vector database connectivity, collection existence, model consistency, index presence, and reference file availability
- **FR-019**: System MUST support reindexing operations that process all documents in the specified directory by default without batch size limits, update existing chunks without creating duplicates using deterministic IDs for deduplication, and optionally support user-specified document count limits for partial processing with resume capability
- **FR-020**: System MUST support forced rebuild operations that create new collections or migration paths when policy or model changes require structural updates
- **FR-021**: System MUST operate as a single-user local system without authentication requirements for CLI operations, with optional authentication support for MCP tools to control access from external clients
- **FR-022**: System MUST handle concurrent operations (simultaneous ingests, queries during ingest) using optimistic concurrency with last-write-wins semantics, relying on deterministic chunk IDs and idempotent deduplication to prevent conflicts and ensure consistency
- **FR-023**: System MUST NOT automatically delete chunks or projects based on age, storage quotas, or version limits; data deletion requires explicit user action via manual deletion commands (out of scope for this milestone)

### Key Entities

- **ConversionResult**: Represents the output of document conversion, containing a stable document identifier, document structure (heading tree hierarchy, page mapping from source to converted text), and the converted plain text content
- **Chunk**: Represents a semantically meaningful segment of a document, containing a deterministic identifier, source document identifier, text content, page span (start and end page numbers), section heading, hierarchical section path (breadcrumb), and chunk index within document
- **CitationMeta**: Represents bibliographic metadata for a document, containing citation key, document title, list of authors, publication year, DOI or URL, tags from reference management system, and collection names from reference management system
- **Project**: Represents a user's document collection scope, containing project identifier, associated vector database collection name, reference metadata file path, configured embedding model identifier, and hybrid search enablement flag
- **RetrievalResult**: Represents a query result item, containing chunk text (trimmed), relevance score, citation metadata reference, section heading, and page span

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can ingest two long PDF documents (≥50 pages each) with complex layouts and receive heading-aware chunks with accurate page spans and section paths in under 2 minutes total processing time
- **SC-002**: Citation metadata enrichment achieves ≥95% successful match rate on test documents with corresponding reference management entries, with unmatched items logged with actionable resolution hints
- **SC-003**: Semantic search queries return relevant results in under 1 second for projects containing up to 10,000 chunks, with results strictly limited to the specified project
- **SC-004**: Hybrid search queries (when enabled) combine semantic and keyword scores to return results in under 1.5 seconds, with results demonstrating improved relevance over semantic-only search in user evaluation
- **SC-005**: MCP tool operations (find_chunks, query_hybrid, inspect_collection) complete within 15 seconds for typical queries, with timeout errors occurring in <1% of operations under normal load
- **SC-006**: Validation checks (tokenizer alignment, database connectivity, collection existence, model consistency, index presence, reference file availability) execute in under 5 seconds and provide clear pass/fail status with actionable guidance for failures
- **SC-007**: Inspection operations report accurate collection statistics (size within 1% of actual, correct embedding model, complete payload schema sample) without exposing sensitive user data
- **SC-008**: Reindexing operations update existing chunks without creating duplicates, maintaining 100% idempotency across multiple reindex runs on the same document set
- **SC-009**: System prevents embedding model mismatches with 100% blocking rate for unauthorized model changes, requiring explicit migration flag for model transitions
- **SC-010**: Retrieved chunks include complete citation information (citekey, page span, section heading) in ≥99% of results for documents with available metadata, enabling ready-to-use citations in user workflows

## Assumptions

- System operates as a single-user local system where the user has full access to all projects via CLI without authentication, and MCP tools may optionally require authentication for external client access
- Users have access to their reference management system export files (CSL-JSON format) that can be kept synchronized with their document library
- Documents to be ingested include very large documents (books, technical manuals up to 1000+ pages) that exceed LLM context windows, requiring effective chunking with overlap to preserve context across boundaries
- Documents are in supported formats (PDF primary, with extensibility for other formats in future milestones)
- Users can configure projects with unique identifiers and maintain separate reference metadata files per project
- Vector database (Qdrant) is accessible either locally or via cloud service with appropriate authentication
- Users understand the importance of embedding model consistency and will follow migration procedures when changing models
- Document conversion may require OCR for scanned documents, and users accept processing time trade-offs for complex documents
- Chunking policies (max tokens, overlap, heading context) are configurable and users will tune them based on their document types and use cases
- Users primarily query with natural language and expect semantic similarity to surface relevant content even if exact keyword matches are absent
- Data deletion is out of scope for this milestone; users retain full control over data lifecycle and no automatic deletion policies are implemented
