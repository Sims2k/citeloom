# Tasks: Production-Ready Document Retrieval System

**Input**: Design documents from `/specs/003-framework-implementation/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency setup

- [X] T001 Create fastmcp.json configuration file in project root with dependencies, transport, and entrypoint
- [X] T002 Add python-dotenv dependency via `uv add python-dotenv` for .env file support
- [X] T003 [P] Update .gitignore to exclude .env files from version control
- [X] T004 [P] Verify existing project structure matches plan.md (src/domain, src/application, src/infrastructure)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Implement environment variable loading from .env file in src/infrastructure/config/environment.py
- [X] T006 [P] Update Settings class in src/infrastructure/config/settings.py to load environment variables with precedence (system env > .env)
- [X] T007 [P] Update CitationMeta domain model in src/domain/models/citation_meta.py to include language field (optional)
- [X] T008 [P] Update Chunk domain model in src/domain/models/chunk.py to include token_count and signal_to_noise_ratio fields (optional)
- [X] T009 [P] Update ConversionResult domain model in src/domain/models/conversion_result.py to include ocr_languages field (optional)
- [X] T010 Update ChunkingPolicy in src/domain/policy/chunking_policy.py to include min_chunk_length and min_signal_to_noise fields

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Reliable Document Conversion with Structure Preservation (Priority: P1) 🎯 MVP

**Goal**: Complete Docling v2 DocumentConverter implementation with OCR support, page mapping, heading tree extraction, and timeout handling. Documents are converted with accurate structure preservation for precise citations.

**Independent Test**: Can be fully tested by ingesting a scanned PDF and a complex multi-column technical document, verifying that both produce valid page maps (page number to text span), consistent heading hierarchies, and normalized text with proper handling of line breaks and whitespace.

### Implementation for User Story 1

- [X] T011 [US1] Implement DoclingConverterAdapter.convert() in src/infrastructure/adapters/docling_converter.py with Docling v2 DocumentConverter initialization
- [X] T012 [US1] Add OCR language selection logic in src/infrastructure/adapters/docling_converter.py (priority: Zotero metadata language → explicit config → default ['en', 'de'])
- [X] T013 [US1] Implement OCR configuration with Tesseract/RapidOCR in src/infrastructure/adapters/docling_converter.py for scanned documents
- [X] T014 [US1] Add timeout handling (120s document, 10s per-page) in src/infrastructure/adapters/docling_converter.py with diagnostic logging
- [X] T015 [US1] Implement page map extraction (page number → character span tuple) in src/infrastructure/adapters/docling_converter.py
- [X] T016 [US1] Implement heading tree extraction with page anchors in src/infrastructure/adapters/docling_converter.py
- [X] T017 [US1] Add text normalization (hyphen repair, whitespace normalization) preserving code/math blocks in src/infrastructure/adapters/docling_converter.py
- [X] T018 [US1] Add image-only page detection and logging in src/infrastructure/adapters/docling_converter.py
- [X] T019 [US1] Add Windows compatibility warnings (WSL/Docker guidance) in src/infrastructure/adapters/docling_converter.py
- [X] T020 [US1] Update TextConverterPort protocol in src/application/ports/text_converter.py to include ocr_languages parameter
- [X] T020a [US1] Add audit log writing infrastructure in src/infrastructure/adapters/qdrant_index.py or src/application/use_cases/ingest_document.py to write JSONL audit logs documenting added/updated/skipped counts, duration, document IDs, and embedding model (FR-018)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Heading-Aware Chunking with Tokenizer Alignment (Priority: P1)

**Goal**: Complete Docling HybridChunker implementation with tokenizer alignment, quality filtering, and deterministic chunk ID generation. Chunks maintain document structure and are properly sized for embedding models.

**Independent Test**: Can be fully tested by chunking multiple PDFs and verifying that chunks have section headings, section paths (breadcrumb), page spans, token counts that match the embedding model's tokenizer, and deterministic IDs that remain stable across re-ingestion.

### Implementation for User Story 2

- [X] T021 [US2] Implement DoclingHybridChunkerAdapter.chunk() in src/infrastructure/adapters/docling_chunker.py with HybridChunker initialization
- [X] T022 [US2] Add tokenizer alignment validation in src/infrastructure/adapters/docling_chunker.py (ensure chunking tokenizer matches embedding model tokenizer family)
- [X] T023 [US2] Implement heading-aware chunking with heading_context ancestor headings in src/infrastructure/adapters/docling_chunker.py
- [X] T024 [US2] Add quality filtering logic (minimum 50 tokens, signal-to-noise ratio ≥ 0.3) in src/infrastructure/adapters/docling_chunker.py
- [X] T025 [US2] Implement section path breadcrumb extraction from heading tree in src/infrastructure/adapters/docling_chunker.py
- [X] T026 [US2] Implement page span mapping from page_map in src/infrastructure/adapters/docling_chunker.py
- [X] T027 [US2] Add token count calculation using embedding model tokenizer in src/infrastructure/adapters/docling_chunker.py
- [X] T028 [US2] Ensure deterministic chunk ID generation using (doc_id, page_span/section_path, embedding_model_id, chunk_idx) in src/infrastructure/adapters/docling_chunker.py
- [X] T029 [US2] Update ChunkerPort protocol in src/application/ports/chunker.py to document quality filtering requirements
- [X] T029a [US2] Ensure audit logs capture chunk counts and quality filter statistics (filtered chunks count) in audit log writing (FR-018)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Project-Isolated Vector Storage with Model Consistency (Priority: P1)

**Goal**: Implement Qdrant collection creation with named vectors, model binding, write-guards, and payload indexes. Collections are isolated per project with enforced model consistency.

**Independent Test**: Can be fully tested by creating multiple projects with different embedding models, attempting to write chunks with mismatched models, and verifying that writes are blocked with clear errors, collections are properly isolated, and payload indexes exist for filtering.

### Implementation for User Story 3

- [X] T030 [US3] Implement QdrantIndexAdapter.ensure_collection() in src/infrastructure/adapters/qdrant_index.py to create collections with named vectors (dense and sparse)
- [X] T031 [US3] Add model binding via set_model() for dense embeddings in src/infrastructure/adapters/qdrant_index.py
- [X] T032 [US3] Add model binding via set_sparse_model() for sparse embeddings in src/infrastructure/adapters/qdrant_index.py (when hybrid enabled)
- [X] T033 [US3] Implement write-guard validation (check embed_model matches collection metadata) in src/infrastructure/adapters/qdrant_index.py
- [X] T034 [US3] Create keyword payload indexes on project_id, doc_id, citekey, year, tags in src/infrastructure/adapters/qdrant_index.py
- [X] T035 [US3] Store dense_model_id and sparse_model_id in collection metadata in src/infrastructure/adapters/qdrant_index.py
- [X] T036 [US3] Implement per-project collection naming (proj-{project_id}) in src/infrastructure/adapters/qdrant_index.py
- [X] T037 [US3] Add server-side project filtering enforcement in all search operations in src/infrastructure/adapters/qdrant_index.py
- [X] T038 [US3] Update VectorIndexPort protocol in src/application/ports/vector_index.py to include ensure_collection() method and sparse_model_id parameter
- [X] T039 [US3] Update payload schema to include project_id, doc_id, section_path, page_start, page_end, citekey, doi, year, authors, title, tags, source_path, chunk_text, heading_chain fields in src/infrastructure/adapters/qdrant_index.py
- [X] T039a [US3] Ensure audit logs capture collection writes (chunks_written count), model IDs (dense_model and sparse_model), and any errors encountered during upsert operations in audit log writing (FR-018)

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently

---

## Phase 6: User Story 4 - Hybrid Search with Query-Time Fusion (Priority: P2)

**Goal**: Implement hybrid search using Qdrant named vectors with RRF fusion. Queries combine semantic similarity with keyword matching for improved retrieval quality.

**Independent Test**: Can be fully tested by performing both dense-only and hybrid queries on a test document set, verifying that hybrid queries improve results for known lexical queries (exact terminology matches) while maintaining semantic search quality, and that results are properly scored and ranked.

### Implementation for User Story 4

- [X] T040 [US4] Implement full-text index creation on chunk_text payload field in src/infrastructure/adapters/qdrant_index.py (when hybrid enabled)
- [X] T041 [US4] Implement hybrid_query() method using named vectors with RRF fusion in src/infrastructure/adapters/qdrant_index.py
- [X] T042 [US4] Add text-based query support using model binding in src/infrastructure/adapters/qdrant_index.py (set_model enables text queries)
- [X] T043 [US4] Ensure both dense and sparse models are bound before allowing hybrid queries in src/infrastructure/adapters/qdrant_index.py
- [X] T044 [US4] Update VectorIndexPort.hybrid_query() protocol in src/application/ports/vector_index.py to document RRF fusion requirements
- [X] T045 [US4] Update QueryChunks use case in src/application/use_cases/query_chunks.py to support hybrid queries with named vectors

**Checkpoint**: At this point, User Stories 1-4 should all work independently

---

## Phase 7: User Story 5 - Predictable MCP Tools with Bounded Outputs (Priority: P2)

**Goal**: Implement FastMCP server with standardized tools, timeouts, bounded outputs, and error taxonomy. Tools are reliable and predictable for AI agent integration.

**Independent Test**: Can be fully tested by invoking MCP tools (ingest_from_source, query, query_hybrid, inspect_collection, list_projects) from an MCP client and verifying that they complete within timeout limits, return consistently formatted responses with trimmed content, enforce project filtering server-side, and provide clear error codes.

### Implementation for User Story 5

- [X] T046 [US5] Create FastMCP server setup in src/infrastructure/mcp/server.py with stdio transport
- [X] T047 [US5] Implement ingest_from_source tool in src/infrastructure/mcp/tools.py with 15s timeout and correlation ID support
- [X] T048 [US5] Implement query tool in src/infrastructure/mcp/tools.py with 8s timeout for dense-only search
- [X] T049 [US5] Implement query_hybrid tool in src/infrastructure/mcp/tools.py with 15s timeout for hybrid search
- [X] T050 [US5] Implement inspect_collection tool in src/infrastructure/mcp/tools.py with 5s timeout showing collection stats and model bindings
- [X] T051 [US5] Implement list_projects tool in src/infrastructure/mcp/tools.py (no timeout, fast enumeration)
- [X] T052 [US5] Add standardized error taxonomy (INVALID_PROJECT, EMBEDDING_MISMATCH, HYBRID_NOT_SUPPORTED, INDEX_UNAVAILABLE, TIMEOUT) in src/infrastructure/mcp/tools.py
- [X] T053 [US5] Add text trimming to max_chars_per_chunk (1,800 chars) in all query tool responses in src/infrastructure/mcp/tools.py
- [X] T054 [US5] Add correlation IDs to all MCP tool responses in src/infrastructure/mcp/tools.py
- [X] T055 [US5] Add server-side project filtering enforcement in all MCP query tools in src/infrastructure/mcp/tools.py
- [X] T056 [US5] Add per-tool timeout enforcement (8-15s depending on operation) in src/infrastructure/mcp/tools.py
- [X] T057 [US5] Update CLI to expose mcp-server command in src/infrastructure/cli/main.py

**Checkpoint**: At this point, User Stories 1-5 should all work independently

---

## Phase 8: User Story 6 - Robust Citation Metadata Resolution via pyzotero (Priority: P2)

**Goal**: Implement Zotero metadata resolution using pyzotero API with Better BibTeX citekey extraction and language field extraction for OCR. Metadata resolution is robust and handles missing data gracefully.

**Independent Test**: Can be fully tested by ingesting documents with corresponding Zotero library entries and verifying that at least 95% match successfully using DOI-first then title-based matching, that unresolved documents are logged but still ingested, and that metadata (citekey from Better BibTeX, tags, collections, language) is correctly stored in chunk payloads.

### Implementation for User Story 6

- [X] T068 [US6] Add pyzotero dependency via `uv add pyzotero` for Zotero API access
- [X] T069 [US6] Replace ZoteroCslJsonResolver with ZoteroPyzoteroResolver in src/infrastructure/adapters/zotero_metadata.py implementing pyzotero client initialization (library_id, library_type, api_key for remote, or local=True for local access)
- [X] T070 [US6] Implement Better BibTeX JSON-RPC client in src/infrastructure/adapters/zotero_metadata.py with port availability check (port 23119 for Zotero, 24119 for Juris-M) with timeout (5-10s), detecting if Better BibTeX is running before attempting item.citationkey method calls
- [X] T071 [US6] Add Better BibTeX citekey extraction fallback parsing item['data']['extra'] field for "Citation Key: citekey" pattern in src/infrastructure/adapters/zotero_metadata.py
- [X] T072 [US6] Implement pyzotero item search by DOI (exact match, normalized) then by title (normalized, fuzzy threshold ≥ 0.8) in src/infrastructure/adapters/zotero_metadata.py
- [X] T073 [US6] Extract metadata fields from pyzotero item response (title, creators → authors, year from date, DOI, URL, tags, collections, language) in src/infrastructure/adapters/zotero_metadata.py
- [X] T074 [US6] Add language field mapping (Zotero codes → OCR language codes, e.g., 'en-US' → 'en') in src/infrastructure/adapters/zotero_metadata.py
- [X] T075 [US6] Pass language from metadata to converter for OCR language selection in src/application/use_cases/ingest_document.py
- [X] T076 [US6] Update MetadataResolverPort protocol in src/application/ports/metadata_resolver.py to replace references_path parameter with zotero_config (optional dict) and document pyzotero usage
- [X] T077 [US6] Add graceful error handling for pyzotero API connection failures and Better BibTeX JSON-RPC unavailability in src/infrastructure/adapters/zotero_metadata.py (non-blocking, returns None, logs MetadataMissing)

**Checkpoint**: At this point, User Stories 1-6 should all work independently

---

## Phase 9: User Story 7 - System Validation and Operational Inspection (Priority: P3)

**Goal**: Implement validate and inspect CLI commands for configuration validation and collection inspection. System provides operational visibility and catches errors before data corruption.

**Independent Test**: Can be fully tested by running validate and inspect commands on a configured project and verifying that validation checks tokenizer-to-embedding alignment, vector database connectivity, collection presence, model lock verification, payload indexes, and Zotero library connectivity (pyzotero API connection), while inspect shows collection statistics and sample data.

### Implementation for User Story 7

- [X] T062 [US7] Implement validate command in src/infrastructure/cli/commands/validate.py checking tokenizer-to-embedding alignment
- [X] T063 [US7] Add vector database connectivity check in src/infrastructure/cli/commands/validate.py
- [X] T064 [US7] Add collection presence and model lock verification in src/infrastructure/cli/commands/validate.py
- [X] T065 [US7] Add payload index verification in src/infrastructure/cli/commands/validate.py
- [X] T067 [US7] Add Zotero library connectivity check (pyzotero API connection test) in src/infrastructure/cli/commands/validate.py
- [X] T068a [US7] Add clear error messages with actionable guidance in src/infrastructure/cli/commands/validate.py
- [X] T069 [US7] Implement inspect command in src/infrastructure/cli/commands/inspect.py displaying collection statistics
- [X] T070 [US7] Add embedding model identifier display in src/infrastructure/cli/commands/inspect.py
- [X] T071 [US7] Add payload schema sample display in src/infrastructure/cli/commands/inspect.py
- [X] T072 [US7] Add index presence confirmation in src/infrastructure/cli/commands/inspect.py
- [X] T073 [US7] Add optional sample chunk data display in src/infrastructure/cli/commands/inspect.py
- [X] T074 [US7] Register validate and inspect commands in src/infrastructure/cli/main.py

**Checkpoint**: At this point, User Stories 1-7 should all work independently

---

## Phase 10: User Story 8 - Environment-Based Configuration for API Keys (Priority: P3)

**Goal**: Complete environment variable loading system with precedence rules and graceful handling of optional/required keys. API keys are managed securely via .env files.

**Independent Test**: Can be fully tested by creating a `.env` file with API keys, running system operations that require those keys, and verifying that keys are loaded correctly and operations work. For optional keys, verify that the system degrades gracefully when keys are missing.

### Implementation for User Story 8

- [X] T090 [US8] Add python-dotenv loading in src/infrastructure/config/environment.py with automatic .env file detection
- [X] T091 [US8] Implement precedence logic (system env > .env file values) in src/infrastructure/config/environment.py
- [X] T092 [US8] Add graceful handling of missing optional API keys (OPENAI_API_KEY, Better BibTeX JSON-RPC when unavailable) in src/infrastructure/config/environment.py with fallback to defaults
- [X] T093 [US8] Add clear error messages for missing required API keys (QDRANT_API_KEY when auth required, ZOTERO_LIBRARY_ID/ZOTERO_API_KEY for remote access) in src/infrastructure/config/environment.py
- [X] T094 [US8] Add Zotero configuration support (ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY, ZOTERO_LOCAL) in src/infrastructure/config/environment.py
- [X] T095 [US8] Update Settings class to use environment-loaded values including Zotero config in src/infrastructure/config/settings.py
- [X] T096 [US8] Verify .env file is in .gitignore and document Zotero configuration in README

**Checkpoint**: At this point, all User Stories 1-8 should be complete

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T097 [P] Add comprehensive integration tests for Docling conversion in tests/integration/test_docling_conversion.py
- [ ] T098 [P] Add comprehensive integration tests for Qdrant named vectors and model binding in tests/integration/test_qdrant_named_vectors.py
- [ ] T099 [P] Add comprehensive integration tests for FastMCP tools in tests/integration/test_fastmcp_tools.py
- [ ] T100 [P] Add integration tests for pyzotero metadata resolution and Better BibTeX citekey extraction in tests/integration/test_zotero_metadata.py
- [ ] T101 [P] Add unit tests for environment variable loading in tests/unit/test_environment_loader.py
- [ ] T102 [P] Enhance audit logging to include dense_model and sparse_model IDs in existing audit log implementation (complements T020a, T029a, T039a)
- [ ] T103 Add diagnostic logging improvements for timeout/page failures in src/infrastructure/adapters/docling_converter.py
- [ ] T104 [P] Update documentation with FastMCP configuration examples in docs/
- [ ] T105 [P] Update documentation with environment variable configuration guide including Zotero setup in docs/
- [ ] T106 Code cleanup and refactoring across all adapters
- [ ] T107 Run quickstart.md validation scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 11)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Depends on US1 for ConversionResult
- **User Story 3 (P1)**: Can start after Foundational (Phase 2) - Depends on US2 for Chunk model
- **User Story 4 (P2)**: Can start after US3 completion - Depends on US3 for collections
- **User Story 5 (P2)**: Can start after US3 and US4 completion - Depends on query capabilities
- **User Story 6 (P2)**: Can start after US1 completion - Depends on converter for language passing
- **User Story 7 (P3)**: Can start after US3 completion - Depends on collections
- **User Story 8 (P3)**: Can start after Foundational (Phase 2) - Independent but low priority

### Within Each User Story

- Domain model updates before adapter implementations
- Adapter implementations before use case updates
- Use case updates before CLI/MCP tools
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003, T004)
- All Foundational tasks marked [P] can run in parallel (T006, T007, T008, T009)
- Once Foundational phase completes:
  - US1, US2 can partially overlap (T011-T020 can run while T021-T029 in progress)
  - US6 can start once US1 is done
  - US8 can start anytime after Foundational
- All Polish tasks marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members after dependencies are met

---

## Parallel Example: User Story 1

```bash
# Parallel domain model updates (if any):
Task: "Update ConversionResult domain model in src/domain/models/conversion_result.py to include ocr_languages field"

# Parallel adapter implementation preparation:
Task: "Implement DoclingConverterAdapter.convert() in src/infrastructure/adapters/docling_converter.py"
Task: "Add OCR language selection logic in src/infrastructure/adapters/docling_converter.py"
Task: "Implement OCR configuration with Tesseract/RapidOCR in src/infrastructure/adapters/docling_converter.py"
```

---

## Parallel Example: User Story 3

```bash
# Parallel collection setup tasks:
Task: "Implement QdrantIndexAdapter.ensure_collection() in src/infrastructure/adapters/qdrant_index.py"
Task: "Add model binding via set_model() for dense embeddings in src/infrastructure/adapters/qdrant_index.py"
Task: "Add model binding via set_sparse_model() for sparse embeddings in src/infrastructure/adapters/qdrant_index.py"
Task: "Create keyword payload indexes on project_id, doc_id, citekey, year, tags in src/infrastructure/adapters/qdrant_index.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1, 2, 3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Document Conversion)
4. Complete Phase 4: User Story 2 (Chunking)
5. Complete Phase 5: User Story 3 (Vector Storage)
6. **STOP and VALIDATE**: Test all three stories independently
7. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Document conversion working
3. Add User Story 2 → Test independently → Chunking working
4. Add User Story 3 → Test independently → Storage working (MVP!)
5. Add User Story 4 → Test independently → Hybrid search working
6. Add User Story 5 → Test independently → MCP tools working
7. Add User Story 6 → Test independently → Metadata resolution enhanced
8. Add User Story 7 → Test independently → Validation/inspection working
9. Add User Story 8 → Test independently → Environment config complete
10. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Document Conversion)
   - Developer B: Prepare User Story 2 (while waiting for US1)
3. Once US1 complete:
   - Developer A: User Story 2 (Chunking)
   - Developer B: User Story 3 (Vector Storage)
   - Developer C: User Story 6 (Metadata - depends on US1)
4. Once US2 and US3 complete:
   - Developer A: User Story 4 (Hybrid Search)
   - Developer B: User Story 5 (MCP Tools)
   - Developer C: User Story 7 (Validation)
5. Developer D: User Story 8 (Environment Config - can start anytime)
6. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- Tests are NOT included in this task list (implementation focus)
- All tasks follow strict checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

---

## Summary

- **Total Tasks**: 107 tasks across 11 phases
- **Task Count by Phase**:
  - Phase 1 (Setup): 4 tasks
  - Phase 2 (Foundational): 6 tasks
  - Phase 3 (US1 - Document Conversion): 11 tasks (includes T020a audit logging)
  - Phase 4 (US2 - Chunking): 10 tasks (includes T029a audit logging)
  - Phase 5 (US3 - Vector Storage): 11 tasks (includes T039a audit logging)
  - Phase 6 (US4 - Hybrid Search): 6 tasks
  - Phase 7 (US5 - MCP Tools): 12 tasks
  - Phase 8 (US6 - Metadata Resolution via pyzotero): 10 tasks
  - Phase 9 (US7 - Validation/Inspection): 12 tasks
  - Phase 10 (US8 - Environment Config): 7 tasks
  - Phase 11 (Polish): 11 tasks

- **Parallel Opportunities**: 28 tasks marked [P] for parallel execution
- **MVP Scope**: User Stories 1, 2, 3 (P1 stories) = 29 tasks
- **Independent Test Criteria**: Each user story has clear independent test criteria documented in spec.md
- **Format Validation**: ✓ All tasks follow strict checklist format with checkbox, ID, optional [P] marker, optional [Story] label, and file paths

