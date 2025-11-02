# Feature Specification: Zotero Collection Import with Batch Processing & Progress Indication

**Feature Branch**: `004-zotero-batch-import`  
**Created**: 2025-01-27  
**Status**: Draft  
**Input**: User description: "Implement Zotero collection import with batch processing, progress indication, and checkpointing/resumability. Enables importing documents from Zotero collections/subfolders into CiteLoom projects with visual progress feedback, automatic batching for large collections, and ability to resume interrupted imports. Includes collection browsing, tag-based filtering, and follows framework-specific best practices for Pyzotero rate limiting, Qdrant batch upserts, Docling sequential processing, and Rich progress bars."

## Clarifications

### Session 2025-01-27

- Q: What should happen to checkpoint files and download manifests after successful import completion? → A: User-controlled via CLI flag (`--keep-checkpoints` / `--cleanup-checkpoints`) with default to retain for potential resume needs and audit trail
- Q: How should the system handle duplicate documents already imported to the project? → A: Skip silently using deterministic chunk IDs (leverage existing idempotent upsert behavior)
- Q: When a Zotero item has multiple PDF attachments, how should the system handle them? → A: Process all PDF attachments as separate documents (each attachment becomes its own document with same Zotero metadata)
- Q: How should checkpoint files be named and organized? → A: Correlation ID-based naming (e.g., `var/checkpoints/{correlation_id}.json`) with one checkpoint per import run
- Q: For tag-based filtering, how should tag matching work? → A: Case-insensitive partial matching (tag "ML" matches "#MachineLearning", "#ML", "#ml", "#ml-tutorial")

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import Documents from Zotero Collections (Priority: P1)

A researcher wants to import all documents (PDF attachments) from a specific Zotero collection or subfolder into their CiteLoom project so they can search and cite documents that are already organized in their reference manager without manually downloading and organizing files.

**Why this priority**: This is the core capability that unlocks Zotero integration. Without the ability to import from collections, researchers must manually download and organize files, defeating the purpose of Zotero integration. This must work reliably with proper batching and error handling.

**Independent Test**: Can be fully tested by importing a Zotero collection containing 10-20 PDF attachments and verifying that all attachments are downloaded, converted, chunked, embedded, and stored in the CiteLoom project with proper metadata from Zotero items. Delivers seamless workflow from Zotero to CiteLoom.

**Acceptance Scenarios**:

1. **Given** a researcher has a Zotero collection with PDF attachments, **When** they run `citeloom ingest run --project my/project --zotero-collection "Collection Name"`, **Then** the system lists the collection, fetches all items with attachments, downloads PDFs in batches (10-20 files), processes each through conversion/chunking/embedding, and stores chunks with Zotero metadata (citekey, title, authors, tags, collections)
2. **Given** a researcher imports a collection with subcollections, **When** the import runs, **Then** the system recursively imports all items from subcollections as well, maintaining collection hierarchy information in metadata
3. **Given** a researcher imports a collection where some items lack PDF attachments, **When** the import runs, **Then** items without attachments are skipped with appropriate logging, and items with attachments are processed normally
4. **Given** a Zotero item has multiple PDF attachments, **When** the import runs, **Then** all PDF attachments are processed as separate documents, each with the same Zotero item metadata (citekey, title, authors, tags, collections), and each attachment creates its own document ID and chunks
5. **Given** a Zotero API rate limit is encountered during import, **When** rate limiting occurs, **Then** the system applies rate limiting (0.5s minimum interval for web API), retries with exponential backoff, and continues processing without manual intervention
6. **Given** a researcher imports a collection using local Zotero API, **When** the import runs, **Then** the system uses local API for faster access without rate limits, falling back to remote API if local is unavailable

---

### User Story 2 - Visual Progress Indication During Processing (Priority: P1)

A researcher wants to see real-time progress feedback during document ingestion (conversion, chunking, embedding, storage) so they know the system is working and can estimate completion time, especially for large collections that may take several minutes to process.

**Why this priority**: Without progress indication, users cannot distinguish between slow processing and frozen processes. For large collections or documents, operations can take minutes with no feedback, leading users to interrupt the process. This is critical for user confidence and operational transparency.

**Independent Test**: Can be fully tested by importing a collection with 5-10 documents and verifying that progress bars show document-level progress (X of Y documents), stage-level progress (converting, chunking, embedding, storing), estimated time remaining, and current operation description. Delivers user confidence and operational visibility.

**Acceptance Scenarios**:

1. **Given** a researcher imports documents from a Zotero collection or local directory, **When** processing begins, **Then** a progress bar displays showing overall document progress (e.g., "Processing document 3 of 10"), individual stage progress for each document (converting, chunking, embedding, storing), elapsed time, and estimated time remaining
2. **Given** a researcher processes a large PDF (500+ pages), **When** conversion takes several minutes, **Then** progress indication shows the conversion stage is active with a spinner or progress indicator, preventing user confusion about whether the process is frozen
3. **Given** batch processing of multiple documents, **When** documents are processed sequentially, **Then** progress bars update in real-time showing which document is being processed, which stage is active, and overall batch progress
4. **Given** a processing stage fails for a document, **When** an error occurs, **Then** the progress bar indicates the failure clearly (e.g., "❌ document.pdf (failed)") and processing continues with remaining documents
5. **Given** progress indication is displayed, **When** the process completes, **Then** final summary shows total documents processed, total chunks created, duration, and any warnings or errors

---

### User Story 3 - Resumable Batch Processing with Checkpointing (Priority: P1)

A researcher wants batch ingestion to be resumable so that if processing stops partway through (crash, timeout, manual interruption), they can resume from the last successful checkpoint without losing progress or reprocessing already-completed documents.

**Why this priority**: Large batch imports can take significant time (hours for hundreds of documents). If processing stops at document 73 of 100, users should not lose all progress. Checkpointing enables reliable large-scale imports and reduces frustration from interrupted workflows.

**Independent Test**: Can be fully tested by starting an import of 10 documents, interrupting it at document 5, then resuming with `--resume` flag and verifying that documents 1-5 are skipped, documents 6-10 are processed, and final results are correct. Delivers reliability and user time savings.

**Acceptance Scenarios**:

1. **Given** a researcher starts importing 100 documents from a Zotero collection, **When** processing stops at document 73 (due to crash, Ctrl+C, or timeout), **Then** a checkpoint file is created documenting completed documents (1-72), and the system can resume from document 73 using `--resume` flag
2. **Given** a researcher resumes an interrupted import with `--resume` flag, **When** the import runs, **Then** the system loads the checkpoint file, skips all documents marked as "completed", and continues processing from the first incomplete document
3. **Given** checkpointing is active, **When** each document completes a processing stage (conversion, chunking, embedding, storage), **Then** the checkpoint is updated with the current stage and progress, allowing resume from the last completed stage if needed
4. **Given** a checkpoint file exists, **When** the researcher starts a new import (without `--resume`), **Then** the system prompts whether to resume from checkpoint or start fresh, or requires explicit `--fresh` flag to start new import
5. **Given** a checkpoint file is corrupted or invalid, **When** resume is attempted, **Then** the system detects the corruption, warns the user, and offers to start fresh or attempt recovery

---

### User Story 4 - Browse and Explore Zotero Library Structure (Priority: P2)

A researcher wants to browse their Zotero library (collections, tags, recent items) before importing so they can select specific collections or filter by tags, understand what will be imported, and verify Zotero connectivity before starting a large import operation.

**Why this priority**: Enables selective imports and prevents importing unwanted documents. Allows researchers to verify Zotero connectivity and explore library structure. Reduces errors from incorrect collection names or typos. Improves user experience with library exploration.

**Independent Test**: Can be fully tested by running `citeloom zotero list-collections` and verifying that all top-level collections are listed with names and keys, then browsing a specific collection to see its items. Delivers library exploration capability that enables informed import decisions.

**Acceptance Scenarios**:

1. **Given** a researcher has a configured Zotero library, **When** they run `citeloom zotero list-collections`, **Then** the system displays all top-level collections with collection names and keys, and optionally subcollection hierarchy
2. **Given** a researcher wants to see items in a collection, **When** they run `citeloom zotero browse-collection "Collection Name"`, **Then** the system displays all items in that collection with titles, item types, attachment counts, and metadata summary
3. **Given** a researcher wants to see recent additions, **When** they run `citeloom zotero recent-items`, **Then** the system displays the 10 most recently added items with titles, dates, and collection membership
4. **Given** a researcher wants to browse tags, **When** they run `citeloom zotero list-tags`, **Then** the system displays all tags used in their library with usage counts
5. **Given** a Zotero library is not accessible (API key invalid, Zotero not running for local), **When** browsing commands are run, **Then** the system provides clear error messages indicating what configuration is needed (API key, library ID, or Zotero desktop running)

---

### User Story 5 - Tag-Based Filtering for Selective Import (Priority: P2)

A researcher wants to import only documents from a Zotero collection that match specific tags (e.g., import all items tagged "#MachineLearning" but exclude items tagged "#Draft") so they can selectively import relevant documents without manually filtering.

**Why this priority**: Researchers often tag documents by topic, status, or relevance. Tag-based filtering enables importing only relevant documents, reducing storage and processing time. Allows for targeted project imports based on research focus.

**Independent Test**: Can be fully tested by importing a collection with tag filter `--zotero-tags "#ML,#AI" --exclude-tags "#Draft"` and verifying that only items matching the include tags and not matching exclude tags are imported. Delivers selective import capability.

**Acceptance Scenarios**:

1. **Given** a researcher has a collection with items tagged "#MachineLearning", "#AI", "#Draft", **When** they import with `--zotero-tags "ML,AI" --exclude-tags "Draft"`, **Then** only items with tags containing "ML" or "AI" (case-insensitive, partial match) and not containing "Draft" are imported (e.g., "#MachineLearning" matches "ML", "#ai-tutorial" matches "AI")
2. **Given** a researcher imports with tag filters, **When** items are processed, **Then** tag filtering occurs before downloading attachments, reducing unnecessary downloads and processing time
3. **Given** tag filtering results in zero items matching criteria, **When** import runs, **Then** the system reports that no items match the filter criteria and exits without error
4. **Given** a researcher uses multiple include tags, **When** filtering occurs, **Then** items matching ANY of the include tags are selected (OR logic), and items matching ANY exclude tag are excluded

---

### User Story 6 - Two-Phase Import for Zotero Collections (Priority: P2)

A researcher wants Zotero collection imports to download all attachments first to persistent storage, then process downloaded files, so that if processing fails, downloads are preserved and processing can be retried without re-downloading.

**Why this priority**: For large collections, downloading attachments can take significant time. If processing fails after downloads complete, re-downloading wastes time and bandwidth. Two-phase approach (download then process) provides better fault tolerance and enables retry without re-download.

**Independent Test**: Can be fully tested by importing a collection with 20 documents, interrupting during processing phase after downloads complete, then verifying that downloaded files persist and can be processed independently using `--process-downloads` flag. Delivers better fault tolerance and time savings.

**Acceptance Scenarios**:

1. **Given** a researcher imports a Zotero collection, **When** the import begins, **Then** the system first downloads all attachments to a persistent directory (`var/zotero_downloads/{collection_key}/`), creates a download manifest, then processes downloaded files through conversion/chunking/embedding pipeline
2. **Given** downloads complete but processing fails partway through, **When** the researcher retries, **Then** the system detects existing downloads via manifest, skips download phase, and processes only remaining files using checkpoint information
3. **Given** a researcher wants to download without processing, **When** they run `citeloom ingest download --zotero-collection "Name"`, **Then** all attachments are downloaded to persistent storage with manifest, and processing can be done later with `citeloom ingest process-downloads --collection-key KEY`
4. **Given** downloaded files persist in storage, **When** the researcher runs process-downloads, **Then** the system reads the download manifest, verifies files exist, and processes them with checkpointing for resumability

---

## Edge Cases

- What happens when a Zotero collection is empty or contains no items with PDF attachments?
- What happens when Zotero API rate limits are exceeded during import?
- How are network interruptions handled during file downloads?
- What happens when a downloaded PDF is corrupted or cannot be converted?
- How does checkpointing handle concurrent import processes?
- What happens when checkpoint file is deleted or moved during processing?
- What happens when collection name doesn't exist or is misspelled?
- How are subcollections handled when parent collection is specified?
- What happens when progress indication is disabled (non-interactive mode)?
- How does resume handle changes to collection contents between runs?
- What happens to checkpoint files and download manifests after successful import completion?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support importing documents from Zotero collections by collection name or collection key
- **FR-002**: System MUST download PDF attachments from Zotero items to persistent storage before processing
- **FR-003**: System MUST support recursive import of subcollections when a parent collection is specified
- **FR-004**: System MUST display real-time progress indication showing document count, current stage, elapsed time, and estimated time remaining
- **FR-005**: System MUST create checkpoint files after each document completes processing, documenting document path, status, chunks created, and completion timestamp
- **FR-006**: System MUST support resuming interrupted imports via `--resume` flag, skipping completed documents and continuing from first incomplete document
- **FR-007**: System MUST apply rate limiting for Zotero web API (0.5s minimum interval between requests, 2 requests per second maximum)
- **FR-008**: System MUST download files in batches (10-20 files) to avoid overwhelming I/O and enable progress tracking
- **FR-009**: System MUST batch Qdrant upserts (100-500 points per batch) for memory efficiency and network performance
- **FR-010**: System MUST save checkpoints after each successful batch upsert to enable fine-grained resume capability
- **FR-011**: System MUST support browsing Zotero library structure (list collections, browse collection items, list tags, get recent items)
- **FR-012**: System MUST support tag-based filtering for selective import (include tags, exclude tags, OR logic for includes, ANY-match logic for excludes)
- **FR-013**: System MUST create download manifests documenting downloaded files, item metadata, and download timestamps for two-phase import
- **FR-014**: System MUST support processing already-downloaded files via `--process-downloads` flag using download manifest
- **FR-015**: System MUST skip items without PDF attachments with appropriate logging
- **FR-016**: System MUST handle Zotero API errors gracefully with retry logic (exponential backoff, 3 retries, 1s base delay, 30s max delay)
- **FR-017**: System MUST handle file download failures gracefully, logging failed downloads and continuing with remaining files
- **FR-018**: System MUST preserve Zotero item metadata (citekey, title, authors, year, DOI, tags, collections) in chunk payloads during import
- **FR-019**: System MUST use local Zotero API when available (local=True) for faster access without rate limits, falling back to remote API if local unavailable
- **FR-020**: System MUST display progress at multiple levels: overall batch progress, per-document stage progress, and operation descriptions
- **FR-021**: System MUST update checkpoints atomically (write to temp file, then atomic rename) to prevent corruption during crashes
- **FR-022**: System MUST validate checkpoint file integrity before resuming and warn if checkpoint is invalid or corrupted
- **FR-023**: System MUST support processing Docling conversions sequentially (one document at a time) due to CPU/memory intensity
- **FR-024**: System MUST apply timeout limits during document conversion (120s per document, 10s per page) as defined in existing specifications
- **FR-025**: System MUST use generator/iterator patterns for large result sets to minimize memory usage during collection browsing and item fetching
- **FR-026**: System MUST provide user-controlled checkpoint and manifest cleanup via CLI flags (`--keep-checkpoints` to retain after completion, `--cleanup-checkpoints` to remove after success), with default behavior to retain files for audit trail and potential resume needs
- **FR-027**: System MUST handle duplicate documents (already imported with matching deterministic chunk IDs) by skipping silently during import, leveraging existing idempotent upsert behavior without user notification
- **FR-028**: System MUST process all PDF attachments from a Zotero item as separate documents, with each attachment becoming its own document with the same Zotero item metadata (citekey, title, authors, tags, collections)
- **FR-029**: System MUST name checkpoint files using correlation ID (e.g., `var/checkpoints/{correlation_id}.json`), with one checkpoint file per import run, enabling traceability to audit logs and resume operations
- **FR-030**: System MUST perform tag-based filtering using case-insensitive partial matching (substring matching), where filter tag "ML" matches item tags containing "ML" regardless of case or surrounding characters (e.g., "#MachineLearning", "#ML", "#ml", "#ml-tutorial")

### Key Entities

- **ZoteroCollection**: Represents a Zotero collection with key, name, and optional subcollections. Used for collection selection and hierarchy navigation.
- **ZoteroItem**: Represents a Zotero library item with key, title, item type, metadata (authors, year, DOI, tags, collections), and attachments. Used for matching and metadata extraction.
- **ZoteroAttachment**: Represents a file attachment to a Zotero item with key, filename, content type, file size, and link mode. Used for downloading PDFs and other files.
- **DownloadManifest**: Documents downloaded files from a Zotero collection with collection metadata, item references, file paths, download status, and timestamps. Used for two-phase import and retry logic.
- **IngestionCheckpoint**: Documents batch ingestion state with correlation ID, project ID, list of document checkpoints, start time, last update time, and completion statistics. Used for resumable processing.
- **DocumentCheckpoint**: Documents state of single document within batch with path, status (pending/converting/chunking/embedding/storing/completed/failed), stage progress, chunks count, doc ID, and error information. Used for fine-grained resume capability.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Researchers can import documents from Zotero collections in under 5 minutes per 50 documents (including download, conversion, chunking, embedding, and storage), with progress visible throughout
- **SC-002**: Researchers can resume interrupted imports and skip completed documents successfully 100% of the time when using `--resume` flag with valid checkpoint file
- **SC-003**: Progress indication provides accurate time estimates (within 20% of actual completion time) for batch operations with 10+ documents
- **SC-004**: System handles Zotero API rate limits without manual intervention, automatically applying rate limiting and retry logic, completing imports successfully 95% of the time despite rate limit encounters
- **SC-005**: Researchers can browse Zotero library structure and view collection contents in under 2 seconds for collections with up to 100 items
- **SC-006**: Tag-based filtering reduces processing time by at least 30% when filtering excludes 50% or more of collection items (by avoiding unnecessary downloads and processing)
- **SC-007**: Two-phase import (download then process) enables retry of processing phase without re-downloading in 100% of cases where downloads completed successfully
- **SC-008**: Checkpoint files enable resume from last completed document with zero duplicate processing (completed documents are skipped) and zero data loss (all progress preserved)
- **SC-009**: System provides clear error messages and recovery guidance when Zotero connectivity fails, API keys are invalid, or collections don't exist, enabling user resolution without support
- **SC-010**: Batch operations (100+ documents) complete successfully without memory exhaustion, using batched processing patterns (file downloads in 10-20 batches, Qdrant upserts in 100-500 point batches)

## Assumptions

- Zotero desktop application is running when using local API (`local=True`)
- Zotero web API is accessible when using remote API (requires internet connection)
- Researchers have Zotero library configured with library ID and API key (for remote) or Zotero desktop running (for local)
- Better BibTeX extension may or may not be installed (system handles both cases gracefully)
- PDF attachments are stored as imported files in Zotero (not linked URLs)
- Collections may contain subcollections (system supports recursive import)
- Project collections in CiteLoom already exist or are created automatically (existing behavior)
- Embedding models are consistent with project configuration (enforced by existing write-guards)
- File system has sufficient space for downloaded attachments (user responsibility)
- Network connectivity is stable for remote Zotero API access (retry logic handles transient failures)
- Researchers can distinguish between collection names when browsing (system provides keys for disambiguation)

## Dependencies

- **Existing Zotero metadata resolution** (ZoteroPyzoteroResolver) for extracting metadata from items
- **Existing document ingestion pipeline** (convert → chunk → embed → store) for processing downloaded files
- **Existing Qdrant integration** (QdrantIndexAdapter) for batch upserts with existing batch size patterns
- **Existing Docling conversion** (DoclingConverterAdapter) with timeout handling already implemented
- **Rich library** (already in dependencies) for progress bar implementation
- **Pyzotero library** (already installed) for Zotero API access
- **Python pathlib** for file path handling
- **Python tempfile** for temporary directory management (if needed)
- **Python json** for checkpoint and manifest file serialization
- **Python datetime** for timestamp tracking in checkpoints

## Constraints

- Zotero web API rate limits: 30,000 requests per day (system must apply rate limiting)
- Local Zotero API requires Zotero desktop application running
- Docling conversion is CPU/memory intensive: sequential processing recommended (1 document at a time)
- Qdrant batch upsert optimal size: 100-500 points (memory and network efficiency)
- Checkpoint files must be human-readable (JSON format) for debugging and manual inspection
- Progress indication requires interactive terminal (Rich library requires TTY for optimal display)
- Two-phase import requires persistent storage space for downloaded attachments
- Checkpoint resume requires correlation ID or explicit resume flag to prevent accidental overwrites

## Notes

- This feature builds on existing Zotero metadata resolution (User Story 6 from 003-framework-implementation)
- MCP tool `ingest_from_source` already has placeholder for Zotero import (returns NOT_IMPLEMENTED)
- Duration tracking in MCP responses has been fixed but can be enhanced with actual batch processing times
- Best practices from `docs/analysis/best-practices-implementation.md` should be followed for rate limiting, batching, and retry logic
- This feature addresses critical gaps identified in `docs/analysis/zotero-implementation-analysis.md`
- Collection browsing functionality overlaps with missing features identified in `docs/analysis/zotero-mcp-comparison.md` but focuses on import workflow rather than general library exploration
