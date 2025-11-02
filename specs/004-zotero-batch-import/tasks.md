# Tasks: Zotero Collection Import with Batch Processing & Progress Indication

**Input**: Design documents from `/specs/004-zotero-batch-import/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [x] T001 Create var/checkpoints/ directory for checkpoint file storage
- [x] T002 Create var/zotero_downloads/ directory for downloaded attachment storage
- [x] T003 [P] Verify existing project structure matches plan.md (src/domain, src/application, src/infrastructure)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain models and port interfaces that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 [US1,US3,US6] Create IngestionCheckpoint entity in src/domain/models/checkpoint.py with correlation_id, project_id, collection_key, start_time, last_update, documents list, and statistics
- [x] T005 [US1,US3,US6] Create DocumentCheckpoint entity in src/domain/models/checkpoint.py with path, status, stage, chunks_count, doc_id, zotero_item_key, zotero_attachment_key, error, updated_at attributes
- [x] T006 [US1,US3,US6] Create CheckpointStatistics value object in src/domain/models/checkpoint.py with total_documents, completed, failed, pending counts and completion_percentage() method
- [x] T007 [US1,US3,US6] Implement IngestionCheckpoint.to_dict() and from_dict() methods in src/domain/models/checkpoint.py for JSON serialization
- [x] T008 [US1,US3,US6] Implement DocumentCheckpoint.to_dict() and from_dict() methods in src/domain/models/checkpoint.py for JSON serialization
- [x] T009 [US1,US3,US6] Implement IngestionCheckpoint.get_incomplete_documents() and get_completed_documents() methods in src/domain/models/checkpoint.py
- [x] T010 [US1,US3,US6] Implement IngestionCheckpoint.update_statistics() method in src/domain/models/checkpoint.py to recalculate statistics from documents list
- [x] T011 [US1,US6] Create DownloadManifest entity in src/domain/models/download_manifest.py with collection_key, collection_name, download_time, items list
- [x] T012 [US1,US6] Create DownloadManifestItem entity in src/domain/models/download_manifest.py with item_key, title, attachments list, metadata dict
- [x] T013 [US1,US6] Create DownloadManifestAttachment entity in src/domain/models/download_manifest.py with attachment_key, filename, local_path, download_status, file_size, error
- [x] T014 [US1,US6] Implement DownloadManifest.to_dict() and from_dict() methods in src/domain/models/download_manifest.py for JSON serialization
- [x] T015 [US1,US6] Implement DownloadManifest.get_all_file_paths() and get_successful_downloads() methods in src/domain/models/download_manifest.py
- [x] T016 [US1,US4,US5,US6] Create ZoteroImporterPort protocol in src/application/ports/zotero_importer.py with list_collections, get_collection_items, get_item_attachments, download_attachment, get_item_metadata, list_tags, get_recent_items, find_collection_by_name methods
- [x] T017 [US2,US3,US6] Create CheckpointManagerPort protocol in src/application/ports/checkpoint_manager.py with save_checkpoint, load_checkpoint, validate_checkpoint, checkpoint_exists methods
- [x] T018 [US2,US6] Create ProgressReporterPort protocol in src/application/ports/progress_reporter.py with start_batch and start_document methods returning ProgressContext and DocumentProgressContext
- [x] T019 [US2,US6] Enhance IngestDocument use case signature in src/application/use_cases/ingest_document.py to accept optional progress_reporter parameter of type ProgressReporterPort
- [x] T020 [US2,US6] Add progress callback support in IngestDocument use case in src/application/use_cases/ingest_document.py to report stage progress (converting, chunking, embedding, storing)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Import Documents from Zotero Collections (Priority: P1) 🎯 MVP

**Goal**: Enable importing all PDF attachments from a Zotero collection or subfolder into a CiteLoom project. Downloads attachments in batches, processes through conversion/chunking/embedding pipeline, and stores chunks with Zotero metadata.

**Independent Test**: Can be fully tested by importing a Zotero collection containing 10-20 PDF attachments and verifying that all attachments are downloaded, converted, chunked, embedded, and stored in the CiteLoom project with proper metadata from Zotero items.

### Implementation for User Story 1

- [x] T021 [US1] Create ZoteroImporterAdapter class in src/infrastructure/adapters/zotero_importer.py implementing ZoteroImporterPort
- [x] T022 [US1] Implement pyzotero client initialization with rate limiting wrapper (0.5s interval for web API, no limits for local) in src/infrastructure/adapters/zotero_importer.py
- [x] T023 [US1] Implement ZoteroImporterAdapter.list_collections() using zot.collections() with rate limiting in src/infrastructure/adapters/zotero_importer.py
- [x] T024 [US1] Implement ZoteroImporterAdapter.get_collection_items() using zot.collection_items() as generator/iterator in src/infrastructure/adapters/zotero_importer.py
- [x] T025 [US1] Add recursive subcollection support in ZoteroImporterAdapter.get_collection_items() using zot.collections_sub() in src/infrastructure/adapters/zotero_importer.py
- [x] T026 [US1] Implement ZoteroImporterAdapter.get_item_attachments() using zot.children(item_key) to fetch PDF attachments in src/infrastructure/adapters/zotero_importer.py
- [x] T027 [US1] Implement ZoteroImporterAdapter.download_attachment() using zot.file() for remote API or direct file access for local API in src/infrastructure/adapters/zotero_importer.py
- [x] T028 [US1] Add retry logic with exponential backoff (3 retries, 1s base delay, 30s max delay, jitter) in ZoteroImporterAdapter.download_attachment() in src/infrastructure/adapters/zotero_importer.py
- [x] T029 [US1] Implement ZoteroImporterAdapter.get_item_metadata() to extract title, creators (authors), date (year), DOI, tags, collections from Zotero item in src/infrastructure/adapters/zotero_importer.py
- [x] T030 [US1] Implement batch download of attachments (10-20 files per batch) with progress tracking in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T031 [US1] Create BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py orchestrating collection fetch, item fetch, attachment download, and processing pipeline, generating correlation ID at start for checkpoint file naming (FR-029)
- [x] T032 [US1] Implement two-phase import workflow (download all attachments first, then process) in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T033 [US1] Create download manifest after downloading all attachments in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T034 [US1] Process all PDF attachments from an item as separate documents (FR-028) in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T035 [US1] Skip items without PDF attachments with appropriate logging in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T036 [US1] Preserve Zotero item metadata (citekey, title, authors, year, DOI, tags, collections) in chunk payloads during import in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T037 [US1] Use existing ZoteroPyzoteroResolver for metadata extraction (reuse existing resolver) in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T038 [US1] Enhance ingest CLI command in src/infrastructure/cli/commands/ingest.py to accept --zotero-collection option (collection name or key)
- [x] T039 [US1] Wire --zotero-collection option to BatchImportFromZotero use case in src/infrastructure/cli/commands/ingest.py
- [x] T040 [US1] Handle ZoteroImporterAdapter.find_collection_by_name() for collection name resolution in src/infrastructure/cli/commands/ingest.py
- [x] T041 [US1] Use local Zotero API when available (local=True) with fallback to remote API in ZoteroImporterAdapter initialization in src/infrastructure/adapters/zotero_importer.py
- [x] T042 [US1] Update MCP tool ingest_from_source in src/infrastructure/mcp/tools.py to replace NOT_IMPLEMENTED placeholder for Zotero import with actual implementation
- [x] T043 [US1] Support collection_key option in ingest_from_source MCP tool in src/infrastructure/mcp/tools.py for Zotero imports

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Visual Progress Indication During Processing (Priority: P1)

**Goal**: Display real-time progress bars showing document-level progress (X of Y documents), stage-level progress (converting, chunking, embedding, storing), elapsed time, and estimated time remaining during batch ingestion operations.

**Independent Test**: Can be fully tested by importing a collection with 5-10 documents and verifying that progress bars show document-level progress, stage-level progress, estimated time remaining, and current operation description.

### Implementation for User Story 2

- [x] T044 [US2] Create RichProgressReporterAdapter class in src/infrastructure/adapters/rich_progress_reporter.py implementing ProgressReporterPort
- [x] T045 [US2] Implement RichProgressReporterAdapter.start_batch() using Rich Progress with SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn in src/infrastructure/adapters/rich_progress_reporter.py
- [x] T046 [US2] Implement RichProgressReporterAdapter.start_document() to create per-document progress task showing document index and name in src/infrastructure/adapters/rich_progress_reporter.py
- [x] T047 [US2] Implement DocumentProgressContext.update_stage() to update progress bar with current stage (converting, chunking, embedding, storing) and description in src/infrastructure/adapters/rich_progress_reporter.py
- [x] T048 [US2] Implement DocumentProgressContext.fail() to mark document as failed with error message in progress bar in src/infrastructure/adapters/rich_progress_reporter.py
- [x] T049 [US2] Detect non-interactive mode (non-TTY) and fallback to structured logging instead of Rich progress bars in RichProgressReporterAdapter in src/infrastructure/adapters/rich_progress_reporter.py
- [x] T050 [US2] Implement time estimation logic based on elapsed time and average stage duration in RichProgressReporterAdapter in src/infrastructure/adapters/rich_progress_reporter.py
- [x] T051 [US2] Enhance IngestDocument use case to call progress_reporter.update_stage() at each stage (converting, chunking, embedding, storing) in src/application/use_cases/ingest_document.py
- [x] T052 [US2] Display final summary with total documents processed, chunks created, duration, warnings, and errors in RichProgressReporterAdapter in src/infrastructure/adapters/rich_progress_reporter.py
- [x] T053 [US2] Integrate RichProgressReporterAdapter with BatchImportFromZotero use case for batch-level and document-level progress in src/application/use_cases/batch_import_from_zotero.py
- [x] T054 [US2] Pass progress_reporter to IngestDocument use case from BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Resumable Batch Processing with Checkpointing (Priority: P1)

**Goal**: Enable resuming interrupted batch imports from the last successful checkpoint, skipping completed documents and continuing from the first incomplete document.

**Independent Test**: Can be fully tested by starting an import of 10 documents, interrupting it at document 5, then resuming with --resume flag and verifying that documents 1-5 are skipped, documents 6-10 are processed, and final results are correct.

### Implementation for User Story 3

- [x] T055 [US3] Create CheckpointManagerAdapter class in src/infrastructure/adapters/checkpoint_manager.py implementing CheckpointManagerPort
- [x] T056 [US3] Implement CheckpointManagerAdapter.save_checkpoint() with atomic write (write to temp file, then atomic rename) in src/infrastructure/adapters/checkpoint_manager.py
- [x] T057 [US3] Implement CheckpointManagerAdapter.load_checkpoint() with JSON deserialization and error handling in src/infrastructure/adapters/checkpoint_manager.py
- [x] T058 [US3] Implement CheckpointManagerAdapter.validate_checkpoint() to validate schema, timestamp consistency, and document checkpoint validity in src/infrastructure/adapters/checkpoint_manager.py
- [x] T059 [US3] Implement CheckpointManagerAdapter.checkpoint_exists() to check if checkpoint file exists at path in src/infrastructure/adapters/checkpoint_manager.py
- [x] T060 [US3] Generate checkpoint file path using correlation ID format var/checkpoints/{correlation_id}.json in CheckpointManagerAdapter in src/infrastructure/adapters/checkpoint_manager.py
- [x] T061 [US3] Update checkpoint after each document completes processing stage in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T062 [US3] Save checkpoint after each successful batch upsert (100-500 points) to enable fine-grained resume in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T063 [US3] Implement resume logic to load checkpoint, skip completed documents, and continue from first incomplete document in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T064 [US3] Validate checkpoint file integrity before resuming and warn if invalid/corrupted in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T065 [US3] Add --resume flag to ingest CLI command in src/infrastructure/cli/commands/ingest.py to enable checkpoint loading
- [x] T066 [US3] Add --fresh flag to ingest CLI command in src/infrastructure/cli/commands/ingest.py to start new import instead of resuming checkpoint (when checkpoint exists, require explicit --fresh flag to start fresh, otherwise prompt user or require --resume)
- [x] T068 [US3] Detect checkpoint file disappearance during processing and handle gracefully (recreate checkpoint if possible, or fail with clear error) in CheckpointManagerAdapter in src/infrastructure/adapters/checkpoint_manager.py
- [x] T067 [US3] Handle duplicate documents by skipping silently using deterministic chunk IDs (existing idempotent upsert behavior) in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently

---

## Phase 6: User Story 4 - Browse and Explore Zotero Library Structure (Priority: P2)

**Goal**: Enable browsing Zotero library structure (collections, tags, recent items) before importing to select specific collections, verify connectivity, and explore library contents.

**Independent Test**: Can be fully tested by running citeloom zotero list-collections and verifying that all top-level collections are listed with names and keys, then browsing a specific collection to see its items.

### Implementation for User Story 4

- [x] T069 [US4] Implement ZoteroImporterAdapter.get_recent_items() using zot.items(sort='dateAdded', direction='desc', limit=10) in src/infrastructure/adapters/zotero_importer.py
- [x] T070 [US4] Implement ZoteroImporterAdapter.list_tags() using zot.tags() returning tags with usage counts in src/infrastructure/adapters/zotero_importer.py
- [x] T071 [US4] Create zotero CLI command group in src/infrastructure/cli/commands/zotero.py
- [x] T072 [US4] Implement list-collections command in src/infrastructure/cli/commands/zotero.py displaying collection names and keys with optional subcollection hierarchy
- [x] T073 [US4] Implement browse-collection command in src/infrastructure/cli/commands/zotero.py displaying items with titles, item types, attachment counts, and metadata summary
- [x] T074 [US4] Implement recent-items command in src/infrastructure/cli/commands/zotero.py displaying 10 most recently added items with titles, dates, and collection membership
- [x] T075 [US4] Implement list-tags command in src/infrastructure/cli/commands/zotero.py displaying all tags with usage counts
- [x] T076 [US4] Register zotero command group in main CLI app in src/infrastructure/cli/main.py
- [x] T077 [US4] Add clear error messages for Zotero connectivity failures (invalid API key, library ID, Zotero not running) in zotero CLI commands in src/infrastructure/cli/commands/zotero.py

**Checkpoint**: At this point, User Stories 1-4 should all work independently

---

## Phase 7: User Story 5 - Tag-Based Filtering for Selective Import (Priority: P2)

**Goal**: Enable importing only documents from a Zotero collection that match specific tags (include tags with OR logic, exclude tags with ANY-match logic) before downloading attachments.

**Independent Test**: Can be fully tested by importing a collection with tag filter --zotero-tags "ML,AI" --exclude-tags "Draft" and verifying that only items matching the include tags and not matching exclude tags are imported.

### Implementation for User Story 5

- [x] T078 [US5] Implement tag-based filtering logic with case-insensitive partial matching (substring matching) in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T079 [US5] Apply include tags with OR logic (any match selects item) in tag filtering in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T080 [US5] Apply exclude tags with ANY-match logic (any exclude tag excludes item) in tag filtering in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T081 [US5] Filter items before downloading attachments to reduce unnecessary downloads in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T082 [US5] Report zero items matching criteria and exit without error if tag filtering results in no matches in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [x] T083 [US5] Add --zotero-tags option to ingest CLI command in src/infrastructure/cli/commands/ingest.py accepting comma-separated list of tags
- [x] T084 [US5] Add --exclude-tags option to ingest CLI command in src/infrastructure/cli/commands/ingest.py accepting comma-separated list of tags
- [x] T085 [US5] Wire --zotero-tags and --exclude-tags options to BatchImportFromZotero use case in src/infrastructure/cli/commands/ingest.py
- [x] T086 [US5] Support tag filters in ingest_from_source MCP tool in src/infrastructure/mcp/tools.py

**Checkpoint**: At this point, User Stories 1-5 should all work independently

---

## Phase 8: User Story 6 - Two-Phase Import for Zotero Collections (Priority: P2)

**Goal**: Download all attachments first to persistent storage, then process downloaded files, enabling retry of processing phase without re-downloading if downloads completed successfully.

**Independent Test**: Can be fully tested by importing a collection with 20 documents, interrupting during processing phase after downloads complete, then verifying that downloaded files persist and can be processed independently using --process-downloads flag.

### Implementation for User Story 6

- [ ] T087 [US6] Create download manifest after downloading all attachments in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T088 [US6] Save download manifest to var/zotero_downloads/{collection_key}/manifest.json in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T089 [US6] Detect existing downloads via manifest and skip download phase on retry in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T090 [US6] Create ingest download command in src/infrastructure/cli/commands/ingest.py to download attachments without processing
- [ ] T091 [US6] Create ingest process-downloads command in src/infrastructure/cli/commands/ingest.py to process already-downloaded files using manifest
- [ ] T092 [US6] Load download manifest and verify files exist before processing in process-downloads command in src/infrastructure/cli/commands/ingest.py
- [ ] T093 [US6] Use checkpointing for resumability when processing downloaded files in process-downloads command in src/infrastructure/cli/commands/ingest.py

**Checkpoint**: At this point, User Stories 1-6 should all work independently

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, error handling improvements, and user-controlled checkpoint/manifest cleanup

- [ ] T094 [US1,US3,US6] Add user-controlled checkpoint and manifest cleanup via --keep-checkpoints and --cleanup-checkpoints flags in src/infrastructure/cli/commands/ingest.py (default: retain)
- [ ] T095 [US1,US3,US6] Implement checkpoint cleanup logic (delete checkpoint files if --cleanup-checkpoints flag set) in src/infrastructure/cli/commands/ingest.py after successful import
- [ ] T096 [US1,US3,US6] Implement manifest cleanup logic (delete manifest and downloaded files if --cleanup-checkpoints flag set) in src/infrastructure/cli/commands/ingest.py after successful import
- [ ] T097 [US1,US2,US3,US6] Add comprehensive error handling for empty collections, network interruptions, corrupted PDFs, and collection name typos in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T098 [US3] Handle checkpoint file deletion/movement during processing gracefully in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T099 [US3] Handle concurrent import processes (warn user, prevent checkpoint corruption) in BatchImportFromZotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T100 [US1,US3,US6] Add integration tests for ZoteroImporterAdapter in tests/integration/test_zotero_importer.py covering collection browsing, item fetching, file downloads, rate limiting, and retry logic
- [ ] T101 [US3] Add integration tests for CheckpointManagerAdapter in tests/integration/test_checkpoint_manager.py covering checkpoint I/O, atomic writes, validation, and resume logic
- [ ] T102 [US2] Add integration tests for RichProgressReporterAdapter in tests/integration/test_progress_indication.py covering progress bars, time estimates, and non-interactive mode fallback
- [ ] T103 [US1,US2,US3,US6] Add unit tests for checkpoint domain models in tests/unit/test_checkpoint_models.py covering validation rules, state transitions, and serialization
- [ ] T104 [US1,US6] Add unit tests for download manifest domain models in tests/unit/test_download_manifest.py covering validation rules and serialization
- [ ] T105 [US1,US2,US3,US6] Add end-to-end tests for full import workflow (browse → import → resume) in tests/integration/test_zotero_batch_import.py
- [ ] T106 [US5] Add integration tests for tag-based filtering in tests/integration/test_tag_filtering.py covering case-insensitive partial matching, OR logic for includes, ANY-match for excludes
- [ ] T107 [US6] Add integration tests for two-phase import in tests/integration/test_two_phase_import.py covering download manifest creation, retry without re-download, and process-downloads command

---

## Dependencies & Story Completion Order

### Story Dependencies

```
US1 (Import) ──┐
               ├──> Can be developed independently
US2 (Progress) ┘

US3 (Checkpointing) ──> Depends on: US1 (needs import workflow)

US4 (Browsing) ───┐
                  ├──> Can be developed independently
US5 (Tag Filtering) ┘

US6 (Two-Phase) ──> Depends on: US1 (needs import workflow), US3 (needs checkpointing)
```

**Recommended Order**:
1. US1 + US2 (can be parallel, US1 is MVP)
2. US3 (after US1 complete)
3. US4 + US5 (can be parallel)
4. US6 (after US1 and US3 complete)

### Parallel Execution Examples

**Phase 3 (US1) - Can parallelize**:
- T021-T029 (ZoteroImporterAdapter implementation) - different methods, can work in parallel
- T030-T037 (BatchImportFromZotero use case) - different sections of workflow
- T038-T043 (CLI and MCP integration) - separate files, can work in parallel

**Phase 4 (US2) - Can parallelize**:
- T044-T049 (RichProgressReporterAdapter implementation) - different methods
- T050-T054 (Use case integration) - can work after T044-T049 complete

**Phase 6 (US4) - Can parallelize**:
- T069-T070 (ZoteroImporterAdapter methods) - different methods (T068 moved to US3, T023 already implements list_collections)
- T071-T077 (CLI commands) - separate commands, can work in parallel

**Phase 7 (US5) - Can parallelize**:
- T078-T082 (Filtering logic) - internal implementation
- T083-T086 (CLI and MCP integration) - separate from logic

## Implementation Strategy

**MVP Scope**: User Story 1 (Import Documents from Zotero Collections) delivers core value and can be fully tested independently.

**Incremental Delivery**:
1. **MVP**: US1 only - enables basic Zotero collection import
2. **Enhanced**: US1 + US2 - adds progress indication for better UX
3. **Reliable**: US1 + US2 + US3 - adds checkpointing for large batches
4. **Exploration**: US4 - enables library browsing before import
5. **Selective**: US5 - enables tag-based filtering for targeted imports
6. **Fault-Tolerant**: US6 - adds two-phase import for better fault tolerance

Each increment delivers independently testable value and can be demonstrated to users.

## Task Summary

**Total Tasks**: 107 (T068 moved from US4 to US3; duplicate removed)

**By Phase**:
- Phase 1 (Setup): 3 tasks
- Phase 2 (Foundational): 17 tasks
- Phase 3 (US1 - Import): 23 tasks
- Phase 4 (US2 - Progress): 11 tasks
- Phase 5 (US3 - Checkpointing): 14 tasks (includes T068 for checkpoint file disappearance handling)
- Phase 6 (US4 - Browsing): 9 tasks (T068 removed as duplicate, already covered by T023 in Phase 3)
- Phase 7 (US5 - Tag Filtering): 9 tasks
- Phase 8 (US6 - Two-Phase): 7 tasks
- Phase 9 (Polish): 14 tasks

**Parallelizable Tasks**: Tasks marked [P] can be worked on simultaneously by different developers

**MVP Tasks**: Phase 3 (US1) - 23 tasks for core import functionality

