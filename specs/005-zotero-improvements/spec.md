# Feature Specification: Comprehensive Zotero Integration Improvements

**Feature Branch**: `005-zotero-improvements`  
**Created**: 2025-01-27  
**Status**: Draft  
**Input**: User description: "Implement comprehensive Zotero integration improvements: local SQLite database access for offline browsing and instant structure access, full-text reuse from Zotero to avoid redundant OCR processing, PDF annotation extraction and indexing as separate vector points, embedding model governance with friendly diagnostics, incremental deduplication based on content hashes, enhanced library browsing tools (offline-capable), flexible source router for local/web source selection, and payload enrichment with Zotero keys for targeted queries. All improvements follow patterns from zotero-mcp and enhance performance, offline capability, and retrieval quality."

## Clarifications

### Session 2025-01-27

- Q: Should annotation indexing be enabled by default or opt-in? → A: Opt-in via configuration flag (`include_annotations=false` by default) to avoid storage bloat until users explicitly enable
- Q: Should `auto` mode be the default strategy for source selection? → A: Default to `auto` mode (smart selection) after Phase 1 rollout; initially `web-first` for backward compatibility during migration period
- Q: How should full-text quality be validated before reuse? → A: Check that fulltext is not empty, has reasonable length (minimum 100 characters), and covers expected document structure; fallback to Docling if quality checks fail
- Q: What happens when Docling conversion fails for a document type it doesn't support? → A: Fail the individual document with a clear error message, log it, continue importing remaining documents in the collection
- Q: How should mixed provenance text (some pages from Zotero fulltext, some from Docling) be structured for chunking? → A: Sequential concatenation in page order (fulltext pages followed by Docling pages) into a single continuous text stream for chunking, with page-level provenance metadata maintained for traceability
- Q: Is SQLite immutable read-only mode safe when Zotero is actively writing to the database? → A: Safe: immutable read-only mode creates a snapshot view, concurrent Zotero writes do not affect reads (SQLite guarantees isolation)
- Q: How should content hash collisions be handled when 1MB preview hash matches but files may differ? → A: Verify file metadata (mtime + size) as secondary check: if hash matches but metadata differs, treat as different document and re-process
- Q: How should source router handle missing files in local-first mode: per-file fallback or collection-level? → A: Per-file fallback: check each file individually, use local if available, download via Web API if missing, track source per file in manifest (allows mixed sources in same collection)
- Q: How should annotation extraction handle Web API rate limits during import? → A: Retry annotation extraction with exponential backoff (3 retries), skip attachment annotations if all retries fail, continue import, log warning (prevents import blocking while maximizing annotation capture)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Offline Library Browsing and Instant Collection Access (Priority: P1)

A researcher wants to browse their Zotero library structure, view collections, and explore items instantly without internet connection or API rate limits, so they can plan imports and verify collection contents before starting large batch operations, even when working offline or on slow networks.

**Why this priority**: This is foundational for all other improvements. Local SQLite access enables zero-latency browsing, offline capability, and eliminates API rate limits. Without this, researchers must wait for API responses and cannot work offline. This must work reliably across all platforms (Windows/macOS/Linux) and handle Zotero running concurrently.

**Independent Test**: Can be fully tested by detecting Zotero profile on local machine, opening SQLite database in read-only immutable mode, listing collections with hierarchy and item counts, browsing a specific collection to see first 10 items with attachment counts, and verifying all operations complete instantly without network calls. Delivers instant library exploration capability and offline functionality.

**Acceptance Scenarios**:

1. **Given** a researcher has Zotero installed with a library containing collections and items, **When** they run `citeloom zotero list-collections`, **Then** the system detects the Zotero profile automatically (platform-aware), opens `zotero.sqlite` in immutable read-only mode, displays all collections with hierarchy (parent-child relationships), shows item counts per collection, and completes in under 2 seconds without any network calls

2. **Given** a researcher wants to browse items in a collection, **When** they run `citeloom zotero browse-collection "Collection Name"`, **Then** the system lists the first 20 items with titles, item types, attachment counts, and tags, works offline without internet connection, and completes instantly using local database queries

3. **Given** Zotero desktop application is running while CiteLoom accesses the database, **When** a researcher browses collections, **Then** the system opens the database in immutable read-only mode (no locks), successfully reads data from a consistent snapshot view without interference from concurrent Zotero writes (SQLite guarantees isolation), and continues operating normally even if Zotero is actively syncing or writing to the database

4. **Given** a researcher's machine has multiple Zotero profiles, **When** the system detects profiles, **Then** it uses the default profile (marked in profiles.ini) or the first available profile, and allows override via configuration if needed

5. **Given** a researcher's Zotero database is locked or corrupted, **When** the system attempts local database access, **Then** it provides a clear error message explaining the issue ("Zotero database is locked. Close Zotero or use Web API mode.") and gracefully falls back to Web API if configured

6. **Given** a researcher is on Windows/macOS/Linux, **When** the system detects the Zotero profile, **Then** it correctly identifies the platform-specific profile path (`%APPDATA%\Zotero\Profiles\` on Windows, `~/Library/Application Support/Zotero/Profiles/` on macOS, `~/.zotero/zotero/Profiles/` on Linux) and finds the database

---

### User Story 2 - Fast Import with Full-Text Reuse (Priority: P1)

A researcher wants to import documents from Zotero collections significantly faster by reusing text that Zotero has already extracted, so they can process large libraries (100+ documents) in minutes rather than hours, especially for documents that Zotero has already processed with PDF indexing or text extraction. However, even with fulltext reuse, documents must still be chunked, embedded, and indexed - only the conversion/OCR step is skipped.

**Why this priority**: Full-text reuse provides 50-80% speedup for documents already in Zotero by skipping the time-consuming Docling conversion/OCR step. However, chunking is always required because large books would exceed LLM context windows if indexed as single units. Without full-text reuse, every document goes through full OCR/conversion even when Zotero has already extracted text. Chunking, embedding, and indexing steps remain necessary for all documents regardless of fulltext source.

**Independent Test**: Can be fully tested by importing a collection containing 20 documents where 15 have Zotero fulltext available, verifying that those 15 use fast path (skipping Docling conversion but still chunked, embedded, and indexed), measuring total import time, and comparing to baseline without full-text reuse. Delivers significant time savings while maintaining proper chunking for all documents (large books must be chunked for LLM context window limits).

**Acceptance Scenarios**:

1. **Given** a researcher imports a collection where most documents have Zotero fulltext available, **When** the import runs with `prefer_zotero_fulltext=true`, **Then** the system checks the Zotero `fulltext` table for each attachment, uses fulltext when available and quality is acceptable (non-empty, reasonable length), skips Docling conversion/OCR for those documents, but still processes them through chunking, embedding, and indexing steps (required because large documents must be chunked for LLM context window limits), and completes the import 50-80% faster than without full-text reuse

2. **Given** a document has Zotero fulltext but it's incomplete or low-quality (too short, missing pages), **When** the system evaluates fulltext, **Then** it falls back to Docling conversion for missing pages, uses Zotero fulltext for available pages, concatenates pages sequentially in order (fulltext pages followed by Docling pages) into a single continuous text stream, maintains page-level provenance metadata in audit trail showing which pages came from which source, and processes the complete concatenated text through chunking, embedding, and indexing

3. **Given** a researcher imports with full-text reuse enabled, **When** the import completes, **Then** the audit log or manifest indicates which documents used Zotero fulltext vs Docling conversion, allowing researchers to verify the fast path was used correctly

4. **Given** a document has no Zotero fulltext available (Zotero couldn't index it or never attempted indexing), **When** the system checks for fulltext, **Then** it automatically and seamlessly falls back to Docling conversion pipeline, processes the document (PDF, image, or other supported format) through full Docling extraction, and treats this as normal processing flow without errors, warnings, or user intervention

5. **Given** a collection contains mixed document types (PDFs with fulltext, PDFs without fulltext, images, other formats), **When** the system imports with `prefer_zotero_fulltext=true`, **Then** it uses Zotero fulltext where available, automatically falls back to Docling for all documents without fulltext (regardless of file type: PDF, images, Office documents), processes all documents successfully, and maintains consistent quality across both paths

6. **Given** Zotero's fulltext table shows a document was never indexed (no entry exists) or indexing failed, **When** the system processes the attachment, **Then** it immediately falls back to Docling conversion without attempting to use fulltext, processes the document through complete pipeline (Docling conversion → chunking → embedding → indexing), and treats this as expected behavior for documents Zotero couldn't index

7. **Given** a large book (500+ pages) has Zotero fulltext available, **When** the system processes it with fulltext reuse, **Then** it uses Zotero fulltext to skip Docling conversion, but still chunks the fulltext into appropriately sized chunks (respecting max_tokens and overlap settings), generates embeddings for each chunk, and indexes chunks separately (not as a single large document), ensuring the document can be used in LLM context windows without exceeding limits

---

### User Story 3 - High-Quality Retrieval with Annotation Indexing (Priority: P2)

A researcher wants their PDF annotations (highlights, comments, notes) from Zotero to be indexed as separate searchable points in CiteLoom, so they can query "show me only annotations" or "find annotations about machine learning" and get high-signal results from their highlighted insights, improving the quality of retrieved context for citations and research.

**Why this priority**: Annotations contain the highest-signal content - researchers highlight and comment on the most important passages. Indexing annotations separately enables focused queries that surface key insights, dramatically improving retrieval quality for LLM context and citations. This feature differentiates CiteLoom from basic document search.

**Independent Test**: Can be fully tested by importing a collection with PDFs containing Zotero annotations (highlights and comments), enabling annotation indexing, verifying annotations are fetched via Web API, normalized correctly (page, quote, comment, color, tags), indexed as separate vector points with `type:annotation` tag, and can be queried with "only annotations" filters. Delivers enhanced retrieval quality through annotation-aware search.

**Acceptance Scenarios**:

1. **Given** a researcher imports a collection with PDFs containing Zotero annotations (highlights, comments), **When** they enable annotation indexing via `include_annotations=true`, **Then** the system fetches annotation items via Web API (`itemType=annotation` filtered by parent attachment), normalizes each annotation (page number, quoted text, comment, color, tags), indexes them as separate vector points with `type:annotation` tag and metadata (`zotero.item_key`, `zotero.attachment_key`, `zotero.annotation.page`), and allows querying with annotation filters

2. **Given** a researcher queries CiteLoom with annotation filter enabled, **When** they search for "machine learning applications", **Then** the system returns results including both regular document chunks and annotation points, with annotations clearly marked, and annotations can be filtered to show only annotation results if desired

3. **Given** annotation indexing is disabled (default), **When** a researcher imports a collection, **Then** the system skips annotation extraction entirely, imports proceed normally without annotation-related API calls, and no storage is used for annotation points

4. **Given** a PDF has annotations but Web API is unavailable or rate limited, **When** annotation indexing is enabled, **Then** the system retries annotation extraction with exponential backoff (3 retries with increasing delays), skips attachment annotations if all retries fail, logs a warning indicating which attachments had annotation extraction failures, continues with document import without those annotations, and does not fail the entire import

---

### User Story 4 - Reliable Re-Imports with Incremental Deduplication (Priority: P2)

A researcher wants to re-import a collection without re-processing unchanged documents, so that if they add new items to a Zotero collection or update import settings, they can re-run the import and only process new or changed documents, saving significant time and computational resources on large libraries.

**Why this priority**: Large collections may take hours to process. Re-importing should be fast and only process what changed. Without deduplication, researchers waste time re-processing hundreds of unchanged documents. This makes iterative imports practical and enables efficient collection updates.

**Independent Test**: Can be fully tested by importing a collection of 50 documents, then re-importing the same collection with one new document added, verifying that the 50 unchanged documents are detected via content hash comparison and skipped (no re-extraction, re-embedding, or re-storage), only the new document is processed, and total re-import time is proportional to new documents only. Delivers efficient incremental updates.

**Acceptance Scenarios**:

1. **Given** a researcher imports a collection, **When** they re-import the same collection later, **Then** the system computes content hashes (first 1MB of file content + file size + embedding model + policy version) for each document, compares against stored fingerprints in manifest, verifies file metadata (mtime + size) as secondary check when hash matches, skips processing for documents where both hash and metadata match, treats documents as different if hash matches but metadata differs (and re-processes them), processes only new or changed documents, and completes re-import in time proportional to changed documents only

2. **Given** a researcher changes embedding model or chunking policy between imports, **When** they re-import a collection, **Then** the system detects the policy change (hash includes policy version), treats all documents as changed (since policy affects embeddings), re-processes all documents with new policy, and updates fingerprints with new policy version

3. **Given** a document file is modified (new version downloaded), **When** the system checks for changes, **Then** it detects the content hash difference, treats the document as changed, re-processes it through full pipeline, and updates the fingerprint in manifest

4. **Given** a researcher imports a collection twice with identical settings and unchanged files, **When** the second import runs, **Then** all documents are detected as unchanged, all are skipped, import completes in under 30 seconds (manifest validation only), and no duplicate chunks are created in the vector index

---

### User Story 5 - Flexible Source Selection with Smart Routing (Priority: P2)

A researcher wants to control whether CiteLoom uses local Zotero database or Web API for imports, with automatic fallback between sources, so they can optimize for speed (local), completeness (web), or let the system choose automatically based on availability, ensuring imports work reliably regardless of network conditions or Zotero state.

**Why this priority**: Different scenarios call for different data sources. Local DB is fast but may miss unsynced files. Web API is complete but slower and rate-limited. Automatic routing provides best of both worlds. This flexibility makes CiteLoom work reliably across varied user environments and network conditions.

**Independent Test**: Can be fully tested by configuring source router with `local-first` strategy, attempting import where some files exist locally and some don't, verifying local files use local DB, missing files fall back to Web API download, and source markers in manifest correctly indicate which files came from which source. Delivers flexible and reliable import across scenarios.

**Acceptance Scenarios**:

1. **Given** a researcher configures `mode=local-first`, **When** they import a collection, **Then** the system checks each file individually via local database first, uses local paths directly for files found locally, downloads via Web API for files missing locally (per-file fallback), tracks source per file in manifest (`source: "local"` or `source: "web"` for each attachment), and allows mixed sources within the same collection

2. **Given** a researcher configures `mode=web-first`, **When** they import a collection, **Then** the system uses Web API primarily, falls back to local database if rate limits are encountered or specific files are unavailable via API, and optimizes for completeness over speed

3. **Given** a researcher configures `mode=auto`, **When** they import a collection, **Then** the system detects availability of local database and Web API, intelligently selects source based on what's available and fastest, provides fallback if primary source fails, and logs the selection strategy used

4. **Given** a researcher configures `mode=local-only` for debugging, **When** they import a collection, **Then** the system uses only local database, fails with clear error if local database unavailable, does not attempt Web API fallback, and provides diagnostic information about what's missing locally

5. **Given** a researcher configures `mode=web-only`, **When** they import a collection, **Then** the system uses only Web API, does not attempt local database access, and works as current implementation (backward compatible mode)

---

### User Story 6 - Enhanced Library Exploration with Offline Browsing (Priority: P3)

A researcher wants to explore their Zotero library structure comprehensively before importing, including viewing collection hierarchies, browsing tags, seeing recent items, and previewing collection contents, all working offline using local database access, so they can make informed decisions about what to import without requiring internet connection.

**Why this priority**: Better import planning and verification. Researchers can explore library structure, verify collection names, check item counts, and preview contents before starting large imports. Offline capability ensures this works regardless of network availability. This is lower priority than core import functionality but significantly improves user experience.

**Independent Test**: Can be fully tested by running collection listing, browsing a collection, listing tags with usage counts, viewing recent items, and verifying all operations work offline using local database, complete quickly (under 5 seconds), and provide useful information for import planning. Delivers comprehensive library exploration capability.

**Acceptance Scenarios**:

1. **Given** a researcher runs `citeloom zotero list-collections`, **When** the command executes, **Then** the system displays hierarchical collection structure (showing parent-child relationships), includes item counts for each collection, works offline using local database, and formats output clearly with indentation for subcollections

2. **Given** a researcher runs `citeloom zotero browse-collection "Collection Name"`, **When** the command executes, **Then** the system displays first 20 items with titles, item types, PDF attachment counts, tags, and publication years if available, works offline, and completes in under 3 seconds

3. **Given** a researcher runs `citeloom zotero list-tags`, **When** the command executes, **Then** the system displays all tags used in the library with usage counts (number of items with each tag), works offline, and allows filtering or searching tags

4. **Given** a researcher runs `citeloom zotero recent-items`, **When** the command executes, **Then** the system displays 10 most recently added items sorted by `dateAdded` descending, shows titles, dates, and collection membership, works offline, and helps researchers discover new additions to import

---

### User Story 7 - Better Traceability with Zotero Key Enrichment (Priority: P3)

A researcher wants to query CiteLoom by Zotero item or attachment keys, so they can find all chunks derived from a specific Zotero paper or attachment, enabling precise traceability from search results back to Zotero items and supporting targeted queries like "show me everything from this paper."

**Why this priority**: Enables targeted queries and better debugging. Researchers can trace chunks back to source Zotero items, query by specific papers, and understand relationships between imported documents and original Zotero entries. This is lower priority as it's an enhancement rather than core functionality, but improves usability significantly.

**Independent Test**: Can be fully tested by importing a collection, verifying that chunk payloads include `zotero.item_key` and `zotero.attachment_key`, testing queries filtered by these keys return correct chunks, and verifying indexes enable fast lookups. Delivers enhanced query capabilities and traceability.

**Acceptance Scenarios**:

1. **Given** a researcher imports documents from Zotero, **When** chunks are stored in vector index, **Then** each chunk payload includes `zotero.item_key` (parent Zotero item) and `zotero.attachment_key` (source PDF attachment), these fields are indexed for fast queries, and queries can filter by these keys

2. **Given** a researcher wants to find all chunks from a specific Zotero paper, **When** they query with `zotero.item_key="ABC123"` filter, **Then** the system returns all chunks derived from that Zotero item, regardless of which attachment or collection they came from, and results are returned quickly via index lookup

3. **Given** a researcher wants to debug an import issue for a specific attachment, **When** they query with `zotero.attachment_key="XYZ789"` filter, **Then** the system returns all chunks from that specific attachment, enabling verification that the attachment was processed correctly

---

### User Story 8 - Clear Diagnostics for Embedding Model Mismatches (Priority: P3)

A researcher wants clear, actionable error messages when they attempt to use a different embedding model than what a collection was created with, so they understand why writes are blocked, what model is currently bound, and how to resolve the mismatch (either switch back to original model or migrate with explicit flag).

**Why this priority**: Prevents confusion and accidental recall degradation. Write-guard already exists but diagnostics are technical. Friendly error messages help researchers understand the issue and take correct action. This is lower priority as it improves existing functionality rather than adding new capabilities.

**Independent Test**: Can be fully tested by creating a collection with one embedding model, attempting to write chunks with a different model, verifying that a friendly error message appears explaining the mismatch and suggesting solutions, and confirming that `--force-rebuild` flag bypasses the guard when migration is intended. Delivers better user experience for model governance.

**Acceptance Scenarios**:

1. **Given** a collection was created with embedding model "BAAI/bge-small-en-v1.5", **When** a researcher attempts to write chunks using model "sentence-transformers/all-MiniLM-L6-v2", **Then** the system detects the mismatch, blocks the write, and displays a friendly error message: "Collection 'my-project' is bound to embedding model 'BAAI/bge-small-en-v1.5'. You requested 'sentence-transformers/all-MiniLM-L6-v2'. Use `reindex --force-rebuild` to migrate to the new model, or switch back to 'BAAI/bge-small-en-v1.5'."

2. **Given** a researcher runs `citeloom inspect project my-project --show-embedding-model`, **When** the command executes, **Then** the system displays the embedding model currently bound to the collection, shows provider information if available, and helps researchers verify model configuration before imports

3. **Given** a researcher explicitly wants to migrate to a new embedding model, **When** they use `--force-rebuild` flag, **Then** the system bypasses the write-guard, allows writes with the new model, updates the collection's bound model, and logs the migration for audit purposes

---

## Edge Cases

- What happens when Zotero database is locked by another process (Zotero syncing, backup tool)?
- What happens when Zotero profile path doesn't exist or is inaccessible?
- What happens when Zotero database schema version is incompatible with expected structure?
- What happens when a document has Zotero fulltext but it's corrupted or malformed?
- What happens when Zotero couldn't index a document (no fulltext entry exists in database)?
- What happens when a document type is unsupported by Zotero indexing (images, Office documents, etc.)?
- What happens when Zotero indexing failed for a PDF (error in Zotero's processing)?
- What happens when a collection contains mix of indexed and non-indexed documents?
- What happens when annotation extraction fails for some attachments but succeeds for others?
- What happens when content hash matches but file metadata (mtime/size) differs (file was modified then restored)? → ANSWERED: Treat as different document and re-process (hash collision protection via metadata verification)
- What happens when source router cannot determine availability (network issues, API key invalid)?
- What happens when a collection has both imported and linked attachments, and some linked files don't exist locally?
- What happens when multiple Zotero profiles exist and none is marked as default?
- What happens when fulltext quality check thresholds need adjustment for different document types (very short papers vs long books)?
- What happens when Docling conversion is required for a document type that Docling doesn't support? → ANSWERED: Individual document fails with clear error message, logged, collection import continues for remaining documents
- What happens when annotation indexing is enabled but Zotero Web API rate limits are encountered? → ANSWERED: Retry annotation extraction with exponential backoff (3 retries), skip attachment annotations if all retries fail, log warning, continue import without blocking
- What happens when a document's policy version changes mid-import (user updates chunking settings)?
- What happens when local database access works but storage directory path resolution fails (moved files, broken links)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support reading Zotero SQLite database in immutable read-only mode (`?immutable=1&mode=ro`) to access collections, items, and attachments without network calls
- **FR-002**: System MUST automatically detect Zotero profile directory per platform (Windows: `%APPDATA%\Zotero\Profiles\`, macOS: `~/Library/Application Support/Zotero/Profiles/`, Linux: `~/.zotero/zotero/Profiles/`)
- **FR-003**: System MUST parse `profiles.ini` to find default profile or use first available profile if no default is marked
- **FR-004**: System MUST implement `ZoteroImporterPort` interface using local SQLite queries for: `list_collections()`, `get_collection_items()`, `get_item_attachments()`, `get_item_metadata()`, `list_tags()`, `get_recent_items()`
- **FR-005**: System MUST resolve attachment file paths distinguishing imported files (`linkMode=0`: `{storageDir}/storage/{itemKey}/{filename}`) from linked files (`linkMode=1`: absolute path from database)
- **FR-006**: System MUST validate resolved attachment paths exist before returning them, and handle missing files gracefully with fallback to Web API download if configured
- **FR-007**: System MUST gracefully fall back to Web API adapter when local database is locked, corrupted, or unavailable, providing clear error messages explaining the issue
- **FR-008**: System MUST check Zotero `fulltext` table for cached text before running Docling conversion, using fulltext when available and quality is acceptable (non-empty, minimum length threshold, reasonable structure), and MUST automatically fall back to Docling conversion pipeline for all documents where fulltext is unavailable, missing, or failed quality checks (including documents Zotero couldn't index, documents with indexing errors, or unsupported file types). **CRITICAL**: Fulltext reuse only skips the Docling conversion/OCR step - documents using Zotero fulltext MUST still be processed through chunking, embedding, and indexing steps (large documents require chunking for LLM context window limits).
- **FR-009**: System MUST support page-level fallback from Zotero fulltext to Docling conversion, creating mixed provenance results where some pages come from Zotero fulltext and others from Docling. When combining pages from multiple sources, pages MUST be concatenated sequentially in page order (fulltext pages followed by Docling pages) into a single continuous text stream for chunking, with page-level provenance metadata maintained in audit trail. System MUST fall back to complete Docling conversion for entire documents when fulltext is completely unavailable or fails quality validation. The complete text (from fulltext or Docling, or concatenated mix) MUST then be chunked, embedded, and indexed.
- **FR-010**: System MUST maintain audit trail indicating which documents/pages used Zotero fulltext vs Docling conversion for transparency and debugging, and MUST clearly indicate when fallback to Docling occurred due to missing fulltext, quality issues, or indexing failures
- **FR-011**: System MUST support configuration flag `prefer_zotero_fulltext=true|false` (default `true`) to enable/disable full-text reuse
- **FR-011a**: System MUST process ALL documents through Docling conversion pipeline when Zotero fulltext is unavailable, regardless of document type (PDFs, images, Office documents, etc.), ensuring that documents Zotero couldn't index or never indexed are fully processed and indexed by CiteLoom's extraction pipeline. After conversion (or fulltext reuse), ALL documents MUST be chunked, embedded, and indexed - no documents skip the chunking step regardless of text source. If Docling conversion fails for an unsupported document type, the individual document MUST fail with a clear error message, be logged, and the collection import MUST continue processing remaining documents.
- **FR-012**: System MUST fetch annotation items via Web API (`itemType=annotation`, filtered by `parentItem=attachmentKey`) when `include_annotations=true`
- **FR-013**: System MUST normalize annotation data: convert `pageIndex` (0-indexed) to `page` (1-indexed), extract `text` as `quote`, extract `comment`, extract `color`, extract `tags[]`
- **FR-014**: System MUST index annotations as separate vector points with payload: `type: "annotation"`, `zotero.item_key`, `zotero.attachment_key`, `zotero.annotation.page`, `zotero.annotation.quote`, `zotero.annotation.comment`, and tag with `type:annotation` for filtering
- **FR-015**: System MUST support configuration flag `include_annotations=true|false` (default `false`) to enable/disable annotation indexing
- **FR-016**: System MUST skip annotation extraction gracefully when Web API is unavailable or annotations don't exist, without failing the entire import. When rate limits are encountered during annotation extraction, System MUST retry with exponential backoff (3 retries, base delay 1s, max delay 30s, with jitter), skip attachment annotations if all retries fail, log warning indicating failed attachments, and continue import without blocking
- **FR-017**: System MUST compute deterministic content hash for each document: `hash(first_1MB_file_content + file_size + embedding_model_id + chunking_policy_version + embedding_policy_version)`
- **FR-018**: System MUST store content fingerprint (hash + `file_mtime + file_size`) in download manifest for each successfully downloaded attachment
- **FR-019**: System MUST compare stored fingerprints against computed hashes before document processing, using file metadata (mtime + size) as secondary verification: skip extraction/embedding/storage only if both hash AND metadata match exactly, treat as different document and re-process if hash matches but metadata differs (collision protection)
- **FR-020**: System MUST re-process documents when content hash differs or policy versions change (embedding model or chunking policy), treating policy changes as requiring full re-processing
- **FR-021**: System MUST implement source router with strategy modes: `local-first`, `web-first`, `auto`, `local-only`, `web-only`
- **FR-022**: System MUST implement `local-first` strategy: check each file individually via local database first, use local paths for files found locally, fallback to Web API download per-file for missing files (not collection-level), track source individually per attachment in manifest
- **FR-023**: System MUST implement `web-first` strategy: attempt Web API first, fallback to local database on rate limits or file unavailability
- **FR-024**: System MUST implement `auto` strategy: intelligently select source based on availability, speed, and completeness, with automatic fallback
- **FR-025**: System MUST implement `local-only` and `web-only` strict modes for debugging, with no fallback between sources
- **FR-026**: System MUST add source markers to download manifest (`source: "local" | "web"`) indicating which source provided each attachment
- **FR-027**: System MUST add `zotero.item_key` and `zotero.attachment_key` fields to chunk payloads in vector index
- **FR-028**: System MUST create keyword indexes on `zotero.item_key` and `zotero.attachment_key` fields for fast querying by these keys
- **FR-029**: System MUST enable queries filtered by `zotero.item_key` or `zotero.attachment_key` to retrieve all chunks from a specific Zotero item or attachment
- **FR-030**: System MUST enhance embedding model mismatch error messages to include: bound model name, requested model name, collection name, and clear instructions for resolution (use `--force-rebuild` or switch back to bound model)
- **FR-031**: System MUST support CLI command `citeloom inspect project <project-id> --show-embedding-model` that displays the embedding model currently bound to the collection
- **FR-032**: System MUST expose embedding model information in MCP tool status/inspect responses for programmatic access
- **FR-033**: System MUST support hierarchical collection browsing: display collections with parent-child relationships and item counts
- **FR-034**: System MUST support collection browsing: display first N items (default 20) with titles, item types, attachment counts, tags, and metadata preview
- **FR-035**: System MUST support tag browsing: list all tags with usage counts (number of items tagged), working offline via local database
- **FR-036**: System MUST support recent items view: display most recently added items (default 10) sorted by `dateAdded` descending, with titles, dates, and collection membership
- **FR-037**: System MUST support configuration in `citeloom.toml` for Zotero options: `mode`, `db_path`, `storage_dir`, `include_annotations`, `prefer_zotero_fulltext`, and Web API credentials
- **FR-038**: System MUST support environment variables: `ZOTERO_LOCAL`, `ZOTERO_LIBRARY_ID`, `ZOTERO_API_KEY`, `ZOTERO_EMBEDDING_MODEL` for configuration
- **FR-039**: System MUST maintain backward compatibility: default to `web-first` strategy during migration period, existing Web API workflows continue to work, annotation indexing disabled by default

### Key Entities

- **LocalZoteroDbAdapter**: Infrastructure adapter implementing `ZoteroImporterPort` using SQLite database access. Provides read-only access to collections, items, attachments via direct SQL queries. Handles platform-aware profile detection, immutable read-only connection, path resolution for imported vs linked files, and graceful fallback to Web API.

- **ZoteroSourceRouter**: Application service that routes Zotero operations to local database or Web API based on strategy mode (`local-first`, `web-first`, `auto`, `local-only`, `web-only`). Implements fallback logic, source selection intelligence, and source marker tracking in manifests.

- **FulltextResolver**: Infrastructure adapter that resolves document full-text content, preferring Zotero cached fulltext from `fulltext` table when available and quality-acceptable, falling back to Docling conversion pipeline for ALL documents where fulltext is unavailable, missing, corrupted, or fails quality checks. MUST handle all document types (PDFs, images, Office documents) through Docling when Zotero indexing failed or never occurred. **IMPORTANT**: Fulltext reuse only provides the raw text - documents using Zotero fulltext still require chunking (for LLM context window limits), embedding, and indexing steps. Supports page-level mixed provenance and maintains audit trails indicating fallback reasons.

- **AnnotationResolver**: Infrastructure adapter that fetches PDF annotations from Zotero via Web API, normalizes annotation data (page, quote, comment, color, tags), and indexes annotations as separate vector points with `type:annotation` tag. Handles graceful skipping when annotations unavailable.

- **ContentFingerprint**: Domain concept representing a document's unique identity for deduplication: content hash (based on file content + embedding model + policy versions), file metadata (mtime + size), and policy versions. Used to detect unchanged documents and skip re-processing.

- **DownloadManifestAttachment**: Enhanced to include `source` field (`"local" | "web"`) indicating which source provided the attachment, and `content_fingerprint` field storing hash and metadata for deduplication checks.

- **AnnotationPoint**: Vector index point type with payload: `type: "annotation"`, `zotero.item_key`, `zotero.attachment_key`, `zotero.annotation.page`, `zotero.annotation.quote`, `zotero.annotation.comment`, `zotero.annotation.color`, `zotero.annotation.tags[]`. Indexed separately from regular document chunks, taggable with `type:annotation` for filtering.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Researchers can browse Zotero library collections and view item lists in under 2 seconds using local database access, without requiring internet connection or API calls, on all supported platforms (Windows, macOS, Linux)

- **SC-002**: Import speed improves by 50-80% for collections where 70% or more documents have Zotero fulltext available, measured by comparing total import time (download + conversion + chunking + embedding + storage) before and after full-text reuse implementation

- **SC-003**: Researchers can import collections containing 100+ documents with annotation indexing enabled, where average 5 annotations per document exist, and all annotations are successfully fetched, normalized, and indexed as separate points without failing the import or significantly increasing total import time (less than 20% overhead)

- **SC-004**: Re-importing an unchanged collection (no new documents, no policy changes) completes in under 30 seconds (manifest validation and deduplication checks only), with zero documents re-processed and zero duplicate chunks created

- **SC-005**: Source router successfully falls back between local database and Web API 95% of the time when primary source fails (database locked, network unavailable, rate limits), with imports completing successfully despite source failures

- **SC-006**: Queries filtered by `zotero.item_key` or `zotero.attachment_key` return results in under 500ms for collections containing up to 10,000 chunks, enabled by keyword indexes on these fields

- **SC-007**: Embedding model mismatch errors provide clear, actionable guidance, with 90% of users successfully resolving mismatch issues using provided error messages without requiring support documentation or help

- **SC-008**: Library browsing commands (list-collections, browse-collection, list-tags, recent-items) work offline in 100% of cases when local Zotero database is available, completing successfully without network calls

- **SC-009**: Platform detection correctly identifies Zotero profile paths on Windows, macOS, and Linux in 95% of standard installations, with override configuration available for non-standard setups

- **SC-010**: Full-text quality validation correctly identifies usable vs unusable Zotero fulltext in 95% of cases, with appropriate fallback to Docling for low-quality fulltext, measured by comparing fulltext content against expected document structure

## Assumptions

- Zotero desktop application may or may not be running when local database access is attempted (immutable read-only mode supports concurrent reads and creates snapshot view, SQLite guarantees isolation from concurrent writes)
- Zotero SQLite database schema is stable and matches expected structure (collections, items, itemAttachments, fulltext tables with known schema)
- Zotero fulltext table contains text extraction results from Zotero's built-in PDF indexing or third-party plugins, but many documents may not have fulltext entries (Zotero indexing may have failed, never run, or document type unsupported)
- Documents without Zotero fulltext (indexed, failed indexing, unsupported types, images, etc.) are common and normal - fallback to Docling is expected and seamless behavior
- **CRITICAL**: Fulltext reuse only skips the Docling conversion/OCR step. All documents (with or without fulltext) must still be chunked into appropriately sized pieces for LLM context windows, embedded, and indexed. Large books would exceed context limits if indexed as single units, so chunking is mandatory regardless of text source
- PDF annotations in Zotero are stored as child items with `itemType=annotation` and accessible via Web API `children()` endpoint
- Researchers have local Zotero installation with accessible profile directory (for local database features)
- Researchers have Zotero Web API credentials configured if using Web API features (library_id, api_key)
- Platform-specific paths are standard (Windows uses APPDATA, macOS uses Library/Application Support, Linux uses .zotero)
- Content hashing using first 1MB of file content + file size provides sufficient uniqueness for deduplication (collision rate acceptable), with file metadata (mtime + size) serving as secondary verification to detect hash collisions
- File metadata (mtime + size) is stable enough for fingerprint comparison (not modified by backup tools or file system operations that preserve content) and serves as collision protection when hash matches
- Policy version tracking includes chunking policy (max_tokens, overlap) and embedding policy (model selection), versioned together
- Default to `web-first` strategy initially for backward compatibility, migrating to `auto` as default after rollout period
- Annotation indexing disabled by default to avoid storage bloat, opt-in via configuration
- Full-text reuse enabled by default (`prefer_zotero_fulltext=true`) for performance benefits
- Quality thresholds for fulltext validation: minimum 100 characters, reasonable document structure (sentences, paragraphs)

## Dependencies

- **Existing Zotero Integration**: Current `ZoteroImporterAdapter` (Web API) and `ZoteroImporterPort` interface
- **Existing Document Processing**: Docling converter, chunker, embedder, vector index adapters
- **Existing Checkpointing**: Checkpoint manager and manifest system for tracking download state
- **SQLite3**: Python standard library sqlite3 module (no external dependency)
- **Platform Detection**: Python standard library `platform` module
- **JSON Parsing**: Python standard library `json` module and SQLite JSON1 extension
- **Content Hashing**: Python standard library `hashlib` module
- **File System Operations**: Python standard library `pathlib` and `os` modules

## Constraints

- Local database access requires Zotero profile to be accessible (file system permissions, path existence)
- Immutable read-only mode allows concurrent reads but requires SQLite 3.8.0+ (widely available)
- Full-text reuse requires Zotero to have indexed documents (not all documents may have fulltext) - documents without fulltext automatically use Docling conversion pipeline
- **CRITICAL PIPELINE FLOW**: Processing pipeline is: [Check fulltext] → [Use fulltext OR Docling conversion] → [Chunking] → [Embedding] → [Indexing]. Fulltext reuse only optimizes the conversion step - chunking, embedding, and indexing always occur for all documents regardless of text source (large documents must be chunked for LLM context window limits)
- Docling conversion pipeline MUST handle all document types (PDFs, images, Office documents) that CiteLoom supports, regardless of whether Zotero indexed them
- Fallback to Docling when fulltext unavailable is automatic, seamless, and treated as normal processing flow (no errors, warnings, or user intervention required)
- Annotation extraction requires Web API access (annotations not easily accessible via local database)
- Content hashing for deduplication must balance accuracy (full file hash) vs performance (1MB preview)
- Policy version changes invalidate all fingerprints (requires full re-processing)
- Source router fallback logic must handle race conditions (network becomes available during import)
- Platform detection must handle non-standard installations (portable Zotero, custom profile paths)
- Full-text quality validation thresholds may need tuning for different document types (short papers vs long books)
- Annotation indexing increases storage requirements (separate points per annotation)

## Notes

- This feature builds on existing Zotero batch import (specs/004-zotero-batch-import) and framework implementation (specs/003-framework-implementation)
- Reference implementation patterns documented in `docs/analysis/zotero-improvement-roadmap.md` section 5.0
- Follows patterns from zotero-mcp repository (github.com/54yyyu/zotero-mcp) for local database access and annotation handling
- SQLite immutable read-only mode (`?immutable=1&mode=ro`) prevents database locks and corruption when Zotero is running
- Profile detection uses `profiles.ini` parsing or defaults to first profile if no default marked
- Full-text quality checks: minimum length (100 chars), structure validation (sentence/paragraph patterns), completeness (not truncated)
- Content hash includes first 1MB of file content + file size + embedding model ID + chunking policy version + embedding policy version
- Policy versions should be versioned together (e.g., "1.0") and included in hash to invalidate on any policy change
- Source router "auto" mode: prefer local if available and files exist, prefer web if local unavailable or files missing, smart selection based on speed and completeness
- Annotation normalization: `pageIndex` is 0-indexed in Zotero, convert to 1-indexed `page` number for CiteLoom
- Payload enrichment: `zotero.item_key` and `zotero.attachment_key` added to all chunk payloads, indexed as keyword fields for fast filtering
- Embedding model diagnostics: store model name and provider at collection creation, check on every write, provide friendly error with collection name and both model names
- Configuration migration: maintain backward compatibility, default to `web-first` during rollout, migrate to `auto` default after user feedback period
- Documentation required: platform-specific profile paths guide, cloud-sync caveats, local vs web API trade-offs, annotation indexing guide, full-text reuse policy, embedding governance guide
