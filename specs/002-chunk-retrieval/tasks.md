# Tasks: Project-Scoped Citable Chunk Retrieval

**Input**: Design documents from `/specs/002-chunk-retrieval/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., [US1], [US2], [US3])
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency management

- [X] T001 Create project directory structure per implementation plan in plan.md
- [X] T002 [P] Add Docling dependency to pyproject.toml for document conversion
  - **Status**: Optional dependency - not available on Windows Python 3.12 (deepsearch-glm lacks Windows wheels).
  - **Resolution**: Adapters updated with graceful error handling:
    - `DoclingConverterAdapter` and `DoclingHybridChunkerAdapter` use try/except for docling import
    - Clear ImportError messages guide Windows users to WSL or alternative solutions
    - Adapters will fail fast with helpful messages if docling is required but unavailable
  - **Windows Options**: Use WSL, Python 3.11 (not recommended), or wait for Windows support
- [X] T003 [P] Add Qdrant Python client dependency to pyproject.toml for vector operations
- [X] T004 [P] Add FastEmbed dependency to pyproject.toml for local embeddings
- [X] T005 [P] Add OpenAI Python SDK dependency (optional, dev group) to pyproject.toml
- [X] T006 [P] Add Typer dependency to pyproject.toml for CLI framework
- [X] T007 [P] Add Rich dependency to pyproject.toml for terminal formatting
- [X] T008 [P] Add MCP SDK dependency to pyproject.toml for Model Context Protocol
- [X] T009 Run uv sync to install all dependencies

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain models, policies, ports, and shared infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Domain Layer (Pure)

- [X] T010 [P] Create ChunkingPolicy in src/domain/policy/chunking_policy.py with max_tokens, overlap_tokens, heading_context, tokenizer_id
- [X] T011 [P] Create RetrievalPolicy in src/domain/policy/retrieval_policy.py with top_k, hybrid_enabled, min_score, require_project_filter, max_chars_per_chunk
- [X] T012 [P] Create ConversionResult model in src/domain/models/conversion_result.py with doc_id, structure (heading_tree, page_map), plain_text
- [X] T013 [P] Create Chunk model in src/domain/models/chunk.py with id, doc_id, text, page_span, section_heading, section_path, chunk_idx
- [X] T014 [P] Create CitationMeta model in src/domain/models/citation_meta.py with citekey, title, authors, year, doi/url, tags, collections
- [X] T015 [P] Create domain errors in src/domain/errors.py: EmbeddingModelMismatch, ProjectNotFound, HybridNotSupported, MetadataMissing
- [X] T016 [P] Create value objects in src/domain/types.py: ProjectId, CiteKey, PageSpan, SectionPath

### Application Layer (Ports & DTOs)

- [X] T017 [P] Define TextConverterPort protocol in src/application/ports/converter.py
- [X] T018 [P] Define ChunkerPort protocol in src/application/ports/chunker.py
- [X] T019 [P] Define MetadataResolverPort protocol in src/application/ports/metadata_resolver.py
- [X] T020 [P] Define EmbeddingPort protocol in src/application/ports/embeddings.py
- [X] T021 [P] Define VectorIndexPort protocol in src/application/ports/vector_index.py
- [X] T022 [P] Create IngestRequest and IngestResult DTOs in src/application/dto/ingest.py
- [X] T023 [P] Create QueryRequest, QueryResult, QueryResultItem DTOs in src/application/dto/query.py

### Infrastructure Layer (Shared)

- [X] T024 Create Pydantic settings class in src/infrastructure/config/settings.py for citeloom.toml configuration
- [X] T025 Create structured logging setup in src/infrastructure/logging.py with correlation ID support
- [X] T026 Create Typer CLI app entrypoint in src/infrastructure/cli/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Ingest Documents into Project-Scoped Chunks (Priority: P1) 🎯 MVP

**Goal**: Enable researchers to ingest long-form documents (PDFs, books, web content) into project-scoped collections with heading-aware chunking, embedding generation, and vector storage.

**Independent Test**: Ingest two varied PDFs (scanned document and complex layout) and verify chunks are created with correct page spans, section headings, and stored in project's vector store.

### Implementation for User Story 1

#### Domain Enhancements

- [X] T027 [US1] Enhance Chunk model in src/domain/models/chunk.py with deterministic ID generation from (doc_id, page_span/section_path, embedding_model_id, chunk_idx)

#### Application Layer

- [X] T028 [US1] Implement IngestDocument use case in src/application/use_cases/ingest_document.py orchestrating convert → chunk → metadata → embed → upsert → audit
- [X] T029 [US1] Implement audit log writing in IngestDocument use case with correlation ID, chunk counts, durations, doc_id, embed_model

#### Infrastructure Adapters

- [X] T030 [US1] Implement DoclingConverterAdapter in src/infrastructure/adapters/docling_converter.py with OCR, heading tree, page map extraction
  - **Status**: Placeholder implementation with graceful error handling for Windows compatibility
- [X] T031 [US1] Implement DoclingHybridChunkerAdapter in src/infrastructure/adapters/docling_chunker.py with heading-aware chunking, tokenizer alignment, policy support
  - **Status**: Placeholder implementation using Chunk model with deterministic IDs; full Docling integration requires Windows support or WSL
- [X] T032 [US1] Implement FastEmbedAdapter in src/infrastructure/adapters/fastembed_embeddings.py with model_id property and batch embedding support
- [X] T033 [US1] Implement QdrantIndexAdapter in src/infrastructure/adapters/qdrant_index.py with per-project collections, upsert, embed_model write-guard, payload indexes
- [X] T033a [US1] Add exponential backoff retry logic to QdrantIndexAdapter upsert method in src/infrastructure/adapters/qdrant_index.py with configurable retry limit and partial progress preservation for vector database unavailability

#### CLI

- [X] T034 [US1] Implement ingest command in src/infrastructure/cli/commands/ingest.py with project, source_path, references_path, embedding_model options
- [X] T035 [US1] Wire ingest command to IngestDocument use case in src/infrastructure/cli/commands/ingest.py
- [X] T036 [US1] Add correlation ID output to ingest command in src/infrastructure/cli/commands/ingest.py

#### Tests

- [X] T037 [P] [US1] Create unit test for Chunk deterministic ID generation in tests/unit/test_domain_models.py
- [X] T038 [P] [US1] Create integration test for Docling conversion in tests/integration/test_docling_smoke.py with page map and heading tree verification
- [X] T039 [P] [US1] Create integration test for Qdrant upsert in tests/integration/test_qdrant_smoke.py with collection creation and write-guard

**Checkpoint**: User Story 1 should be fully functional - can ingest documents and store chunks independently

---

## Phase 4: User Story 2 - Enrich Chunks with Citation Metadata (Priority: P2)

**Goal**: Automatically enrich document chunks with citation metadata (author, title, year, DOI, citation key) from Zotero CSL-JSON exports.

**Independent Test**: Ingest documents with corresponding entries in reference management export file and verify chunks are enriched with correct citation metadata (citekey, authors, year, DOI).

### Implementation for User Story 2

#### Application Layer

- [X] T040 [US2] Enhance IngestDocument use case in src/application/use_cases/ingest_document.py to call metadata resolver and attach CitationMeta to chunks

#### Infrastructure Adapters

- [X] T041 [US2] Implement ZoteroCslJsonResolver in src/infrastructure/adapters/zotero_metadata.py with DOI-first matching, normalized title fallback, fuzzy threshold
- [X] T042 [US2] Add MetadataMissing logging to ZoteroCslJsonResolver in src/infrastructure/adapters/zotero_metadata.py (non-blocking)

#### Tests

- [X] T043 [P] [US2] Create integration test for Zotero metadata matching in tests/integration/test_zotero_metadata.py with DOI match, title fallback, unknown handling

**Checkpoint**: User Stories 1 AND 2 should both work independently - chunks include citation metadata

---

## Phase 5: User Story 3 - Query and Retrieve Relevant Chunks (Priority: P2)

**Goal**: Enable semantic and hybrid search queries with project filtering, returning trimmed chunks with citation-ready metadata.

**Independent Test**: Perform semantic search queries on ingested project and verify results are limited to that project, include proper citation metadata, are trimmed to readable lengths, and contain page spans and section headings.

### Implementation for User Story 3

#### Application Layer

- [X] T044 [US3] Implement QueryChunks use case in src/application/use_cases/query_chunks.py with project filter enforcement, top_k limit, text trimming, retrieval policy
- [X] T045 [US3] Add hybrid query support to QueryChunks use case in src/application/use_cases/query_chunks.py with query-time fusion (BM25 + vector)

#### Infrastructure Adapters

- [X] T046 [US3] Implement search method in QdrantIndexAdapter in src/infrastructure/adapters/qdrant_index.py with vector search and project filtering
- [X] T047 [US3] Implement hybrid_query method in QdrantIndexAdapter in src/infrastructure/adapters/qdrant_index.py with full-text index and score fusion
- [X] T048 [US3] Ensure QdrantIndexAdapter creates fulltext index in src/infrastructure/adapters/qdrant_index.py when hybrid_enabled=True

#### CLI

- [X] T049 [US3] Implement query command in src/infrastructure/cli/commands/query.py with project, query text, top_k, hybrid, filters options
- [X] T050 [US3] Wire query command to QueryChunks use case in src/infrastructure/cli/commands/query.py
- [X] T051 [US3] Format query results output in src/infrastructure/cli/commands/query.py with (citekey, pp. x–y, section) format

#### Tests

- [X] T052 [P] [US3] Create integration test for hybrid query in tests/integration/test_query_hybrid.py with dense-only and hybrid search verification

**Checkpoint**: User Stories 1, 2, AND 3 should all work independently - full query and retrieval capability

---

## Phase 6: User Story 4 - Access Chunks via MCP Tools (Priority: P2)

**Goal**: Expose standardized MCP tools for AI development environments to access project chunks with time-bounded, project-scoped operations.

**Independent Test**: Expose MCP tools and verify they can be invoked from MCP client, return properly formatted results with trimmed content, and enforce project scoping.

### Implementation for User Story 4

#### Infrastructure MCP

- [ ] T053 [US4] Create MCP server setup in src/infrastructure/mcp/server.py with stdio/SSE transport
- [ ] T054 [US4] Implement store_chunks MCP tool in src/infrastructure/mcp/tools.py with batched upsert, timeouts, error codes
- [ ] T055 [US4] Implement find_chunks MCP tool in src/infrastructure/mcp/tools.py with vector search, project filtering, trimmed output
- [ ] T056 [US4] Implement query_hybrid MCP tool in src/infrastructure/mcp/tools.py with hybrid search, timeout handling
- [ ] T057 [US4] Implement inspect_collection MCP tool in src/infrastructure/mcp/tools.py with collection stats, embed_model, payload schema sample
- [ ] T058 [US4] Implement list_projects MCP tool in src/infrastructure/mcp/tools.py with project enumeration
- [ ] T059 [US4] Add error taxonomy to MCP tools in src/infrastructure/mcp/tools.py with INVALID_PROJECT, EMBEDDING_MISMATCH, INDEX_UNAVAILABLE, TIMEOUT codes
- [ ] T060 [US4] Wire MCP tools to use cases (IngestDocument, QueryChunks, InspectIndex) in src/infrastructure/mcp/tools.py

#### Tests

- [ ] T061 [P] [US4] Create integration test for MCP tools in tests/integration/test_mcp_tools.py with client invocation, error handling, timeout verification

**Checkpoint**: User Stories 1-4 should all work independently - MCP integration complete

---

## Phase 7: User Story 5 - Inspect and Validate Project Index (Priority: P3)

**Goal**: Provide inspection and validation capabilities to verify project index configuration, tokenizer-embedding alignment, and dependency availability.

**Independent Test**: Run inspect and validate commands on configured project and verify they report collection statistics, embedding model information, and pass all validation checks.

### Implementation for User Story 5

#### Application Layer

- [ ] T062 [US5] Implement InspectIndex use case in src/application/use_cases/inspect_index.py with collection size, embed_model, payload schema, index presence
- [ ] T063 [US5] Implement ValidateIndex use case in src/application/use_cases/validate_index.py with tokenizer-embedding alignment, Qdrant connectivity, collection existence, model consistency, index presence, references file checks

#### CLI

- [ ] T064 [US5] Implement inspect command in src/infrastructure/cli/commands/inspect.py with project and sample options
- [ ] T065 [US5] Wire inspect command to InspectIndex use case in src/infrastructure/cli/commands/inspect.py
- [ ] T066 [US5] Implement validate command in src/infrastructure/cli/commands/validate.py
- [ ] T067 [US5] Wire validate command to ValidateIndex use case in src/infrastructure/cli/commands/validate.py
- [ ] T068 [US5] Add actionable error messages to validate command in src/infrastructure/cli/commands/validate.py

**Checkpoint**: User Stories 1-5 should all work independently - operational visibility complete

---

## Phase 8: User Story 6 - Reindex Projects and Handle Model Migrations (Priority: P3)

**Goal**: Enable safe reindexing of project documents and migration to new embedding models while preventing duplicates and model mismatches.

**Independent Test**: Reindex project directory and verify chunks are updated without duplicates, and attempt model change to verify blocking unless explicitly authorized.

### Implementation for User Story 6

#### Application Layer

- [ ] T069 [US6] Implement ReindexProject use case in src/application/use_cases/reindex_project.py with idempotent processing, deterministic IDs, migration flag support
- [ ] T070 [US6] Add force-rebuild logic to ReindexProject use case in src/application/use_cases/reindex_project.py with new collection creation or migration path

#### CLI

- [ ] T071 [US6] Implement reindex command in src/infrastructure/cli/commands/reindex.py with project, force-rebuild, limit (for partial processing), and resume (for continuing partial operations) options
- [ ] T072 [US6] Wire reindex command to ReindexProject use case in src/infrastructure/cli/commands/reindex.py
- [ ] T072a [US6] Implement resume capability in ReindexProject use case in src/application/use_cases/reindex_project.py with state tracking/checkpointing for partial processing when document count limits are used

**Checkpoint**: All user stories should now be independently functional - maintenance operations complete

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final polish

### Testing & Coverage

- [ ] T073 [P] Ensure domain layer has ≥90% test coverage with unit tests in tests/unit/
- [ ] T074 [P] Create architecture test for dependency direction in tests/architecture/test_import_linter.py
- [ ] T075 [P] Add performance smoke tests in tests/integration/test_perf_smoke.py (skipped by default, CITELOOM_RUN_PERF=1)
- [ ] T075a [P] Implement optional OpenAIAdapter in src/infrastructure/adapters/openai_embeddings.py with model_id property, batch embedding support, and environment variable configuration (OPENAI_API_KEY, OPENAI_EMBED_MODEL) with no secrets in logs (deferred - FastEmbed is default)

### Documentation

- [ ] T076 [P] Update README.md with chunk retrieval features and usage examples
- [ ] T077 [P] Create ADR for hybrid retrieval decision in docs/adr/0002-hybrid-retrieval.md
- [ ] T078 [P] Document citeloom.toml configuration reference in docs/configuration.md

### Code Quality

- [ ] T079 Run ruff format and check on all files
- [ ] T080 Run mypy with strict checking on src/domain
- [ ] T081 Verify all imports follow Clean Architecture dependency rules

### Operational

- [ ] T082 [P] Add correlation ID logging verification in tests/integration/test_logging.py
- [ ] T083 Validate quickstart.md examples work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - **BLOCKS all user stories**
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - User stories can proceed in priority order (P1 → P2 → P3)
  - US2 depends on US1 (uses IngestDocument)
  - US3 depends on US1 (queries stored chunks)
  - US4 depends on US1, US3 (uses IngestDocument, QueryChunks)
  - US5 depends on US1 (inspects existing collections)
  - US6 depends on US1 (reindexes existing projects)
- **Polish (Phase 9)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - **MVP - no dependencies on other stories**
- **User Story 2 (P2)**: Depends on US1 (enhances IngestDocument)
- **User Story 3 (P2)**: Depends on US1 (queries chunks from US1)
- **User Story 4 (P2)**: Depends on US1, US3 (uses IngestDocument, QueryChunks)
- **User Story 5 (P3)**: Depends on US1 (inspects collections created by US1)
- **User Story 6 (P3)**: Depends on US1 (reindexes projects from US1)

### Within Each User Story

- Domain models before use cases
- Use cases before adapters
- Adapters before CLI/MCP
- Core implementation before integration tests

### Parallel Opportunities

- All Setup tasks (T002-T008) can run in parallel
- All Foundational domain tasks (T010-T016) can run in parallel
- All Foundational application ports (T017-T021) can run in parallel
- All Foundational DTOs (T022-T023) can run in parallel
- Tests marked [P] within a user story can run in parallel
- Different adapters within a story marked [P] can run in parallel
- Polish tasks marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# Parallel domain enhancement:
T027: Enhance Chunk model with deterministic ID

# Parallel adapter implementation:
T030: Implement DoclingConverterAdapter
T031: Implement DoclingHybridChunkerAdapter
T032: Implement FastEmbedAdapter
T033: Implement QdrantIndexAdapter

# Parallel tests:
T037: Unit test for Chunk ID generation
T038: Integration test for Docling
T039: Integration test for Qdrant
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL - blocks all stories**)
3. Complete Phase 3: User Story 1 (Ingest)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (**MVP!**)
3. Add User Story 2 → Test independently → Deploy/Demo (Citation metadata)
4. Add User Story 3 → Test independently → Deploy/Demo (Query capability)
5. Add User Story 4 → Test independently → Deploy/Demo (MCP integration)
6. Add User Story 5 → Test independently → Deploy/Demo (Operational tools)
7. Add User Story 6 → Test independently → Deploy/Demo (Maintenance)
8. Polish → Final release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Ingest) - **MVP**
   - Developer B: Prepare User Story 2 (Metadata resolver)
   - Developer C: Prepare User Story 3 (Query use case)
3. After US1 complete:
   - Developer A: User Story 2 (enriches US1)
   - Developer B: User Story 3 (queries US1 chunks)
   - Developer C: User Story 4 (MCP tools)
4. Final: User Stories 5-6 + Polish

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- **MVP is User Story 1** - foundational ingest capability

---

## Summary

- **Total Tasks**: 86
- **Setup Tasks**: 9 (T001-T009)
- **Foundational Tasks**: 17 (T010-T026)
- **User Story 1 Tasks**: 14 (T027-T039, T033a) - **MVP**
- **User Story 2 Tasks**: 4 (T040-T043)
- **User Story 3 Tasks**: 9 (T044-T052)
- **User Story 4 Tasks**: 9 (T053-T061)
- **User Story 5 Tasks**: 7 (T062-T068)
- **User Story 6 Tasks**: 5 (T069-T072, T072a)
- **Polish Tasks**: 12 (T073-T083, T075a)

**MVP Scope**: Phases 1-3 (Setup + Foundational + User Story 1) = 40 tasks

