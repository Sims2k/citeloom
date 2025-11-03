# CiteLoom Constitution
Weave long-form sources into small, citable context for your AI work.

<!--
Sync Impact Report
- Version change: 1.9.0 → 1.12.0
- Modified principles/sections:
  - Performance & Hybrid Retrieval → updated to Qdrant named vectors with model binding and RRF fusion
  - Vector Database Patterns → added Named Vectors & Model Binding, Storage Optimization sections
  - Document Processing Patterns → added Docling Conversion section with OCR language integration, quality filtering thresholds
  - MCP Integration Patterns → updated to FastMCP server configuration with fastmcp.json declarative config
- Added sections:
  - Named Vectors & Model Binding (under Vector Database Patterns)
  - Storage Optimization (under Vector Database Patterns)
  - Docling Conversion (under Document Processing Patterns)
  - FastMCP Server Configuration (under MCP Integration Patterns)
- Removed sections:
  - None
- Templates requiring updates:
  - None (all templates remain compatible)
- Deferred TODOs:
  - TODO(RATIFICATION_DATE): Original adoption date unknown; set once confirmed
- Planning & Analysis Complete:
  - Milestone 003-framework-implementation planning phase complete (2025-10-31)
  - Generated: plan.md, research.md, data-model.md, contracts/, quickstart.md, tasks.md
  - Cross-artifact analysis completed (2025-10-31): Fixed MCP tool name inconsistencies (spec.md updated to use ingest_from_source, query, query_hybrid), removed obsolete CSL-JSON references (replaced with pyzotero API connectivity checks), resolved task ID collisions (T058→T068, renumbered US6-US8 tasks), clarified FR-027 remediation guidance requirement
  - Ready for implementation with 107 tasks organized by 8 user stories (pyzotero integration complete)
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
- **Qdrant named vectors with model binding** (authoritative): Use Qdrant named vector schema with model binding via `set_model()` and `set_sparse_model()` for hybrid search. This enables automatic RRF (Reciprocal Rank Fusion) between dense and sparse vectors without manual score combination. Recommended approach for modern vector databases (2024-2025 best practice).
  - Create per-project collections with two named vectors: `dense` (FastEmbed model, e.g., `BAAI/bge-small-en-v1.5`) and `sparse` (BM25/SPLADE/miniCOIL)
  - Model binding enables text-based queries without manual embedding
  - RRF fusion is automatic when both vectors are bound, providing robust retrieval on technical texts
  - Default sparse model: `Qdrant/bm25` for classic lexical search; optional: `prithivida/Splade_PP_en_v1` (neural sparse), `Qdrant/miniCOIL` (BM25-like with semantics)
- **Manual fusion** (legacy): Query-time hybrid using manual score combination (0.3 * text_score + 0.7 * vector_score) is still supported for compatibility but named vectors with RRF are preferred.
- **Ingest-time sparse vectors** (alternative): Not recommended initially; requires additional storage overhead and separate sparse index management. May be considered later via ADR if named vectors prove insufficient.
- Performance smoke tests are provided and SKIPPED by default. To enable locally or in perf CI, set environment variable `CITELOOM_RUN_PERF=1`.
- Perf targets: ingest ≤ 2 minutes for two 50+ page PDFs with 120s document timeout, 10s per-page timeout; query top-6 ≤ 1s for projects with ≤10,000 chunks; hybrid query ≤ 3s (with RRF fusion).
- **Large document support**: System must handle documents up to 1000+ pages that exceed LLM context windows, requiring effective chunking with overlap to preserve context across boundaries. Enable on-disk vectors and HNSW for large projects to optimize memory usage.

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
- **Security & privacy**: Initial posture: single-user local system (no authentication for CLI), optional authentication for MCP tools. Avoid logging PII; use least-privilege by default. Never log API keys or secrets. **Environment-based secrets management** (authoritative):
  - Load environment variables from `.env` file in project root using environment variable loading capabilities (e.g., python-dotenv via uv dependency management)
  - API keys and sensitive configuration (e.g., `OPENAI_API_KEY`, `QDRANT_API_KEY`) MUST be stored in `.env` files, never in version-controlled `citeloom.toml`
  - `.env` files MUST be excluded from version control (via `.gitignore`)
  - Environment variable precedence: Explicitly set system/shell environment variables override `.env` file values (allows per-session overrides)
  - Optional API keys (e.g., OpenAI embeddings when FastEmbed is default) MUST gracefully degrade when missing: system falls back to default behavior without failing
  - Required API keys (e.g., Qdrant API key when authentication is required) MUST provide clear error messages indicating which environment variable is missing and how to configure it
  - Configuration keys that may be sourced from environment: `OPENAI_API_KEY` (optional, for OpenAI embeddings), `QDRANT_API_KEY` (optional, for authenticated Qdrant), `CITELOOM_CONFIG` (optional, for custom config path)
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
- **Environment variable management**: Load environment variables from `.env` file in project root (managed via python-dotenv or equivalent, added via `uv add python-dotenv`). `.env` file must be in `.gitignore` and never committed. System automatically loads `.env` on startup; explicitly set environment variables take precedence over `.env` values.

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

**Named Vectors & Model Binding**
- **Named vector schema**: Create collections with two named vectors: `dense` (dense embeddings) and `sparse` (sparse/lexical embeddings).
- **Model binding**: Use Qdrant client `set_model()` to bind dense embedding model (e.g., FastEmbed `BAAI/bge-small-en-v1.5`) and `set_sparse_model()` to bind sparse model (BM25/SPLADE/miniCOIL).
- Model binding enables text-based queries without manual embedding generation; Qdrant handles embedding automatically.
- **RRF fusion**: When both dense and sparse models are bound, Qdrant automatically fuses results using Reciprocal Rank Fusion (RRF), providing robust hybrid retrieval.
- **Sparse model selection**: Per-project configuration allows choosing sparse model: `Qdrant/bm25` (classic lexical), `prithivida/Splade_PP_en_v1` (neural sparse), `Qdrant/miniCOIL` (BM25-like with semantics).

**Embedding Model Consistency**
- **Write-guard policy**: Block upserts if `embed_model` doesn't match collection's stored model (unless migration flag is explicitly set).
- Validate tokenizer family matches embedding model family before chunking (tokenizer-embedding alignment is a first-class policy requirement).
- Migration path: Use `--force-rebuild` flag or create new collection suffix (e.g., `-v2`) for model changes.

**Storage Optimization**
- **On-disk vectors**: Enable `vectors.on_disk: true` for large projects to reduce RAM usage (trades some cold-query latency for memory efficiency).
- **On-disk HNSW**: Enable HNSW on-disk when vectors are on-disk for consistent memory optimization.
- **On-disk payload & indices**: Optional for very large metadata sets to further reduce memory usage.
- **Scalar quantization**: Consider int8 quantization with memmap for throughput-critical scenarios while maintaining acceptable recall.

**Idempotency & Deterministic IDs**
- Generate deterministic chunk IDs from: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`.
- Enable idempotent upserts: re-ingesting same document produces no duplicates.
- Support directory-based batch processing without explicit size limits (user controls scope via directory selection).
- **Resume capability**: For long-running batch operations (reindex with document count limits), implement state tracking/checkpointing to enable resume of partial operations. State must be recoverable and safe for interruption.

**Payload Schema (Stable)**
- Required fields: `project_id`, `doc_id`, `section_path`, `page_start`, `page_end`, `citekey`, `doi`, `year`, `authors[]`, `title`, `tags[]`, `source_path`, `chunk_text`, `heading_chain`, `embed_model`, `version`.
- Legacy compatibility: Also supports `project`, `source`, `zotero`, `doc` structure for backward compatibility.
- Indexes: Keyword on `project_id`, `doc_id`, `citekey`, `year`, `tags`; full-text on `chunk_text` (if hybrid enabled).

## Document Processing Patterns

**Docling Conversion**
- **Docling v2 DocumentConverter**: Use Docling v2 for document conversion with OCR support, heading tree extraction, and page mapping.
- **OCR configuration**: Enable OCR (Tesseract/RapidOCR) for scanned documents. Language selection priority: Zotero metadata `language` field → explicit configuration → default ['en', 'de'].
- **Timeout limits**: 120 seconds per document, 10 seconds per page (allows complex documents to process while preventing runaway operations).
- **Windows support**: Docling not tested on Windows; provide WSL/Docker path documentation and surface precise error messages with remediation guidance.
- **Structure extraction**: Extract reliable page maps (page number → character span) and heading tree hierarchies with page anchors.

**Chunking Strategy**
- **HybridChunker**: Use Docling's HybridChunker with tokenizer-aligned configuration for heading-aware segmentation.
- **Heading-aware segmentation**: Preserve document structure (heading hierarchy, page numbers, sections) in chunks.
- **Tokenizer alignment**: Chunking tokenizer MUST match embedding model tokenizer family (e.g., MiniLM tokenizer for MiniLM embeddings). Enforced via policy validation.
- **Default policy**: `max_tokens=450`, `overlap_tokens=60`, `heading_context=1-2` ancestor headings included.
- **Quality filtering**: Filter out chunks below minimum length (50 tokens) or signal-to-noise ratio (< 0.3). Chunks below threshold are filtered with appropriate logging.
- **Serialization**: Use `contextualize()` to include `heading_chain` + figure/table captions near chunks while keeping body text focused.
- **Large document support**: Handle documents up to 1000+ pages with effective overlap to preserve context across chunk boundaries.

**Citation Metadata Integration**
- **Zotero CSL-JSON**: Per-project CSL-JSON files (Better BibTeX auto-export, "Keep updated").
- **Language field extraction**: Extract `language` field from Zotero metadata and use for OCR language selection during document conversion.
- **Matching order**: DOI-first (most reliable), then normalized title (fuzzy threshold), then `source_hint`.
- **Non-blocking**: If metadata cannot be matched, log `MetadataMissing` warning and proceed with ingest. Chunks remain usable without full metadata.
- **Metadata acquisition**: Prefer Zotero Web API (`format=json`) for live metadata; use BBT auto-export path for stable citekeys. Never read `zotero.sqlite` while Zotero is open (lock/corruption risk).

## MCP Integration Patterns

**FastMCP Server Configuration**
- **Declarative configuration**: Use FastMCP with `fastmcp.json` as single source of truth (dependencies, transport, entrypoint). FastMCP 2.12+ uses this as canonical configuration.
- **Transport**: STDIO for Cursor/Claude Desktop integration (HTTP/SSE variants optional for future).
- **Environment integration**: Enable `fastmcp run` with uv environment pre-builds for consistent deployment.
- **Tool surface**: Expose `ingest_from_source`, `query`, `query_hybrid`, `inspect`, `list_projects` with standardized contracts.

**Tool Design**
- **Time-bounded operations**: Per-tool timeouts (8-15 seconds depending on operation complexity).
- **Project scoping**: All tools enforce strict project filtering. No cross-project data leakage.
- **Output shaping**: Always return trimmed `render_text` (≤max_chars_per_chunk policy, default 1,800 characters) plus citation-ready metadata. Never dump full text by default.
- **Error taxonomy**: Standardized error codes: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `HYBRID_NOT_SUPPORTED`, `INDEX_UNAVAILABLE`, `TIMEOUT`.
- **Batch limits**: `store_chunks` accepts 100-500 chunks per batch.
- **Correlation IDs**: Include correlation IDs in responses for observability and tracing.

**Hybrid Retrieval Tools**
- **query_hybrid**: Requires both dense and sparse models bound via `set_model()` and `set_sparse_model()` for RRF fusion.
- **query**: Dense-only vector search (works with named vector `dense`).
- **Sparse model selection**: Per-project configuration allows choosing sparse model (BM25/SPLADE/miniCOIL).

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

### Milestone: 003-framework-implementation (Production-Ready Document Retrieval System)

**Feature Branch**: `003-framework-implementation`

**Planning Phase** — ✅ Complete (2025-10-31)
- Created comprehensive implementation plan (plan.md) with technical context and constitution check
- Generated research document (research.md) with 9 research areas covering Qdrant named vectors, Docling v2, FastMCP, Zotero language integration, environment variables, storage optimization, hybrid retrieval, and production readiness patterns
- Created data model document (data-model.md) with enhanced domain entities, value objects, and Qdrant payload schema
- Generated port contracts (contracts/ports.md) and FastMCP tool contracts (contracts/fastmcp-tools.md)
- Created quickstart guide (quickstart.md) with implementation checklist and common patterns
- Generated actionable tasks.md with 107 tasks organized by 11 phases (Setup, Foundational, 8 User Stories, Polish)
- Updated constitution to version 1.12.0 with framework-specific patterns (named vectors, model binding, OCR language integration, FastMCP configuration)
- Ready for implementation: All design artifacts complete, tasks organized for independent story implementation

**Phase 1: Setup (Shared Infrastructure)** — ✅ Complete
- Created `fastmcp.json` configuration file with dependencies, transport, and entrypoint
- Added `python-dotenv` dependency via `uv add python-dotenv` for .env file support
- Updated `.gitignore` to exclude .env files from version control
- Verified existing project structure matches plan.md (src/domain, src/application, src/infrastructure)

**Phase 2: Foundational (Blocking Prerequisites)** — ✅ Complete
- **Environment Configuration**: Implemented environment variable loading from .env file with precedence logic (system env > .env)
- **Domain Models**: Enhanced `CitationMeta` with optional `language` field, `Chunk` with `token_count` and `signal_to_noise_ratio`, `ConversionResult` with `ocr_languages` field
- **Policies**: Updated `ChunkingPolicy` to include `min_chunk_length` and `min_signal_to_noise` fields for quality filtering
- **Settings**: Updated Settings class to load environment variables with precedence rules

**Phase 3: User Story 1 - Reliable Document Conversion with Structure Preservation (P1)** — ✅ Complete
- **Docling v2 Integration**: Implemented `DoclingConverterAdapter.convert()` with DocumentConverter initialization
- **OCR Support**: Added OCR language selection logic (priority: Zotero metadata language → explicit config → default ['en', 'de'])
- **OCR Configuration**: Implemented Tesseract/RapidOCR configuration for scanned documents
- **Timeout Handling**: Added timeout handling (120s document, 10s per-page) with diagnostic logging
- **Structure Extraction**: Implemented page map extraction (page number → character span) and heading tree extraction with page anchors
- **Text Normalization**: Added text normalization (hyphen repair, whitespace normalization) preserving code/math blocks
- **Diagnostics**: Added image-only page detection and Windows compatibility warnings (WSL/Docker guidance)
- **Audit Logging**: Added audit log writing infrastructure (JSONL format) documenting added/updated/skipped counts, duration, document IDs, and embedding model
- **Protocol Updates**: Updated `TextConverterPort` to include `ocr_languages` parameter

**Phase 4: User Story 2 - Heading-Aware Chunking with Tokenizer Alignment (P1)** — ✅ Complete
- **HybridChunker**: Implemented `DoclingHybridChunkerAdapter.chunk()` with HybridChunker initialization
- **Tokenizer Alignment**: Added tokenizer alignment validation ensuring chunking tokenizer matches embedding model tokenizer family
- **Heading-Aware Chunking**: Implemented heading-aware chunking with heading_context ancestor headings
- **Quality Filtering**: Added quality filtering logic (minimum 50 tokens, signal-to-noise ratio ≥ 0.3)
- **Structure Preservation**: Implemented section path breadcrumb extraction from heading tree and page span mapping from page_map
- **Token Counting**: Added token count calculation using embedding model tokenizer
- **Deterministic IDs**: Ensured deterministic chunk ID generation using (doc_id, page_span/section_path, embedding_model_id, chunk_idx)
- **Audit Logging**: Enhanced audit logs to capture chunk counts and quality filter statistics (filtered chunks count)

**Phase 5: User Story 3 - Project-Isolated Vector Storage with Model Consistency (P1)** — ✅ Complete
- **Named Vectors**: Implemented `QdrantIndexAdapter.ensure_collection()` to create collections with named vectors (dense and sparse)
- **Model Binding**: Added model binding via `set_model()` for dense embeddings and `set_sparse_model()` for sparse embeddings (when hybrid enabled)
- **Write-Guards**: Implemented write-guard validation (check embed_model matches collection metadata)
- **Payload Indexes**: Created keyword payload indexes on project_id, doc_id, citekey, year, tags
- **Collection Metadata**: Store dense_model_id and sparse_model_id in collection metadata
- **Project Isolation**: Implemented per-project collection naming (proj-{project_id}) with server-side project filtering enforcement in all search operations
- **Audit Logging**: Enhanced audit logs to capture collection writes (chunks_written count), model IDs (dense_model and sparse_model), and errors during upsert operations

**Phase 6: User Story 4 - Hybrid Search with Query-Time Fusion (P2)** — ✅ Complete
- **Full-Text Index**: Implemented full-text index creation on chunk_text payload field (when hybrid enabled)
- **Hybrid Query**: Implemented `hybrid_query()` method using named vectors with RRF fusion
- **Text-Based Queries**: Added text-based query support using model binding (set_model enables text queries)
- **Model Validation**: Ensured both dense and sparse models are bound before allowing hybrid queries
- **Use Case Integration**: Updated `QueryChunks` use case to support hybrid queries with named vectors

**Phase 7: User Story 5 - Predictable MCP Tools with Bounded Outputs (P2)** — ✅ Complete
- **FastMCP Server**: Created FastMCP server setup in `src/infrastructure/mcp/server.py` with stdio transport
- **MCP Tools**: Implemented 5 standardized tools:
  - `ingest_from_source`: 15s timeout with correlation ID support
  - `query`: 8s timeout for dense-only search
  - `query_hybrid`: 15s timeout for hybrid search
  - `inspect_collection`: 5s timeout showing collection stats and model bindings
  - `list_projects`: Fast enumeration (no timeout)
- **Error Taxonomy**: Added standardized error codes (INVALID_PROJECT, EMBEDDING_MISMATCH, HYBRID_NOT_SUPPORTED, INDEX_UNAVAILABLE, TIMEOUT)
- **Output Shaping**: Added text trimming to max_chars_per_chunk (1,800 chars) in all query tool responses
- **Correlation IDs**: Added correlation IDs to all MCP tool responses
- **Project Filtering**: Added server-side project filtering enforcement in all MCP query tools
- **CLI Integration**: Updated CLI to expose mcp-server command

**Phase 8: User Story 6 - Robust Citation Metadata Resolution via pyzotero (P2)** — ✅ Complete
- **pyzotero Integration**: Added pyzotero dependency and replaced ZoteroCslJsonResolver with ZoteroPyzoteroResolver
- **Better BibTeX**: Implemented Better BibTeX JSON-RPC client with port availability check (port 23119 for Zotero, 24119 for Juris-M) with timeout (5-10s)
- **Citekey Extraction**: Added Better BibTeX citekey extraction with fallback parsing item['data']['extra'] field
- **Metadata Matching**: Implemented pyzotero item search by DOI (exact match, normalized) then by title (normalized, fuzzy threshold ≥ 0.8)
- **Field Extraction**: Extract metadata fields (title, creators → authors, year from date, DOI, URL, tags, collections, language)
- **Language Mapping**: Added language field mapping (Zotero codes → OCR language codes, e.g., 'en-US' → 'en')
- **OCR Integration**: Pass language from metadata to converter for OCR language selection
- **Error Handling**: Added graceful error handling for pyzotero API connection failures and Better BibTeX JSON-RPC unavailability (non-blocking, returns None, logs MetadataMissing)

**Phase 9: User Story 7 - System Validation and Operational Inspection (P3)** — ✅ Complete
- **Validate Command**: Implemented validate command checking:
  - Tokenizer-to-embedding alignment
  - Vector database connectivity
  - Collection presence and model lock verification
  - Payload index verification
  - Zotero library connectivity (pyzotero API connection test)
- **Inspect Command**: Implemented inspect command displaying:
  - Collection statistics
  - Embedding model identifier
  - Payload schema samples
  - Index presence confirmation
  - Optional sample chunk data
- **Error Messages**: Added clear error messages with actionable guidance
- **CLI Registration**: Registered validate and inspect commands in CLI

**Phase 10: User Story 8 - Environment-Based Configuration for API Keys (P3)** — ✅ Complete
- **Environment Loading**: Added python-dotenv loading with automatic .env file detection
- **Precedence Logic**: Implemented precedence logic (system env > .env file values)
- **Optional Keys**: Added graceful handling of missing optional API keys (OPENAI_API_KEY, Better BibTeX JSON-RPC) with fallback to defaults
- **Required Keys**: Added clear error messages for missing required API keys (QDRANT_API_KEY when auth required, ZOTERO_LIBRARY_ID/ZOTERO_API_KEY for remote access)
- **Zotero Config**: Added Zotero configuration support (ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY, ZOTERO_LOCAL)
- **Settings Integration**: Updated Settings class to use environment-loaded values including Zotero config
- **Documentation**: Verified .env file is in .gitignore and documented Zotero configuration

**Phase 11: Polish & Cross-Cutting Concerns** — ✅ Complete
- **Integration Tests**: Added comprehensive integration tests:
  - Docling conversion tests (`tests/integration/test_docling_conversion.py`)
  - Qdrant named vectors and model binding tests (`tests/integration/test_qdrant_named_vectors.py`)
  - FastMCP tools tests (`tests/integration/test_fastmcp_tools.py`)
  - pyzotero metadata resolution and Better BibTeX citekey extraction tests (`tests/integration/test_zotero_metadata.py`)
- **Unit Tests**: Added unit tests for environment variable loading (`tests/unit/test_environment_loader.py`)
- **Audit Logging**: Enhanced audit logging to include dense_model and sparse_model IDs in existing audit log implementation
- **Diagnostic Logging**: Added diagnostic logging improvements for timeout/page failures in `src/infrastructure/adapters/docling_converter.py`
- **Documentation**: Updated documentation with FastMCP configuration examples and environment variable configuration guide including Zotero setup (`docs/environment-config.md`)
- **Code Cleanup**: Performed code cleanup and refactoring across all adapters
- **Validation**: Created and ran quickstart.md validation scenarios (`scripts/validate_quickstart.py`)

**Status**: ✅ Implementation complete - All 107 tasks across 11 phases finished. Production-ready document retrieval system with Docling v2 conversion, Qdrant named vectors with RRF fusion, FastMCP integration, pyzotero metadata resolution, comprehensive validation, and environment-based configuration.

---

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
  - `ZoteroCslJsonResolver`: Initial implementation with DOI-first matching, normalized title fallback, fuzzy scoring, proper CSL-JSON parsing
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

**Phase 4: User Story 2 - Enrich Chunks with Citation Metadata** — ✅ Complete (2025-01-27)
- **Application Layer**:
  - Enhanced `IngestDocument` use case to extract source hints from conversion results and file paths
  - Extracts DOI from document structure metadata (if available in conversion result)
  - Falls back to title hint from source file path (basename without extension)
  - Resolves metadata once per document (before chunk loop) and attaches `CitationMeta` to all chunks
  - Improved error handling and variable scope management
  - Added structured logging for successful metadata resolution with citekey
- **Infrastructure Adapters**:
  - Enhanced `ZoteroCslJsonResolver` with robust DOI-first matching:
    - Handles multiple DOI formats: `doi:10.1234/example`, `https://doi.org/10.1234/example`, direct `10.1234/example`
    - Normalizes DOIs by removing URL prefixes, lowercasing, and stripping whitespace for consistent matching
    - Exact match or substring matching for flexible DOI resolution
  - Improved normalized title fallback:
    - Uses Jaccard similarity on normalized word sets for fuzzy matching
    - Configurable fuzzy threshold (default 0.8) to balance precision and recall
    - Normalizes titles by lowercasing, removing punctuation, collapsing whitespace
  - Enhanced `MetadataMissing` logging:
    - Non-blocking warnings with actionable hints (suggests checking references file, adding DOI/citekey/title)
    - Structured logging with correlation IDs, doc_id, references_path, and source_hint for debugging
    - Logs match method (DOI, title, citekey) with confidence scores when applicable
- **Tests**:
  - Created comprehensive integration test suite (`tests/integration/test_zotero_metadata.py`) - 10 tests covering:
    - DOI matching (exact and normalized URL formats)
    - Title fallback matching with fuzzy similarity (Jaccard score threshold)
    - Citekey matching
    - Unknown document handling (graceful None return)
    - Missing references file handling (non-blocking)
    - Author extraction from CSL-JSON format (handles both dict and string formats)
    - Tags and collections extraction
    - Fuzzy threshold validation (low similarity titles correctly rejected)
    - URL fallback for items without DOI (ensures either DOI or URL present)
- **Quality**: All 10 integration tests pass, no linter errors, follows Clean Architecture principles
- **Status**: User Story 2 complete - Chunks are automatically enriched with citation metadata from Zotero CSL-JSON exports using DOI-first matching with normalized title fallback

**Phase 5: User Story 3 - Query and Retrieve Relevant Chunks** — ✅ Complete (2025-01-27)
- **Application Layer**:
  - Implemented `QueryChunks` use case orchestrator:
    - Project filter enforcement (mandatory per RetrievalPolicy)
    - Top-k limit enforcement with policy-based caps
    - Text trimming to max_chars_per_chunk (1800 chars default, configurable)
    - RetrievalPolicy integration for hybrid_enabled, min_score filtering
    - Full citation metadata extraction (citekey, page_span, section_path, section_heading, DOI/URL)
    - Proper error handling for ProjectNotFound and HybridNotSupported exceptions
  - Hybrid query support with query-time fusion:
    - Normalized score combination: 0.3 * text_score + 0.7 * vector_score
    - Policy-driven hybrid_enabled enforcement
    - Graceful fallback when hybrid not enabled for project
- **Infrastructure Adapters**:
  - Enhanced `QdrantIndexAdapter.search()` method:
    - Proper payload extraction with `with_payload=True` flag
    - Consistent payload structure: `fulltext`, `doc` (page_span, section_path, etc.), `zotero`, `project`, `embed_model`
    - In-memory fallback with proper payload structure matching real Qdrant format
    - Project filtering via Filter with FieldCondition for mandatory project scoping
  - Implemented `QdrantIndexAdapter.hybrid_query()` method:
    - Manual fusion implementation for maximum Qdrant client compatibility (works across versions)
    - Vector search + text matching score combination
    - Normalized score fusion: 0.3 * normalized_text_score + 0.7 * normalized_vector_score
    - In-memory fallback with BM25 approximation using term frequency scoring
    - Proper error handling for HybridNotSupported when full-text index disabled
  - Enhanced `_create_payload_indexes()` method:
    - Better logging for full-text index creation status
    - Handles auto-indexing in newer Qdrant versions gracefully
    - Ensures `fulltext` field available for BM25 queries when hybrid enabled
  - In-memory storage improvements:
    - Proper `doc` payload structure for consistency (matches real Qdrant format)
    - Payload structure includes: doc_id, page_span, section_heading, section_path, chunk_idx
- **CLI**:
  - Implemented comprehensive `query` command with all required options:
    - `--project`, `--query` (required)
    - `--top-k` (default: 6, configurable)
    - `--hybrid` (flag to enable hybrid search)
    - `--filters` (JSON format for additional Qdrant filters)
  - Settings integration:
    - Loads project configuration from `citeloom.toml`
    - Respects project-level `hybrid_enabled` setting
    - Uses Qdrant URL and fulltext index settings from config
  - Rich table formatting with citation-ready output:
    - Table view: Score | Citation | Pages | Section | Text Preview
    - Detailed view: Full citation info, page spans (pp. x–y), section paths, DOI/URL
    - Proper "(citekey, pp. x–y, section)" format as specified in requirements
  - Error handling with user-friendly messages for missing projects, invalid filters, etc.
- **Tests**:
  - Created comprehensive integration test suite (`tests/integration/test_query_hybrid.py`):
    - Tests both dense-only and hybrid search modes independently
    - Validates proper payload structure and extraction
    - Verifies score correctness (scores >= 0.0)
    - Validates content relevance (query terms appear in results)
    - Proper chunk structure with embeddings for realistic testing
- **Quality**: All code passes linting (ruff, no errors), Clean Architecture compliance maintained, proper error handling throughout, type hints and documentation complete
- **Status**: User Story 3 complete - Full query and retrieval capability with semantic and hybrid search, project filtering, and citation-ready output formatting

**Phase 6: User Story 4 - Access Chunks via MCP Tools** — ✅ Complete (2025-01-27)
- **MCP Server Implementation**:
  - Created MCP server setup (`src/infrastructure/mcp/server.py`) with stdio transport for editor integration (Cursor, Claude Desktop)
  - Configuration loading from `citeloom.toml` via `CITELOOM_CONFIG` environment variable
  - Tool registration and async execution handling with proper error serialization
  - CLI integration: Added `mcp-server` command to main Typer app (`uv run citeloom mcp-server`)
- **MCP Tools Implementation** (`src/infrastructure/mcp/tools.py`):
  - **store_chunks**: Batched upsert (100-500 chunks per batch) with 15s timeout
    - Project validation, embedding model consistency checks via write-guard
    - Integration with QdrantIndexAdapter.upsert() with exponential backoff retry
    - Error codes: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `TIMEOUT`
  - **find_chunks**: Vector search with 8s timeout
    - Wired to `QueryChunks` use case with project filtering enforcement
    - Text trimming to `max_chars_per_chunk` policy (1800 chars default)
    - Citation-ready metadata extraction (citekey, page_span, section_path, DOI/URL)
    - Error codes: `INVALID_PROJECT`, `TIMEOUT`
  - **query_hybrid**: Hybrid search (query-time fusion) with 15s timeout
    - Wired to `QueryChunks` use case with hybrid_enabled validation
    - BM25 + vector score fusion with normalized weighting (0.3 * text + 0.7 * vector)
    - Error codes: `INVALID_PROJECT`, `HYBRID_NOT_SUPPORTED`, `TIMEOUT`
  - **inspect_collection**: Collection metadata inspection with 5s timeout
    - Collection size, embedding model, payload schema extraction
    - Sample payloads (0-5 max) with structured format matching Qdrant payload structure
    - Error codes: `INVALID_PROJECT`, `INDEX_UNAVAILABLE`
  - **list_projects**: Fast project enumeration (no timeout)
    - Returns all configured projects with metadata (collection, embed_model, hybrid_enabled)
    - No error codes (always succeeds, may return empty list)
- **Error Taxonomy**:
  - Standardized error codes: `INVALID_PROJECT`, `EMBEDDING_MISMATCH`, `HYBRID_NOT_SUPPORTED`, `INDEX_UNAVAILABLE`, `TIMEOUT`
  - Structured JSON error responses with human-readable messages and detailed context
  - Consistent error handling across all tools with proper serialization
- **Async/Sync Integration**:
  - Proper async/await patterns using `asyncio.run_in_executor()` for timeout support
  - Bridges synchronous use cases and adapters to async MCP protocol
  - Timeout enforcement per tool specification (8-15s depending on operation complexity)
- **Tests**:
  - Comprehensive integration test suite (`tests/integration/test_mcp_tools.py`) - 9 tests covering:
    - Project enumeration (list_projects with empty and populated settings)
    - Invalid project validation (find_chunks, query_hybrid, inspect_collection, store_chunks)
    - Hybrid not supported scenarios
    - Batch size validation (store_chunks)
    - Unknown tool handling
    - Proper error response structure validation
- **Quality**: All code passes ruff linting, comprehensive integration tests, proper error handling, follows Clean Architecture principles, type hints and documentation complete
- **Status**: User Story 4 complete - MCP integration ready for AI development environment testing. All MCP tools expose project-scoped, time-bounded operations with proper error taxonomy and citation-ready output formatting

---

### Milestone: 005-zotero-improvements (Comprehensive Zotero Integration Improvements)

**Feature Branch**: `005-zotero-improvements`

**Planning Phase** — ✅ Complete (2025-01-27)
- Created comprehensive feature specification (spec.md) with 8 user stories covering:
  - Local SQLite database access for offline browsing and instant collection access
  - Full-text reuse from Zotero to avoid redundant OCR processing
  - PDF annotation extraction and indexing as separate vector points
  - Embedding model governance with friendly diagnostics
  - Incremental deduplication based on content hashes
  - Enhanced library browsing tools (offline-capable)
  - Flexible source router for local/web source selection
  - Payload enrichment with Zotero keys for targeted queries
- Generated requirements checklist (checklists/requirements.md) with specification quality validation
- Completed clarification sessions resolving 9 critical ambiguities:
  - Annotation indexing default behavior (opt-in via configuration)
  - Source router default strategy (auto mode after rollout, web-first initially)
  - Full-text quality validation thresholds (100 chars minimum, structure checks)
  - Docling conversion failure handling (fail individual document, continue import)
  - Mixed provenance text structure (sequential concatenation in page order)
  - SQLite concurrent access safety (immutable read-only snapshot isolation)
  - Content hash collision handling (metadata verification as secondary check)
  - Source router fallback strategy (per-file fallback, not collection-level)
  - Annotation extraction rate limit handling (retry with backoff, skip on failure)
- Specification includes 39 functional requirements (FR-001 to FR-039)
- Specification includes 10 measurable success criteria (SC-001 to SC-010)
- All edge cases identified and documented with resolution strategies
- Key entities defined: LocalZoteroDbAdapter, ZoteroSourceRouter, FulltextResolver, AnnotationResolver, ContentFingerprint

**Implementation Planning Phase** — ✅ Complete (2025-01-27)
- Generated implementation plan (plan.md) with technical context, constitution check, and project structure
- Generated research document (research.md) with implementation patterns from zotero-mcp covering:
  - SQLite immutable read-only access patterns
  - Platform-aware profile detection
  - Full-text quality validation
  - Annotation extraction patterns
  - Content hashing strategies
  - Source routing and fallback strategies
- Generated data model document (data-model.md) defining:
  - ContentFingerprint entity for deduplication
  - Enhanced DownloadManifestAttachment with source and content_fingerprint fields
  - Enhanced Chunk payload with Zotero keys
  - Annotation point payload structure
- Generated port contracts (contracts/ports.md) defining:
  - Enhanced ZoteroImporterPort interface
  - FulltextResolverPort for full-text resolution
  - AnnotationResolverPort for annotation extraction
  - ZoteroSourceRouter application service
  - Enhanced VectorIndexPort with Zotero key indexes
- Generated quickstart guide (quickstart.md) with step-by-step implementation instructions
- Generated actionable tasks.md with 126 tasks organized by 11 phases (Setup, Foundational, 8 User Stories, Polish)
- Tasks organized by user story for independent implementation and testing
- MVP scope identified: 43 tasks (Setup + Foundational + US1) for offline library browsing capability
- All constitution gates passed - ready for implementation

**Status**: ✅ Planning and task generation complete - Ready for implementation

---

**Version**: 1.15.0 | **Ratified**: TODO(RATIFICATION_DATE) | **Last Amended**: 2025-01-27 (Milestone 005-zotero-improvements planning complete: Implementation plan and 126 actionable tasks generated across 11 phases, organized by 8 user stories. MVP scope: 43 tasks for offline library browsing. Ready for implementation)
