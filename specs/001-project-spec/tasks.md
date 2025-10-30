---

description: "Task list template for feature implementation"
---

# Tasks: CiteLoom naming and positioning

**Input**: Design documents from `/specs/001-project-spec/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md, contracts/

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Ensure Python 3.12.x pinned in `.python-version` at repo root
- [x] T002 Initialize uv env/lock (creates `.venv/` and `uv.lock`)
- [x] T003 [P] Add dev dependencies via uv (pytest, ruff, mypy, pytest-cov)
- [x] T004 [P] Add runtime deps via uv (typer, rich, qdrant-client, sentence-transformers, fastembed, pydantic)
- [x] T005 Configure Ruff and mypy in `pyproject.toml` (ruff check+format; mypy strict in `src/domain`)
- [x] T006 Create `.editorconfig` and `.gitignore` (ignore `.venv/`, `var/`, `.pytest_cache/`)
- [x] T007 Create source tree and packages with `__init__.py` under `src/` per plan
- [x] T008 Create `README.md` sections placeholders (Intro, Quickstart, CLI, Config)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core gates and governance compliance

- [x] T009 Create GitHub Actions CI with ruff/mypy/pytest in `.github/workflows/ci.yml` (domain coverage gate ≥90%)
- [x] T010 Add grep guard for forbidden `pip install` in CI script
- [x] T011 Ensure `.python-version` and `uv.lock` committed; verify `.gitignore` covers `.venv/`
- [x] T012 Create `docs/adr/0001-toolchain-standard.md` (pyenv+uv+Ruff)
- [x] T013 Create `citeloom.toml` sample at repo root with project `citeloom/clean-arch` and defaults
- [x] T014 Create sample directories: `assets/raw/`, `references/`, `var/audit/`
- [x] T015 Add sample CSL-JSON file `references/clean-arch.json` (stub minimal valid JSON)
- [x] T016 Add `docker-compose.yml` for local Qdrant (port 6333)
- [x] T017 [P] Create domain policy skeletons: `src/domain/policy/chunking_policy.py`, `src/domain/policy/retrieval_policy.py`
- [x] T018 [P] Create domain types: `src/domain/types.py` (value objects as needed)
- [x] T019 Create application port interfaces: 
  - `src/application/ports/converter.py`
  - `src/application/ports/chunker.py`
  - `src/application/ports/metadata_resolver.py`
  - `src/application/ports/embeddings.py`
  - `src/application/ports/vector_index.py`
- [x] T020 Create application DTOs: `src/application/dto/ingest.py`, `src/application/dto/query.py`
- [x] T021 Create application use cases (stubs):
  - `src/application/use_cases/ingest_document.py`
  - `src/application/use_cases/query_chunks.py`
- [x] T022 Implement CLI scaffold with Typer: `src/infrastructure/cli/main.py` and `src/infrastructure/cli/commands/{ingest.py,query.py,inspect.py,validate.py}` (stubs print help)
- [x] T023 Implement logging setup: `src/infrastructure/logging.py` (structured logs)
- [x] T024 Architecture tests: configure `import-linter` or `pytest-archon` rules in `tests/architecture/`
- [x] T025 Create minimal unit test scaffolding in `tests/unit/` for policies and DTOs

- [x] T052 Add CI mypy strict domain check step (assert `src/domain` uses strict in mypy config)
- [x] T053 Add CI architecture check step (run import-linter/pytest-archon to enforce inward deps)

**Checkpoint**: Foundation ready - user story implementation can begin in parallel

---

## Phase 3: User Story 1 - Choose and publish project name and tagline (Priority: P1) 🎯 MVP

**Goal**: Expose name "CiteLoom" and finalized tagline prominently
**Independent Test**: README shows name + tagline in first screenful and matches spec and constitution

### Implementation for User Story 1

- [x] T026 [P] [US1] Update README title and tagline in `README.md`
- [x] T027 [US1] Add positioning bullets to `README.md` below tagline (sources, chunking, citations, projects, tools, architecture, flow)
- [x] T028 [P] [US1] Mirror tagline in constitution header block in `.specify/memory/constitution.md` (if header present)
- [x] T029 [US1] Verify consistency across README and constitution (exact tagline match)

**Checkpoint**: US1 independently testable and complete

---

## Phase 4: User Story 2 - Provide high-level description for prospective users (Priority: P2)

**Goal**: Short, clear description of purpose and workflow in README
**Independent Test**: README includes 4–8 bullet overview conveying the value and flow

### Implementation for User Story 2

- [x] T030 [P] [US2] Insert high-level description paragraph in `README.md`
- [x] T031 [P] [US2] Add 4–8 bullet overview to `README.md` (from spec Appendix)
- [x] T032 [US2] Validate language is non-technical and ≤120 chars for tagline context where applicable

**Checkpoint**: US2 independently testable and complete

---

## Phase 5: User Story 3 - Alternate names recorded for future branding (Priority: P3)

**Goal**: Preserve vetted alternatives for future branding decisions
**Independent Test**: Alternatives are documented without affecting current name/tagline

### Implementation for User Story 3

- [x] T033 [P] [US3] Add "Naming alternatives" subsection to `specs/001-project-spec/spec.md` (Appendix already present) and ensure completeness
- [x] T034 [US3] Create `docs/branding/naming-alternatives.md` with list and slugs
- [x] T035 [P] [US3] Link alternatives from `README.md` (optional, single link)

**Checkpoint**: US3 independently testable and complete

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T036 [P] Add badges to `README.md` (Python 3.12, uv, Ruff, CI)
- [x] T037 Ensure Quickstart in `specs/001-project-spec/quickstart.md` aligns with README
- [x] T038 Run formatting and type checks; fix any issues reported by ruff/mypy

---

## Phase F: MVP Ingest/Query Implementation (Foundational extension)

**Purpose**: Deliver working CLI ingest and query with stubbed-but-functional adapters

- [ ] T039 Implement `DoclingConverterAdapter` in `src/infrastructure/adapters/docling_converter.py` (parse PDF → structure/text)
- [ ] T040 Implement `DoclingHybridChunkerAdapter` in `src/infrastructure/adapters/docling_chunker.py` (heading-aware chunks)
- [ ] T041 Implement `ZoteroCslJsonResolver` in `src/infrastructure/adapters/zotero_metadata.py` (read CSL-JSON → CitationMeta)
- [ ] T042 Implement `FastEmbedAdapter` in `src/infrastructure/adapters/fastembed_embeddings.py` (batch embed)
- [ ] T043 Implement `QdrantIndexAdapter` in `src/infrastructure/adapters/qdrant_index.py` (upsert/search with project filter)
- [ ] T044 Wire `ingest_document` use case in `src/application/use_cases/ingest_document.py` (converter→chunker→resolver→embed→index)
- [ ] T045 Wire `query_chunks` use case in `src/application/use_cases/query_chunks.py` (hybrid flag respected; top_k applied)
- [ ] T046 Implement CLI `ingest` in `src/infrastructure/cli/commands/ingest.py` (read config; log audit file)
- [ ] T047 Implement CLI `query` in `src/infrastructure/cli/commands/query.py` (print citekey, section, page span)
- [ ] T048 Implement CLI `validate` in `src/infrastructure/cli/commands/validate.py` (embedding model/tokenizer alignment; qdrant connectivity)
- [ ] T049 [P] Add integration smoke tests: `tests/integration/test_qdrant_smoke.py`, `tests/integration/test_docling_smoke.py`
- [ ] T050 [P] Add unit tests for policies and DTOs to reach domain ≥90% coverage
- [ ] T051 Document minimal `citeloom.toml` and sample commands in `README.md`
 - [x] T039 Implement `DoclingConverterAdapter` in `src/infrastructure/adapters/docling_converter.py` (parse PDF → structure/text)
 - [x] T040 Implement `DoclingHybridChunkerAdapter` in `src/infrastructure/adapters/docling_chunker.py` (heading-aware chunks)
 - [x] T041 Implement `ZoteroCslJsonResolver` in `src/infrastructure/adapters/zotero_metadata.py` (read CSL-JSON → CitationMeta)
 - [x] T042 Implement `FastEmbedAdapter` in `src/infrastructure/adapters/fastembed_embeddings.py` (batch embed)
 - [x] T043 Implement `QdrantIndexAdapter` in `src/infrastructure/adapters/qdrant_index.py` (upsert/search with project filter)
 - [x] T044 Wire `ingest_document` use case in `src/application/use_cases/ingest_document.py` (converter→chunker→resolver→embed→index)
 - [x] T045 Wire `query_chunks` use case in `src/application/use_cases/query_chunks.py` (hybrid flag respected; top_k applied)
 - [x] T046 Implement CLI `ingest` in `src/infrastructure/cli/commands/ingest.py` (read config; log audit file)
 - [x] T047 Implement CLI `query` in `src/infrastructure/cli/commands/query.py` (print citekey, section, page span)
 - [x] T048 Implement CLI `validate` in `src/infrastructure/cli/commands/validate.py` (embedding model/tokenizer alignment; qdrant connectivity)
 - [x] T049 [P] Add integration smoke tests: `tests/integration/test_qdrant_smoke.py`, `tests/integration/test_docling_smoke.py`
 - [ ] T050 [P] Add unit tests for policies and DTOs to reach domain ≥90% coverage
 - [ ] T051 Document minimal `citeloom.toml` and sample commands in `README.md`

- [ ] T054 Add hybrid retrieval config flag and path in `query_chunks` (ingest-time vs query-time sparse note)
- [ ] T055 Add integration test for hybrid flag in `tests/integration/test_query_hybrid.py` (verify both modes execute)
- [ ] T056 Add perf smoke: ingest single small PDF ≤ 2 min in `tests/integration/test_perf_smoke.py` (mark as slow, skip in default if env var missing)
- [ ] T057 Add perf smoke: query top-6 ≤ 1s against local Qdrant in `tests/integration/test_perf_smoke.py`
- [ ] T058 Ensure correlation id is logged per ingest run (augment `validate` or ingest path) and assert presence in test logs `tests/integration/test_logging.py`

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup (Phase 1) → Foundational (Phase 2) → User Stories (US1 → US2 → US3) → Polish
 - MVP Ingest/Query (Phase F) depends on Phase 2 completion

### User Story Dependencies
- US1 has no dependency on US2/US3
- US2 depends on Setup/Foundational only
- US3 depends on Setup/Foundational only

### Within Each User Story
- Update README/spec first, then validate consistency

### Parallel Opportunities
- T003/T004 can run in parallel
- Creating domain/policy/types (T017–T018) and ports (T019) can run in parallel
- Implementing embeddings (T042) and Qdrant index (T043) can run in parallel
- US1 tasks T026 and T028 can run in parallel
- US2 tasks T030/T031 can run in parallel
- US3 tasks T033/T035 can run in parallel

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1 and Phase 2
2. Complete US1 tasks (T026–T029)
3. Validate README shows correct name and tagline

### Incremental Delivery
1. Deliver US1 → merge to main
2. Deliver US2 → merge to main
3. Deliver US3 → merge to main
4. Deliver Phase F to enable first ingest/query end-to-end
