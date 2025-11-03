# Tasks: Comprehensive Zotero Integration Improvements

**Input**: Design documents from `/specs/005-zotero-improvements/`  
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓, quickstart.md ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and directory structure

- [X] T001 [P] Verify existing project structure matches plan.md (src/domain, src/application, src/infrastructure)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain models, error types, and port interfaces that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Domain Models

- [X] T002 [US4] Create ContentFingerprint entity in src/domain/models/content_fingerprint.py with content_hash, file_mtime, file_size, embedding_model, chunking_policy_version, embedding_policy_version fields
- [X] T003 [US4] Implement ContentFingerprint validation in __post_init__ method in src/domain/models/content_fingerprint.py
- [X] T004 [US4] Implement ContentFingerprint.matches() method for fingerprint comparison in src/domain/models/content_fingerprint.py
- [X] T005 [US4] Implement ContentFingerprint.to_dict() and from_dict() methods for serialization in src/domain/models/content_fingerprint.py
- [X] T006 [US5] Enhance DownloadManifestAttachment with source field ("local" | "web") in src/domain/models/download_manifest.py
- [X] T007 [US4,US5] Enhance DownloadManifestAttachment with content_fingerprint field (ContentFingerprint | None) in src/domain/models/download_manifest.py
- [X] T008 [US5] Update DownloadManifestAttachment.to_dict() to include source and content_fingerprint fields in src/domain/models/download_manifest.py
- [X] T009 [US5] Update DownloadManifestAttachment.from_dict() to deserialize source and content_fingerprint fields in src/domain/models/download_manifest.py
- [X] T010 [US5] Add validation for source field in DownloadManifestAttachment.__post_init__ in src/domain/models/download_manifest.py

### Domain Services

- [X] T011 [US4] Create ContentFingerprintService domain service in src/domain/services/content_fingerprint.py
- [X] T012 [US4] Implement ContentFingerprintService.compute_fingerprint() static method in src/domain/services/content_fingerprint.py
- [X] T013 [US4] Implement ContentFingerprintService.is_unchanged() static method for fingerprint comparison in src/domain/services/content_fingerprint.py

### Error Types

- [X] T014 [US1] Add ZoteroDatabaseLockedError exception class in src/domain/errors.py
- [X] T015 [US1] Add ZoteroDatabaseNotFoundError exception class in src/domain/errors.py
- [X] T016 [US1] Add ZoteroProfileNotFoundError exception class in src/domain/errors.py
- [X] T017 [US1] Add ZoteroPathResolutionError exception class in src/domain/errors.py
- [X] T018 [US2] Add ZoteroFulltextNotFoundError exception class in src/domain/errors.py
- [X] T019 [US2] Add ZoteroFulltextQualityError exception class in src/domain/errors.py
- [X] T020 [US3] Add ZoteroAnnotationNotFoundError exception class in src/domain/errors.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Offline Library Browsing and Instant Collection Access (Priority: P1) 🎯 MVP

**Goal**: Enable browsing Zotero library structure, viewing collections, and exploring items instantly without internet connection or API rate limits, using local SQLite database access.

**Independent Test**: Can be fully tested by detecting Zotero profile on local machine, opening SQLite database in read-only immutable mode, listing collections with hierarchy and item counts, browsing a specific collection to see first 10 items with attachment counts, and verifying all operations complete instantly without network calls.

### Implementation for User Story 1

- [X] T021 [US1] Create LocalZoteroDbAdapter class skeleton in src/infrastructure/adapters/zotero_local_db.py implementing ZoteroImporterPort
- [X] T022 [US1] Implement platform detection method _detect_zotero_profile() in src/infrastructure/adapters/zotero_local_db.py for Windows/macOS/Linux
- [X] T023 [US1] Implement _parse_profiles_ini() method to find default profile in src/infrastructure/adapters/zotero_local_db.py
- [X] T024 [US1] Implement _open_db_readonly() method using SQLite URI mode with immutable=1&mode=ro flags in src/infrastructure/adapters/zotero_local_db.py
- [X] T025 [US1] Implement LocalZoteroDbAdapter.list_collections() using SQL query on collections table with hierarchy and item counts in src/infrastructure/adapters/zotero_local_db.py
- [X] T026 [US1] Implement LocalZoteroDbAdapter.get_collection_items() using recursive CTE for subcollections in src/infrastructure/adapters/zotero_local_db.py
- [X] T027 [US1] Implement LocalZoteroDbAdapter.get_item_attachments() using SQL query on itemAttachments table in src/infrastructure/adapters/zotero_local_db.py
- [X] T028 [US1] Implement LocalZoteroDbAdapter.resolve_attachment_path() distinguishing linkMode=0 (imported) vs linkMode=1 (linked) in src/infrastructure/adapters/zotero_local_db.py
- [X] T029 [US1] Implement LocalZoteroDbAdapter.download_attachment() to copy files from local storage in src/infrastructure/adapters/zotero_local_db.py
- [X] T030 [US1] Implement LocalZoteroDbAdapter.get_item_metadata() extracting from items.data JSON field in src/infrastructure/adapters/zotero_local_db.py
- [X] T031 [US1] Implement LocalZoteroDbAdapter.list_tags() using SQL query with usage counts in src/infrastructure/adapters/zotero_local_db.py
- [X] T032 [US1] Implement LocalZoteroDbAdapter.get_recent_items(limit=10) sorted by dateAdded descending in src/infrastructure/adapters/zotero_local_db.py with default limit of 10 items
- [X] T033 [US1] Implement LocalZoteroDbAdapter.find_collection_by_name() with case-insensitive partial match in src/infrastructure/adapters/zotero_local_db.py
- [X] T034 [US1] Implement LocalZoteroDbAdapter.can_resolve_locally() optional method for source routing in src/infrastructure/adapters/zotero_local_db.py
- [X] T035 [US1] Add error handling for database locks (ZoteroDatabaseLockedError) with fallback support in src/infrastructure/adapters/zotero_local_db.py
- [X] T036 [US1] Add error handling for missing database (ZoteroDatabaseNotFoundError) in src/infrastructure/adapters/zotero_local_db.py
- [X] T037 [US1] Add error handling for missing profile (ZoteroProfileNotFoundError) in src/infrastructure/adapters/zotero_local_db.py
- [X] T038 [US1] Add error handling for path resolution failures (ZoteroPathResolutionError) in src/infrastructure/adapters/zotero_local_db.py
- [X] T039 [US1] Create zotero CLI command group in src/infrastructure/cli/commands/zotero.py
- [X] T040 [US1] Implement list-collections command displaying hierarchical collection structure (parent-child relationships with indentation) with item counts in src/infrastructure/cli/commands/zotero.py
- [X] T041 [US1] Implement browse-collection command displaying first N items (default 20, configurable via --limit option) with metadata in src/infrastructure/cli/commands/zotero.py
- [X] T042 [US1] Register zotero command group in src/infrastructure/cli/main.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Fast Import with Full-Text Reuse (Priority: P1)

**Goal**: Import documents from Zotero collections significantly faster by reusing text that Zotero has already extracted, skipping Docling conversion/OCR for documents with available fulltext (50-80% speedup), while still chunking, embedding, and indexing all documents.

**Independent Test**: Can be fully tested by importing a collection containing 20 documents where 15 have Zotero fulltext available, verifying that those 15 use fast path (skipping Docling conversion but still chunked, embedded, and indexed), measuring total import time, and comparing to baseline without full-text reuse.

### Implementation for User Story 2

- [X] T043 [US2] Create FulltextResolverPort protocol in src/application/ports/fulltext_resolver.py
- [X] T044 [US2] Create FulltextResult dataclass with text, source, pages_from_zotero, pages_from_docling, zotero_quality_score fields in src/application/ports/fulltext_resolver.py
- [X] T045 [US2] Create ZoteroFulltextResolverAdapter class in src/infrastructure/adapters/zotero_fulltext_resolver.py implementing FulltextResolverPort
- [X] T046 [US2] Implement ZoteroFulltextResolverAdapter.get_zotero_fulltext() querying fulltext table via SQLite in src/infrastructure/adapters/zotero_fulltext_resolver.py
- [X] T047 [US2] Implement fulltext quality validation (non-empty, minimum length, structure checks) in src/infrastructure/adapters/zotero_fulltext_resolver.py
- [X] T048 [US2] Implement ZoteroFulltextResolverAdapter.resolve_fulltext() with Zotero preference and Docling fallback in src/infrastructure/adapters/zotero_fulltext_resolver.py
- [X] T049 [US2] Implement page-level mixed provenance tracking (pages_from_zotero, pages_from_docling) in src/infrastructure/adapters/zotero_fulltext_resolver.py
- [X] T050 [US2] Implement sequential page concatenation for mixed provenance text in src/infrastructure/adapters/zotero_fulltext_resolver.py
- [X] T051 [US2] Integrate FulltextResolver into ingest_document use case before Docling conversion in src/application/use_cases/ingest_document.py
- [X] T052 [US2] Update ingest_document to use fulltext when available, skip Docling conversion but proceed with chunking/embedding/indexing in src/application/use_cases/ingest_document.py
- [X] T053 [US2] Add fulltext provenance metadata to audit logs in src/application/use_cases/ingest_document.py
- [X] T054 [US2] Add prefer_zotero_fulltext configuration option to Settings in src/infrastructure/config/settings.py
- [X] T055 [US2] Add prefer_zotero_fulltext CLI option to ingest command in src/infrastructure/cli/commands/ingest.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - High-Quality Retrieval with Annotation Indexing (Priority: P2)

**Goal**: Index PDF annotations (highlights, comments, notes) from Zotero as separate searchable vector points, enabling focused queries on annotations and improving retrieval quality.

**Independent Test**: Can be fully tested by importing a collection with PDFs containing Zotero annotations (highlights and comments), enabling annotation indexing, verifying annotations are fetched via Web API, normalized correctly (page, quote, comment, color, tags), indexed as separate vector points with type:annotation tag, and can be queried with "only annotations" filters.

### Implementation for User Story 3

- [X] T056 [US3] Create Annotation dataclass with page, quote, comment, color, tags fields in src/infrastructure/adapters/zotero_annotation_resolver.py
- [X] T057 [US3] Create AnnotationResolverPort protocol in src/application/ports/annotation_resolver.py
- [X] T058 [US3] Create ZoteroAnnotationResolverAdapter class in src/infrastructure/adapters/zotero_annotation_resolver.py implementing AnnotationResolverPort
- [X] T059 [US3] Implement ZoteroAnnotationResolverAdapter.fetch_annotations() using Web API children() method with itemType=annotation in src/infrastructure/adapters/zotero_annotation_resolver.py
- [X] T060 [US3] Implement annotation normalization (pageIndex → page, extract quote/comment/color/tags) in src/infrastructure/adapters/zotero_annotation_resolver.py
- [X] T061 [US3] Implement retry logic with exponential backoff (3 retries, base 1s, max 30s, jitter) for annotation fetching in src/infrastructure/adapters/zotero_annotation_resolver.py
- [X] T062 [US3] Implement graceful skipping when annotations unavailable (log warning, continue import) in src/infrastructure/adapters/zotero_annotation_resolver.py
- [X] T063 [US3] Implement ZoteroAnnotationResolverAdapter.index_annotations() creating annotation payloads with type:annotation tag in src/infrastructure/adapters/zotero_annotation_resolver.py
- [X] T064 [US3] Create annotation payload structure with zotero.item_key, zotero.attachment_key, zotero.annotation.* fields in src/infrastructure/adapters/zotero_annotation_resolver.py
- [X] T065 [US3] Integrate AnnotationResolver into batch_import_from_zotero use case when include_annotations=true in src/application/use_cases/batch_import_from_zotero.py
- [X] T066 [US3] Call AnnotationResolver.index_annotations() after document processing for each PDF attachment in src/application/use_cases/batch_import_from_zotero.py
- [X] T067 [US3] Add include_annotations configuration option to Settings in src/infrastructure/config/settings.py
- [X] T068 [US3] Add include_annotations CLI option to ingest command in src/infrastructure/cli/commands/ingest.py

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently

---

## Phase 6: User Story 4 - Reliable Re-Imports with Incremental Deduplication (Priority: P2)

**Goal**: Enable re-importing collections without re-processing unchanged documents, detecting unchanged documents via content fingerprints and skipping processing to save time and computational resources.

**Independent Test**: Can be fully tested by importing a collection of 50 documents, then re-importing the same collection with one new document added, verifying that the 50 unchanged documents are detected via content hash comparison and skipped (no re-extraction, re-embedding, or re-storage), only the new document is processed, and total re-import time is proportional to new documents only.

### Implementation for User Story 4

- [ ] T069 [US4] Integrate ContentFingerprintService.compute_fingerprint() into batch_import_from_zotero before document processing in src/application/use_cases/batch_import_from_zotero.py
- [ ] T070 [US4] Implement fingerprint comparison logic checking stored vs computed fingerprints in batch_import_from_zotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T071 [US4] Implement skip logic for unchanged documents: skip processing only if both hash AND metadata (mtime + size) match exactly; if hash matches but metadata differs, treat as changed document and perform full re-processing (collision protection per FR-019)
- [ ] T072 [US4] Implement policy version checking to invalidate fingerprints on policy changes in batch_import_from_zotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T073 [US4] Store content fingerprint in DownloadManifestAttachment after successful download in batch_import_from_zotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T074 [US4] Update content fingerprint in manifest after document processing completes in batch_import_from_zotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T075 [US4] Add logging for skipped unchanged documents in batch_import_from_zotero use case in src/application/use_cases/batch_import_from_zotero.py

**Checkpoint**: At this point, User Stories 1, 2, 3, AND 4 should all work independently

---

## Phase 7: User Story 5 - Flexible Source Selection with Smart Routing (Priority: P2)

**Goal**: Enable control over whether CiteLoom uses local Zotero database or Web API for imports, with automatic fallback between sources based on strategy mode (local-first, web-first, auto, local-only, web-only).

**Independent Test**: Can be fully tested by configuring source router with local-first strategy, attempting import where some files exist locally and some don't, verifying local files use local DB, missing files fall back to Web API download, and source markers in manifest correctly indicate which files came from which source.

### Implementation for User Story 5

- [ ] T076 [US5] Create ZoteroSourceRouter application service class in src/application/services/zotero_source_router.py
- [ ] T077 [US5] Implement ZoteroSourceRouter.__init__() accepting local_adapter, web_adapter, and strategy mode in src/application/services/zotero_source_router.py
- [ ] T078 [US5] Implement local-first strategy with per-file fallback to Web API in src/application/services/zotero_source_router.py
- [ ] T079 [US5] Implement web-first strategy with fallback to local DB on rate limits in src/application/services/zotero_source_router.py
- [ ] T080 [US5] Implement auto strategy with intelligent source selection: prefer local if DB available and files exist locally, prefer web if local unavailable or files missing, smart selection based on speed and completeness with automatic fallback, logging selection strategy used (see FR-024)
- [ ] T081 [US5] Implement local-only strict mode (no fallback) in src/application/services/zotero_source_router.py
- [ ] T082 [US5] Implement web-only strict mode (no fallback, backward compatible) in src/application/services/zotero_source_router.py
- [ ] T083 [US5] Implement ZoteroSourceRouter.download_attachment() returning (file_path, source_marker) tuple in src/application/services/zotero_source_router.py
- [ ] T084 [US5] Implement ZoteroSourceRouter.list_collections() with strategy-based routing in src/application/services/zotero_source_router.py
- [ ] T085 [US5] Implement ZoteroSourceRouter.get_collection_items() with strategy-based routing in src/application/services/zotero_source_router.py
- [ ] T086 [US5] Integrate ZoteroSourceRouter into batch_import_from_zotero use case replacing direct adapter usage in src/application/use_cases/batch_import_from_zotero.py
- [ ] T087 [US5] Store source markers ("local" | "web") in DownloadManifestAttachment.source field in batch_import_from_zotero use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T088 [US5] Add mode configuration option (local-first, web-first, auto, local-only, web-only) to Settings in src/infrastructure/config/settings.py
- [ ] T089 [US5] Add mode CLI option to ingest command with default web-first for backward compatibility in src/infrastructure/cli/commands/ingest.py

**Checkpoint**: At this point, User Stories 1, 2, 3, 4, AND 5 should all work independently

---

## Phase 8: User Story 6 - Enhanced Library Exploration with Offline Browsing (Priority: P3)

**Goal**: Enable comprehensive library exploration before importing, including viewing collection hierarchies, browsing tags with usage counts, seeing recent items, and previewing collection contents, all working offline using local database access.

**Independent Test**: Can be fully tested by running collection listing, browsing a collection, listing tags with usage counts, viewing recent items, and verifying all operations work offline using local database, complete quickly (under 5 seconds), and provide useful information for import planning.

### Implementation for User Story 6

- [ ] T090 [US6] Implement list-tags command displaying tags with usage counts in src/infrastructure/cli/commands/zotero.py
- [ ] T091 [US6] Implement recent-items command displaying N most recent items (default 10, configurable via --limit option) sorted by dateAdded descending in src/infrastructure/cli/commands/zotero.py
- [ ] T092 [US6] Enhance list-collections command to show hierarchical structure with indentation in src/infrastructure/cli/commands/zotero.py
- [ ] T093 [US6] Enhance browse-collection command to show more metadata (publication years, creators) in src/infrastructure/cli/commands/zotero.py

**Checkpoint**: At this point, User Stories 1-6 should all work independently

---

## Phase 9: User Story 7 - Better Traceability with Zotero Key Enrichment (Priority: P3)

**Goal**: Add zotero.item_key and zotero.attachment_key fields to chunk payloads and create keyword indexes for fast queries, enabling targeted queries by Zotero item or attachment.

**Independent Test**: Can be fully tested by importing a collection, verifying that chunk payloads include zotero.item_key and zotero.attachment_key, testing queries filtered by these keys return correct chunks, and verifying indexes enable fast lookups (< 500ms for 10k chunks).

### Implementation for User Story 7

- [ ] T094 [US7] Enhance chunk payload creation to include zotero.item_key and zotero.attachment_key fields in ingest_document use case in src/application/use_cases/ingest_document.py
- [ ] T095 [US7] Create keyword indexes on both zotero.item_key and zotero.attachment_key fields together in QdrantIndexAdapter.ensure_collection() in src/infrastructure/adapters/qdrant_index.py (both indexes created in single operation)
- [ ] T096 [US7] Implement query filtering by zotero.item_key or zotero.attachment_key in QueryChunks use case or QdrantIndexAdapter search methods to enable FR-029 filtered queries in src/application/use_cases/query_chunks.py or src/infrastructure/adapters/qdrant_index.py
- [ ] T097 [US7] Pass zotero.item_key and zotero.attachment_key from batch_import_from_zotero to ingest_document use case in src/application/use_cases/batch_import_from_zotero.py
- [ ] T098 [US7] Ensure zotero keys are included in annotation payloads as well in AnnotationResolver in src/infrastructure/adapters/zotero_annotation_resolver.py

**Checkpoint**: At this point, User Stories 1-7 should all work independently

---

## Phase 10: User Story 8 - Clear Diagnostics for Embedding Model Mismatches (Priority: P3)

**Goal**: Enhance embedding model mismatch error messages to be friendly and actionable, providing clear guidance on bound model, requested model, and resolution steps.

**Independent Test**: Can be fully tested by creating a collection with one embedding model, attempting to write chunks with a different model, verifying that a friendly error message appears explaining the mismatch and suggesting solutions, and confirming that --force-rebuild flag bypasses the guard when migration is intended.

### Implementation for User Story 8

- [ ] T099 [US8] Enhance EmbeddingModelMismatch error message to include collection name and resolution instructions in src/infrastructure/adapters/qdrant_index.py
- [ ] T100 [US8] Add --show-embedding-model option to inspect CLI command in src/infrastructure/cli/commands/inspect.py
- [ ] T101 [US8] Implement embedding model display in inspect command querying collection metadata in src/infrastructure/cli/commands/inspect.py
- [ ] T102 [US8] Expose embedding model information in MCP inspect tool response in src/infrastructure/mcp/tools.py

**Checkpoint**: At this point, all User Stories 1-8 should be complete

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final polish

### Configuration

- [ ] T103 [P] Add Zotero configuration section to Settings with mode, db_path, storage_dir, include_annotations, prefer_zotero_fulltext in src/infrastructure/config/settings.py
- [ ] T104 [P] Add zotero.web configuration subsection with library_id and api_key in src/infrastructure/config/settings.py
- [ ] T105 [P] Add zotero.fulltext configuration subsection with min_length threshold in src/infrastructure/config/settings.py
- [ ] T106 [P] Update citeloom.toml example configuration with complete Zotero section including all FR-037 options: mode (default web-first), db_path (optional override), storage_dir (optional), include_annotations (default false), prefer_zotero_fulltext (default true), and zotero.web subsection with library_id and api_key

### Documentation

- [ ] T107 [P] Create platform-specific Zotero profile paths guide in docs/zotero-local-access.md
- [ ] T108 [P] Create annotation indexing guide in docs/zotero-annotations.md
- [ ] T109 [P] Create full-text reuse policy explanation in docs/zotero-fulltext-reuse.md
- [ ] T110 [P] Create embedding model governance guide in docs/embedding-governance.md
- [ ] T111 [P] Update README.md with new Zotero features and configuration options

### Testing

- [ ] T112 [P] Create integration test for LocalZoteroDbAdapter profile detection in tests/integration/test_zotero_local_db.py
- [ ] T113 [P] Create integration test for LocalZoteroDbAdapter SQL queries in tests/integration/test_zotero_local_db.py
- [ ] T114 [P] Create integration test for LocalZoteroDbAdapter path resolution in tests/integration/test_zotero_local_db.py
- [ ] T115 [P] Create integration test for FulltextResolver fulltext preference and fallback in tests/integration/test_zotero_fulltext.py
- [ ] T116 [P] Create integration test for FulltextResolver mixed provenance in tests/integration/test_zotero_fulltext.py
- [ ] T117 [P] Create integration test for AnnotationResolver extraction and indexing in tests/integration/test_zotero_annotations.py
- [ ] T118 [P] Create integration test for incremental deduplication in tests/integration/test_zotero_deduplication.py
- [ ] T119 [P] Create integration test for source router strategies in tests/integration/test_zotero_source_router.py
- [ ] T120 [P] Create unit test for ContentFingerprint entity validation in tests/unit/test_domain_models.py
- [ ] T121 [P] Create unit test for ContentFingerprintService fingerprint computation in tests/unit/test_domain_models.py
- [ ] T122 [P] Create unit test for ZoteroSourceRouter strategy logic with doubles in tests/unit/test_zotero_source_router.py
- [ ] T127 [P] Create performance test for query-by-zotero-key filtering (< 500ms for 10k chunks per SC-006) in tests/integration/test_zotero_query_performance.py
- [ ] T128 [P] Create performance test for collection browsing operations (< 2 seconds per SC-001) in tests/integration/test_zotero_browsing_performance.py
- [ ] T129 [P] Create performance test for import speedup with fulltext reuse (50-80% speedup per SC-002) in tests/integration/test_zotero_fulltext_performance.py
- [ ] T130 [P] Create integration test for offline operation validation (100% offline success per SC-008) in tests/integration/test_zotero_offline.py

### Code Quality

- [ ] T123 [P] Run ruff format and check on all new files
- [ ] T124 [P] Run mypy type checking on all new files
- [ ] T125 [P] Verify architecture tests pass (no new dependency violations)
- [ ] T126 [P] Run quickstart.md validation workflow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - User stories can proceed sequentially in priority order (P1 → P2 → P3)
  - Or in parallel if staffed (US1 and US2 can be parallel after Foundational)
- **Polish (Phase 11)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Uses LocalZoteroDbAdapter from US1 for fulltext queries
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Independent, uses existing Web API
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - Independent, uses ContentFingerprint from Phase 2
- **User Story 5 (P2)**: Can start after Foundational (Phase 2) - Requires LocalZoteroDbAdapter from US1, enhances batch_import_from_zotero
- **User Story 6 (P3)**: Can start after US1 completion - Builds on LocalZoteroDbAdapter CLI commands
- **User Story 7 (P3)**: Can start after Foundational (Phase 2) - Independent, payload enhancement
- **User Story 8 (P3)**: Can start after Foundational (Phase 2) - Independent, enhances existing error handling

### Within Each User Story

- Domain models before services
- Services before adapters
- Adapters before use cases
- Use cases before CLI commands
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T002-T013 (domain models and services) can run in parallel
- T014-T020 (error types) can run in parallel
- All foundational tasks can proceed in parallel after T001

**Phase 3 (US1)**:
- T022-T024 (platform detection, profile parsing, DB opening) can run in parallel
- T025-T033 (port method implementations) can run in parallel
- T035-T038 (error handling) can run in parallel
- T039-T042 (CLI commands) can run in parallel after adapter complete

**Phase 4 (US2)**:
- T043-T044 (port definition) can run in parallel
- T046-T050 (adapter implementation) can run sequentially
- T054-T055 (configuration) can run in parallel

**Phase 5 (US3)**:
- T056-T057 (domain models and port) can run in parallel
- T059-T063 (adapter implementation) can run sequentially
- T067-T068 (configuration) can run in parallel

**Phase 6 (US4)**:
- T069-T075 (integration tasks) run sequentially

**Phase 7 (US5)**:
- T078-T082 (strategy implementations) can run in parallel
- T088-T089 (configuration) can run in parallel

**Phase 8 (US6)**:
- T090-T093 (CLI command enhancements) can run in parallel

**Phase 9 (US7)**:
- T094-T098 (payload and index enhancements) can run in parallel after T094

**Phase 10 (US8)**:
- T099-T102 (diagnostics enhancements) can run in parallel

**Phase 11 (Polish)**:
- All tasks marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch foundational domain models in parallel:
Task: "Create ContentFingerprint entity in src/domain/models/content_fingerprint.py"
Task: "Enhance DownloadManifestAttachment with source field in src/domain/models/download_manifest.py"
Task: "Add ZoteroDatabaseLockedError exception class in src/domain/errors.py"

# Launch US1 adapter methods in parallel (after skeleton created):
Task: "Implement platform detection method _detect_zotero_profile() in src/infrastructure/adapters/zotero_local_db.py"
Task: "Implement LocalZoteroDbAdapter.list_collections() using SQL query in src/infrastructure/adapters/zotero_local_db.py"
Task: "Implement LocalZoteroDbAdapter.get_collection_items() using recursive CTE in src/infrastructure/adapters/zotero_local_db.py"

# Launch CLI commands in parallel (after adapter complete):
Task: "Implement list-collections command in src/infrastructure/cli/commands/zotero.py"
Task: "Implement browse-collection command in src/infrastructure/cli/commands/zotero.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Offline Library Browsing)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo (50-80% speedup)
4. Add User Story 3 → Test independently → Deploy/Demo (Annotation indexing)
5. Add User Story 4 → Test independently → Deploy/Demo (Deduplication)
6. Add User Story 5 → Test independently → Deploy/Demo (Source routing)
7. Add User Stories 6-8 → Test independently → Deploy/Demo (Enhancements)
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Local SQLite Adapter) - MVP
   - Developer B: User Story 2 (Full-Text Reuse) - Requires US1 for fulltext queries
   - Developer C: User Story 4 (Deduplication) - Independent
3. After US1 completes:
   - Developer A: User Story 5 (Source Router) - Requires US1
   - Developer B: Continue US2 integration
   - Developer C: Continue US4
4. After core features complete:
   - Developer A: User Story 6 (Library Exploration)
   - Developer B: User Story 7 (Key Enrichment)
   - Developer C: User Story 8 (Embedding Diagnostics)
5. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies within same story
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (if TDD approach used)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Reference quickstart.md for implementation guidance
- Reference research.md for implementation patterns from zotero-mcp
- Reference contracts/ports.md for interface definitions

---

## Task Summary

**Total Tasks**: 130 tasks across 11 phases

**Tasks by Phase**:
- Phase 1 (Setup): 1 task
- Phase 2 (Foundational): 20 tasks (blocking - must complete first)
- Phase 3 (US1 - P1 MVP): 22 tasks
- Phase 4 (US2 - P1): 13 tasks
- Phase 5 (US3 - P2): 13 tasks
- Phase 6 (US4 - P2): 7 tasks
- Phase 7 (US5 - P2): 14 tasks
- Phase 8 (US6 - P3): 4 tasks
- Phase 9 (US7 - P3): 5 tasks
- Phase 10 (US8 - P3): 4 tasks
- Phase 11 (Polish): 28 tasks

**Tasks by User Story**:
- User Story 1: 22 tasks
- User Story 2: 13 tasks
- User Story 3: 13 tasks
- User Story 4: 7 tasks (plus 5 foundational tasks)
- User Story 5: 14 tasks (plus 2 foundational tasks)
- User Story 6: 4 tasks
- User Story 7: 5 tasks
- User Story 8: 4 tasks

**Parallel Opportunities Identified**: 
- Phase 2: 15 tasks can run in parallel
- Phase 3: 18 tasks can run in parallel (within adapter methods)
- Phase 4-10: Multiple parallel opportunities within each story
- Phase 11: 22 tasks can run in parallel

**Suggested MVP Scope**: 
- Phase 1 (Setup): 1 task
- Phase 2 (Foundational): 20 tasks (required)
- Phase 3 (User Story 1): 22 tasks
- **Total MVP**: 43 tasks for offline library browsing capability

**Independent Test Criteria**:
- **US1**: Detect profile, open DB, list collections, browse collection, verify < 2 seconds offline
- **US2**: Import 20 docs (15 with fulltext), verify fast path used, measure 50-80% speedup
- **US3**: Import collection with annotations, verify separate vector points indexed
- **US4**: Re-import unchanged collection, verify all skipped, < 30 seconds
- **US5**: Configure local-first, import with mixed sources, verify source markers
- **US6**: Run all browsing commands offline, verify < 5 seconds
- **US7**: Import collection, verify keys in payloads, query by keys, < 500ms
- **US8**: Create collection with model, attempt different model, verify friendly error

---

**Tasks Status**: ✅ Complete - 130 tasks organized by user story, ready for implementation

