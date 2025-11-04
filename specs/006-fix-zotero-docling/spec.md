# Feature Specification: Fix Zotero & Docling Performance and Correctness Issues

**Feature Branch**: `006-fix-zotero-docling`  
**Created**: 2025-01-27  
**Status**: Draft  
**Input**: User description: "Fix critical performance and correctness issues in Zotero integration and Docling document conversion: reduce Zotero API calls by 50%+ through command-scoped caching (browsing 10 items in <10 seconds), fix page and heading extraction bugs ensuring multi-page documents produce multiple chunks (15-40 for 20+ pages), add progress feedback for long-running operations, enable resource sharing (converter reuse), implement automatic model binding, improve HTTP logging, and enhance Windows profile detection."

## Clarifications

### Session 2025-01-27

- Q: Should caching be command-scoped or global? → A: Command-scoped (cleared after each CLI command) to avoid stale data and memory bloat
- Q: How should page extraction failures be handled? → A: Add diagnostic logging, fallback to single-page structure if extraction fails, continue processing with warning
- Q: Should progress reporting be opt-in or always-on? → A: Always-on for operations >5 seconds, with non-interactive mode detection for CI/automation
- Q: How should converter sharing work across processes? → A: Process-scoped (module-level cache), not cross-process (each process has its own converter instance)
- Q: Should model binding be automatic or manual? → A: Automatic on first query, stored in collection payload for subsequent queries
- Q: What verbosity level should HTTP logs use? → A: DEBUG level only, INFO level for important operations without HTTP details

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast Zotero Collection Browsing (Priority: P1) 🎯 MVP

A researcher wants to browse Zotero collections quickly without waiting for slow API responses, so they can explore their library structure and plan imports efficiently, reducing browsing time from 35+ seconds to under 10 seconds for 10 items.

**Why this priority**: Critical for user experience. Current browsing is too slow due to excessive API calls. This must be fixed before other improvements.

**Independent Test**: Browse a collection with 10 items and measure API call count and response time. Success: <10 seconds with at least 50% reduction in API calls compared to current implementation.

**Acceptance Scenarios**:

1. **Given** a researcher has a Zotero collection with 10 items, **When** they run `citeloom zotero browse-collection "Collection Name"`, **Then** the command completes in under 10 seconds, makes at least 50% fewer API calls than current implementation, and displays all items with metadata

2. **Given** a researcher browses a collection, **When** the command accesses collection info and item metadata, **Then** subsequent accesses within the same command use cached data (no redundant API calls), and cache is cleared after command completes

3. **Given** a researcher runs multiple browse commands, **When** each command executes, **Then** each command starts with a fresh cache (no cross-command cache pollution), ensuring data consistency

---

### User Story 2 - Accurate Document Conversion and Chunking (Priority: P1)

A researcher wants multi-page documents to be correctly converted and chunked, so that 20+ page documents produce 15-40 chunks (not just 1 chunk), with accurate page mapping and heading structure for proper citation and context.

**Why this priority**: Critical correctness issue. Current implementation produces only 1 chunk for large documents, losing important context and making retrieval ineffective.

**Independent Test**: Convert a known 20-page document with clear headings and verify: (1) page count = 20 (not 1), (2) heading tree is populated, (3) 15-40 chunks are created. Success: accurate page count, heading structure extracted, multiple chunks proportional to document size.

**Acceptance Scenarios**:

1. **Given** a researcher has a 20-page PDF document with headings, **When** they ingest the document, **Then** the system extracts all 20 pages (not just 1), builds a heading tree with hierarchical structure, and creates 15-40 chunks based on document content

2. **Given** a document conversion fails to extract pages, **When** the system processes the document, **Then** it logs diagnostic information about the failure, falls back to single-page structure with warning, and continues processing

3. **Given** a document has heading structure, **When** the system chunks the document, **Then** chunks include heading context (ancestor headings), and heading paths are preserved in chunk metadata

4. **Given** chunking produces only 1 chunk for a large document, **When** the system processes the document, **Then** it applies quality filtering correctly (not filtering all chunks), produces multiple chunks proportional to document size, and logs any filtering decisions

---

### User Story 3 - Progress Feedback for Long Operations (Priority: P2)

A researcher wants to see progress when operations take longer than expected, so they know the system is working and can estimate completion time, especially for large document imports or conversions.

**Why this priority**: Improves user experience for long-running operations. Users need feedback to know the system is working.

**Independent Test**: Run an operation that takes >5 seconds and verify progress indication appears. Success: progress visible within 5 seconds, shows current stage and estimated completion.

**Acceptance Scenarios**:

1. **Given** a researcher starts a document import that takes >5 seconds, **When** the operation runs, **Then** progress indication appears within 5 seconds, shows current stage (downloading, converting, chunking, embedding), and updates as operation progresses

2. **Given** a researcher runs a command in non-interactive mode (CI/automation), **When** progress would normally be shown, **Then** the system uses structured logging instead of progress bars, ensuring logs are parseable

---

### User Story 4 - Resource Sharing (Priority: P2)

A researcher wants subsequent commands to reuse expensive resources (like Docling converter), so that second and subsequent commands start faster, eliminating 2-3 second converter initialization overhead.

**Why this priority**: Improves performance for repeated operations. Converter initialization is expensive and should be cached.

**Independent Test**: Run two consecutive ingest commands and verify second command reuses converter. Success: second command starts immediately without converter initialization delay.

**Acceptance Scenarios**:

1. **Given** a researcher runs an ingest command, **When** the command completes, **Then** the converter instance is cached at module level (process-scoped), and subsequent commands in the same process reuse the cached converter

2. **Given** a converter is cached, **When** a new command needs a converter, **Then** it uses the cached instance (no initialization delay), and cache persists for the process lifetime

---

### User Story 5 - Automatic Model Binding (Priority: P2)

A researcher wants to query collections immediately after ingestion without manual model binding, so that queries work automatically without configuration steps.

**Why this priority**: Improves usability. Users shouldn't need to manually bind models after ingestion.

**Independent Test**: Ingest a document, then immediately query the collection. Success: query succeeds without manual model binding, model ID is automatically stored in collection payload.

**Acceptance Scenarios**:

1. **Given** a researcher ingests a document into a collection, **When** they query the collection, **Then** the query succeeds immediately without manual model binding, and the model ID used for ingestion is automatically bound to the collection

2. **Given** a collection has a model bound, **When** a query uses a different model, **Then** the system detects the mismatch, provides a clear error message with guidance, and prevents query execution

---

### User Story 6 - HTTP Logging Improvements (Priority: P3)

A researcher wants cleaner logs without HTTP request/response details cluttering the output, so they can see important information at INFO level without verbose HTTP details.

**Why this priority**: Improves log readability. HTTP details are useful for debugging but too verbose for normal use.

**Independent Test**: Run commands at INFO log level and verify HTTP details are not shown. Success: INFO level shows important operations without HTTP details, DEBUG level shows HTTP details when needed.

**Acceptance Scenarios**:

1. **Given** a researcher runs commands at INFO log level, **When** commands execute, **Then** logs show important operations (collection access, document processing) without HTTP request/response details, and HTTP details are only visible at DEBUG level

2. **Given** a researcher needs to debug HTTP issues, **When** they set log level to DEBUG, **Then** HTTP request/response details are logged, including URLs, status codes, and response sizes

---

### User Story 7 - Windows Profile Detection (Priority: P3)

A researcher on Windows wants Zotero profile detection to work automatically or provide clear guidance when auto-detection fails, so they can use local database access without manual configuration.

**Why this priority**: Improves Windows user experience. Auto-detection should work, but clear guidance is essential when it doesn't.

**Independent Test**: Run Zotero commands on Windows and verify profile detection works or provides clear guidance. Success: profile detected automatically, or clear error message with configuration instructions.

**Acceptance Scenarios**:

1. **Given** a researcher on Windows has Zotero installed, **When** they run Zotero commands, **Then** the system automatically detects the Zotero profile, or provides a clear error message with step-by-step configuration instructions if detection fails

2. **Given** profile auto-detection fails, **When** the system cannot find the profile, **Then** it provides a clear error message with: (1) explanation of what was checked, (2) manual configuration steps, (3) example configuration for citeloom.toml

---

## Functional Requirements

### FR-001: Command-Scoped Collection Caching
- Cache collection info within a single CLI command
- Cache is cleared after command completes
- Cache lookup before API call to reduce redundant requests

### FR-002: Item Metadata Caching
- Cache item metadata within command scope
- Reuse cached metadata when displaying items
- Clear cache after command completes

### FR-003: API Call Reduction
- Reduce API calls by at least 50% for collection browsing
- Measure and log API call counts for verification

### FR-006: Cache Cleanup
- Clear command-scoped caches after command completion
- Prevent cross-command cache pollution

### FR-012: Accurate Page Extraction
- Extract all pages from multi-page documents (not just page 1)
- Build accurate page map with page boundaries
- Handle page extraction failures gracefully

### FR-013: Heading Tree Extraction
- Extract hierarchical heading structure from documents
- Preserve heading context in chunks
- Handle heading extraction failures gracefully

### FR-014: Multiple Chunks for Large Documents
- Produce 15-40 chunks for 20+ page documents
- Apply quality filtering correctly (not filtering all chunks)
- Log chunking decisions for debugging

### FR-021: Quality Filtering
- Filter chunks based on minimum token count and signal-to-noise ratio
- Ensure reasonable chunk counts (not filtering all but one)
- Log filtering decisions

### FR-024: Chunk ID Uniqueness
- Generate unique chunk IDs
- Validate uniqueness with warning if collisions detected

### FR-007: Accurate Download Manifest
- Update manifest with actual downloaded filename
- Account for duplicate filename handling (_1, _2 suffixes)

### FR-019: Language-Aware OCR
- Use Zotero metadata language information for OCR when available
- Fallback to default languages if metadata unavailable

### FR-020: Suppress Unnecessary OCR Warnings
- Only show OCR warnings when actually needed
- Suppress warnings when OCR attempted but not needed

### FR-023: Windows Chunker Documentation
- Document Windows chunker limitations clearly
- Explain what works and what doesn't

---

## Success Criteria

1. **Performance**: Zotero browsing completes in <10 seconds for 10 items (down from 35+ seconds)
2. **API Calls**: At least 50% reduction in API calls for collection browsing
3. **Correctness**: 20-page documents produce 15-40 chunks with accurate page mapping
4. **Progress**: Progress indication visible within 5 seconds for operations >5 seconds
5. **Resource Reuse**: Second command starts immediately without converter initialization delay
6. **Model Binding**: Queries work immediately after ingestion without manual binding
7. **Logging**: INFO level logs are clean without HTTP details
8. **Windows**: Profile detection works or provides clear configuration guidance

---

## Out of Scope

- Cross-process resource sharing (process-scoped only)
- Global caching (command-scoped only)
- Breaking changes to existing APIs
- New features beyond fixes and performance improvements

---

## Dependencies

- Existing ZoteroImporterPort interface
- Existing DoclingConverterAdapter
- Existing RichProgressReporterAdapter
- Qdrant collections with payload support

---

## Assumptions

- Zotero API is accessible (local or remote)
- Docling is available (or manual chunking fallback works)
- Documents have reasonable structure (not corrupted)
- Users have appropriate permissions for Zotero database access


