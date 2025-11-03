# Tasks: Fix Zotero & Docling Performance and Correctness Issues

**Input**: Design documents from `/specs/006-fix-zotero-docling/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: Tests are included for critical correctness fixes (US2) and resource sharing (US4). Other stories focus on performance/UX improvements that can be verified via integration testing.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Verification)

**Purpose**: Verify existing project structure and dependencies

- [X] T001 Verify Python 3.12.x environment is active (check `.python-version`)
- [X] T002 [P] Verify dependencies are synced (`uv sync` completes successfully)
- [X] T003 [P] Verify existing test suite passes (`uv run pytest -q`)

**Checkpoint**: Project is ready for feature implementation

---

## Phase 2: Foundational (Critical Prerequisites)

**Purpose**: Core infrastructure fixes that MUST be complete before user story implementation

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Create factory function `get_converter()` with module-level cache in `src/infrastructure/adapters/docling_converter.py`
- [X] T005 Verify `RichProgressReporterAdapter` exists and is functional in `src/infrastructure/adapters/rich_progress_reporter.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Fast Zotero Collection Browsing (Priority: P1) 🎯 MVP

**Goal**: Reduce Zotero API calls by 50%+ through command-scoped caching, enabling browsing 10 items in under 10 seconds (down from 35+ seconds)

**Independent Test**: Browse a collection with 10 items and measure API call count and response time. Success: <10 seconds with at least 50% reduction in API calls compared to current implementation.

**Functional Requirements**: FR-001, FR-002, FR-003, FR-006

### Tests for User Story 1

- [ ] T006 [P] [US1] Add test for collection cache hit/miss behavior in `tests/integration/test_zotero_caching.py`
- [ ] T007 [P] [US1] Add test for item metadata cache reuse in `tests/integration/test_zotero_caching.py`
- [ ] T008 [P] [US1] Add test for command-scoped cache cleanup in `tests/integration/test_zotero_caching.py`

### Implementation for User Story 1

- [X] T009 [US1] Add `collection_cache` parameter to `get_collection_info()` method in `src/infrastructure/adapters/zotero_importer.py`
- [X] T010 [US1] Add `collection_cache` parameter to `get_item_metadata()` method in `src/infrastructure/adapters/zotero_importer.py`
- [X] T011 [US1] Implement cache lookup logic in `get_item_metadata()` to use cached collection info when available
- [X] T012 [US1] Create command-scoped `collection_cache` dictionary in `browse_collection()` function in `src/infrastructure/cli/commands/zotero.py`
- [X] T013 [US1] Create command-scoped `item_cache` dictionary in `browse_collection()` function in `src/infrastructure/cli/commands/zotero.py`
- [X] T014 [US1] Pass `collection_cache` to `get_collection_info()` call in `browse_collection()` function
- [X] T015 [US1] Pass `collection_cache` to `get_item_metadata()` calls during item iteration in `browse_collection()` function
- [X] T016 [US1] Reuse item metadata from `item_cache` when displaying metadata summary section in `browse_collection()` function
- [X] T017 [US1] Use basic item data (title, creators, date) directly from collection items response when displaying item table in `browse_collection()` function

**Checkpoint**: User Story 1 complete - browsing 10 items completes in <10 seconds with 50%+ API call reduction

---

## Phase 4: User Story 2 - Accurate Document Conversion and Chunking (Priority: P1)

**Goal**: Fix page and heading extraction bugs, ensuring multi-page documents produce multiple chunks (15-40 for 20+ pages) with accurate page mapping and heading structure

**Independent Test**: Convert a known 20-page document with clear headings and verify: (1) page count = 20 (not 1), (2) heading tree is populated, (3) 15-40 chunks are created. Success: accurate page count, heading structure extracted, multiple chunks proportional to document size.

**Functional Requirements**: FR-012, FR-013, FR-014, FR-021, FR-024

### Tests for User Story 2

- [X] T018 [P] [US2] Add test for page map extraction with multi-page document in `tests/integration/test_docling_page_extraction.py`
- [X] T019 [P] [US2] Add test for heading tree extraction with document containing headings in `tests/integration/test_docling_heading_extraction.py`
- [X] T020 [P] [US2] Add test for chunk creation producing multiple chunks from large document in `tests/integration/test_docling_chunking.py`
- [X] T021 [P] [US2] Add test for manual chunking fallback on Windows producing multiple chunks in `tests/integration/test_docling_chunking.py`

### Implementation for User Story 2

- [X] T022 [US2] Fix `_extract_page_map()` method to correctly extract page boundaries from Docling Document in `src/infrastructure/adapters/docling_converter.py`
- [X] T023 [US2] Add diagnostic logging for page map extraction failures in `_extract_page_map()` method
- [X] T024 [US2] Fix `_extract_heading_tree()` method to correctly extract heading hierarchy from Docling Document in `src/infrastructure/adapters/docling_converter.py`
- [X] T025 [US2] Add diagnostic logging for heading tree extraction failures in `_extract_heading_tree()` method
- [X] T026 [US2] Investigate and fix why only 1 chunk created from large documents in `src/infrastructure/adapters/docling_chunker.py`
- [X] T027 [US2] Improve manual chunking fallback to produce multiple chunks proportional to document size in `src/infrastructure/adapters/docling_chunker.py`
- [X] T028 [US2] Add diagnostic logging for quality filtering decisions (why chunks are filtered) in `src/infrastructure/adapters/docling_chunker.py`
- [X] T029 [US2] Review and adjust quality filtering thresholds to ensure reasonable chunk counts (not filtering all but one) in `src/infrastructure/adapters/docling_chunker.py`
- [X] T030 [US2] Add validation for chunk ID uniqueness with warning if collisions detected in `src/infrastructure/adapters/docling_chunker.py`

**Checkpoint**: User Story 2 complete - 20-page document produces 15-40 chunks with accurate page mapping and heading structure

---

## Phase 5: User Story 3 - Progress Feedback During Long Operations (Priority: P2)

**Goal**: Add progress indication for operations longer than 5 seconds, showing current item/page being processed and total count, with progress updates throttled to maximum once per second

**Independent Test**: Run a document conversion or collection browse operation taking >5 seconds and verify progress indicators are displayed. Success: users see progress bars, current operation description, and time estimates.

**Functional Requirements**: FR-004, FR-015

### Implementation for User Story 3

- [X] T031 [US3] Integrate `RichProgressReporterAdapter` into `convert()` method in `src/infrastructure/adapters/docling_converter.py`
- [X] T032 [US3] Add document-level progress for single document conversions in `src/infrastructure/adapters/docling_converter.py`
- [X] T033 [US3] Add progress indication to `browse_collection()` function for operations >5 seconds in `src/infrastructure/cli/commands/zotero.py`
- [X] T034 [US3] Implement progress update throttling (maximum once per second) in progress reporter integration
- [X] T035 [US3] Update `IngestDocument` use case to accept and use `ProgressReporterPort` parameter in `src/application/use_cases/ingest_document.py`
- [X] T036 [US3] Add progress stage updates (converting, chunking, embedding, storing) in `IngestDocument` use case

**Checkpoint**: User Story 3 complete - progress indication visible within 5 seconds for operations >5 seconds

---

## Phase 6: User Story 4 - Efficient Resource Management (Priority: P2)

**Goal**: Share converter and embedding model instances within same process to eliminate 2-3s initialization overhead on subsequent commands

**Independent Test**: Run multiple document ingestion commands in sequence and verify converter/model initialization happens once, not per command. Success: second and subsequent commands reuse initialized resources, eliminating 2-3s overhead.

**Functional Requirements**: FR-016, FR-017

### Tests for User Story 4

- [ ] T037 [P] [US4] Add test for converter factory returning same instance on multiple calls in `tests/integration/test_resource_factory.py`
- [ ] T038 [P] [US4] Add test for converter reuse across multiple CLI commands in same process in `tests/integration/test_resource_factory.py`

### Implementation for User Story 4

- [ ] T039 [US4] Implement module-level cache `_converter_cache` dictionary in `src/infrastructure/adapters/docling_converter.py`
- [ ] T040 [US4] Implement `get_converter()` factory function returning cached instance in `src/infrastructure/adapters/docling_converter.py`
- [ ] T041 [US4] Update `ingest run` command to use `get_converter()` factory instead of direct instantiation in `src/infrastructure/cli/commands/ingest.py`
- [ ] T042 [US4] Update MCP tools to use `get_converter()` factory in `src/infrastructure/mcp/tools.py` (if applicable)
- [ ] T043 [US4] Verify process-scoped lifetime (no inactivity-based cleanup, only process termination)
- [ ] T044a [US4] [P] [FR-017] Implement module-level cache `_embedding_model_cache` dictionary in `src/infrastructure/adapters/fastembed_embeddings.py`
- [ ] T044b [US4] [FR-017] Implement `get_embedding_model()` factory function returning cached instance in `src/infrastructure/adapters/fastembed_embeddings.py` (Note: Can be deferred if embedding model reuse is not critical for MVP)

**Checkpoint**: User Story 4 complete - second and subsequent commands reuse converter instance, eliminating 2-3s overhead

---

## Phase 7: User Story 5 - Query Works Immediately After Ingestion (Priority: P2)

**Goal**: Automatically bind embedding model to collection during ingestion so queries work immediately without manual model binding steps

**Independent Test**: Ingest a document and immediately query it. Success: query succeeds without requiring manual model binding or additional configuration.

**Functional Requirements**: FR-025, FR-026, FR-027

### Implementation for User Story 5

- [ ] T044 [US5] Add automatic model binding to collection during ingestion in `src/infrastructure/adapters/qdrant_index.py`
- [ ] T046 [US5] Verify model binding after ingestion completes successfully in `src/infrastructure/adapters/qdrant_index.py`
- [ ] T047 [US5] Improve error message when query fails due to model binding in `src/infrastructure/cli/commands/query.py`
- [ ] T048a [US5] Add actionable guidance in model binding error messages (how to resolve issue)

**Checkpoint**: User Story 5 complete - queries succeed immediately after document ingestion without manual model binding

---

## Phase 8: User Story 6 - Clean, Informative Logging (Priority: P3)

**Goal**: Suppress HTTP request logs at INFO level, showing them only in verbose mode, while keeping important progress/result information visible

**Independent Test**: Run commands and verify HTTP logs appear only in verbose mode, while important progress/result information remains visible at normal log levels. Success: default logging shows only high-level operations, HTTP logs available in verbose mode.

**Functional Requirements**: FR-008

### Implementation for User Story 6

- [ ] T049 [US6] Move HTTP request logs from INFO to DEBUG level in `src/infrastructure/logging.py`
- [ ] T050 [US6] Configure HTTP client logging to respect verbose mode flag in `src/infrastructure/logging.py`
- [ ] T051 [US6] Verify important information (progress, results, errors) remains visible at INFO level
- [ ] T052a [US6] Add summary logging for API call counts (e.g., "Made 20 API calls in 35 seconds") instead of individual request logs

**Checkpoint**: User Story 6 complete - HTTP logs suppressed in default mode, appearing only in verbose mode

---

## Phase 9: User Story 7 - Improved Local Zotero Database Access (Priority: P3)

**Goal**: Improve Windows Zotero profile detection by checking additional common paths and provide clear guidance when detection fails

**Independent Test**: Run Zotero commands on Windows with Zotero installed and verify: (1) system detects Zotero profile when possible, (2) clear guidance provided when detection fails, (3) configuration instructions accessible. Success: users can easily configure direct database access with clear error messages.

**Functional Requirements**: FR-010, FR-011, FR-009

### Implementation for User Story 7

- [ ] T053 [US7] Improve Windows Zotero profile detection by checking `%APPDATA%\Zotero` path in `src/infrastructure/adapters/zotero_local_db.py`
- [ ] T054 [US7] Improve Windows Zotero profile detection by checking `%LOCALAPPDATA%\Zotero` path in `src/infrastructure/adapters/zotero_local_db.py`
- [ ] T055 [US7] Improve Windows Zotero profile detection by checking `%USERPROFILE%\Documents\Zotero` path in `src/infrastructure/adapters/zotero_local_db.py`
- [ ] T056 [US7] Improve error message when local adapter detection fails with clear configuration instructions in `src/infrastructure/adapters/zotero_local_db.py`
- [ ] T057 [US7] Improve file not found error messages with filename variation suggestions in download processing
- [ ] T058a [US7] Update setup guide with Windows-specific Zotero profile configuration examples and troubleshooting steps in `docs/setup-guide.md`

**Checkpoint**: User Story 7 complete - improved Windows profile detection and clear error messages with actionable guidance

---

## Phase 10: Cross-Platform Timeout Enforcement (Priority: P2 - Supporting US2)

**Goal**: Implement cross-platform timeout enforcement for document conversion (not just Unix), ensuring Windows users have timeout protection

**Functional Requirements**: FR-018

### Implementation for Cross-Platform Timeout

- [ ] T059 Replace `signal.SIGALRM` timeout with `concurrent.futures.ThreadPoolExecutor` approach in `src/infrastructure/adapters/docling_converter.py`
- [ ] T060 Implement `_convert_with_timeout()` using `ThreadPoolExecutor` with timeout parameter for cross-platform support
- [ ] T061 Add timeout verification test for Windows platform in `tests/integration/test_docling_timeout.py`
- [ ] T062a Document platform behavior differences (if any) in code comments

**Checkpoint**: Cross-platform timeout enforcement complete - Windows users have timeout protection

---

## Phase 11: Additional Fixes (Supporting Multiple Stories)

**Goal**: Implement supporting fixes that improve overall system quality

**Functional Requirements**: FR-007, FR-019, FR-020, FR-023

### Implementation for Additional Fixes

- [ ] T063 [P] [FR-007] Update download manifest with actual downloaded filename accounting for duplicate filename handling (_1, _2 suffixes) in `src/application/use_cases/batch_import_from_zotero.py` (update `local_path` in `DownloadManifestAttachment` at lines 636-644 to use resolved `downloaded_path` after duplicate handling at lines 576-582)
- [ ] T064 [P] [FR-019] Use Zotero metadata language information for OCR when available in `src/infrastructure/adapters/docling_converter.py`
- [ ] T065 [P] [FR-020] Suppress unnecessary OCR warnings when OCR attempted but not needed in `src/infrastructure/adapters/docling_converter.py`
- [ ] T066a [P] [FR-023] Document Windows chunker limitations clearly explaining what works and what doesn't in `docs/windows-compatibility.md`

**Checkpoint**: Additional fixes complete

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements and validation

- [ ] T067 [P] Run full test suite and verify all tests pass (`uv run pytest -q`)
- [ ] T068 [P] Run linting and type checking (`uvx ruff check . && uv run mypy .`)
- [ ] T069 [P] Update quickstart.md validation steps with actual test commands
- [ ] T070 [P] Performance testing: Verify Zotero browsing completes in <10s for 10 items
- [ ] T071 [P] Performance testing: Verify document conversion produces multiple chunks for 20+ page documents
- [ ] T072 [P] Performance testing: Verify resource reuse eliminates initialization overhead on subsequent commands
- [ ] T073 Code review and cleanup of all modified files
- [ ] T074 Update CHANGELOG.md with feature summary

**Checkpoint**: Feature complete and ready for merge

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed) after Foundational complete
  - Or sequentially in priority order (P1 → P2 → P3)
- **Cross-Platform Timeout (Phase 10)**: Supports US2, can proceed in parallel with US2
- **Additional Fixes (Phase 11)**: Can proceed in parallel with any user story
- **Polish (Phase 12)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - May use progress reporter from US1/US2 but independently testable
- **User Story 4 (P2)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 5 (P2)**: Can start after Foundational (Phase 2) - May use converter from US4 but independently testable
- **User Story 6 (P3)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 7 (P3)**: Can start after Foundational (Phase 2) - No dependencies on other stories

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Core implementation before integration
- Story complete before moving to next priority (unless parallel execution)

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- Foundational tasks T004 and T005 can run in parallel (different files)
- Once Foundational phase completes, user stories can start in parallel:
  - US1, US2 can run in parallel (different adapters)
  - US3, US4 can run in parallel (different features)
  - US6, US7 can run in parallel (different adapters)
- All tests for a user story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T006: "Add test for collection cache hit/miss behavior in tests/integration/test_zotero_caching.py"
Task T007: "Add test for item metadata cache reuse in tests/integration/test_zotero_caching.py"
Task T008: "Add test for command-scoped cache cleanup in tests/integration/test_zotero_caching.py"

# Then implementation tasks (sequential within story for logical flow)
```

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task T018: "Add test for page map extraction with multi-page document"
Task T019: "Add test for heading tree extraction with document containing headings"
Task T020: "Add test for chunk creation producing multiple chunks from large document"
Task T021: "Add test for manual chunking fallback on Windows producing multiple chunks"

# Implementation tasks for page/heading extraction (can run in parallel):
Task T022: "Fix _extract_page_map() method in docling_converter.py"
Task T024: "Fix _extract_heading_tree() method in docling_converter.py"

# Chunking fixes (sequential after page/heading fixes):
Task T026: "Investigate and fix why only 1 chunk created"
Task T027: "Improve manual chunking fallback"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 - P1 Priority)

1. Complete Phase 1: Setup (verification)
2. Complete Phase 2: Foundational (T004, T005)
3. Complete Phase 3: User Story 1 (Fast Zotero Browsing)
4. Complete Phase 4: User Story 2 (Accurate Conversion/Chunking)
5. **STOP and VALIDATE**: Test both stories independently
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (P1) → Test independently → Deploy/Demo (MVP part 1)
3. Add User Story 2 (P1) → Test independently → Deploy/Demo (MVP part 2)
4. Add User Story 3 (P2) → Test independently → Deploy/Demo
5. Add User Story 4 (P2) → Test independently → Deploy/Demo
6. Add User Story 5 (P2) → Test independently → Deploy/Demo
7. Add User Stories 6 & 7 (P3) → Test independently → Deploy/Demo
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Zotero caching)
   - Developer B: User Story 2 (Docling fixes)
   - Developer C: Cross-platform timeout (Phase 10)
3. Next iteration:
   - Developer A: User Story 3 (Progress feedback)
   - Developer B: User Story 4 (Resource sharing)
   - Developer C: User Story 5 (Model binding)
4. Final iteration:
   - Developer A: User Story 6 (Logging)
   - Developer B: User Story 7 (Windows detection)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach for critical fixes)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Performance targets must be met: <10s for 10 items browsing, 15-40 chunks for 20+ page documents

---

## Task Summary

- **Total Tasks**: 74
- **Tasks by User Story**:
  - US1 (P1): 12 tasks (3 tests + 9 implementation)
  - US2 (P1): 13 tasks (4 tests + 9 implementation)
  - US3 (P2): 6 tasks (0 tests + 6 implementation)
  - US4 (P2): 7 tasks (2 tests + 5 implementation) - Added FR-017 tasks (T044a, T044b)
  - US5 (P2): 4 tasks (0 tests + 4 implementation)
  - US6 (P3): 4 tasks (0 tests + 4 implementation)
  - US7 (P3): 6 tasks (0 tests + 6 implementation)
  - Cross-platform timeout: 4 tasks
  - Additional fixes: 4 tasks
  - Polish: 8 tasks
  - Setup: 3 tasks
  - Foundational: 2 tasks

- **Parallel Opportunities**: 
  - All setup tasks (3)
  - Foundational tasks (2)
  - User story tests within each story
  - Different user stories can run in parallel after foundational
  - Additional fixes (4 tasks)

- **MVP Scope**: User Stories 1 & 2 (P1 priority) - Fast browsing and accurate conversion/chunking

- **Independent Test Criteria**:
  - US1: Browse 10 items in <10s with 50%+ API call reduction
  - US2: 20-page document produces 15-40 chunks with accurate page/heading extraction
  - US3: Progress indication visible within 5 seconds for operations >5 seconds
  - US4: Second command reuses converter, eliminating 2-3s overhead
  - US5: Query succeeds immediately after ingestion without manual binding
  - US6: HTTP logs only in verbose mode, important info visible at INFO
  - US7: Windows profile detection works or provides clear guidance

