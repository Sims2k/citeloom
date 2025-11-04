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
- **Timeout limits**: Configurable timeouts (default: 600 seconds per document, 15 seconds per page) allowing complex documents to process while preventing runaway operations. Can be increased for very large documents (>1000 pages).
- **Windows support**: Docling not tested on Windows; provide WSL/Docker path documentation and surface precise error messages with remediation guidance.
- **Structure extraction**: Extract reliable page maps (page number → character span) and heading tree hierarchies with page anchors.
- **Windowed conversion**: For large documents (>1000 pages), process in page windows (default: 10 pages) to prevent timeouts. Automatic detection for documents exceeding threshold, manual override via `force_windowed_conversion` setting, progress tracking per window, and immediate chunking after each window conversion.
- **CPU optimization**: Optimize for CPU-only systems with fast table mode enabled, remote services disabled, feature toggles for expensive operations (code enrichment, formula enrichment, picture classification/description, page image generation), and CPU thread auto-detection.

**Chunking Strategy**
- **HybridChunker**: Use Docling's HybridChunker with tokenizer-aligned configuration for heading-aware segmentation.
- **Heading-aware segmentation**: Preserve document structure (heading hierarchy, page numbers, sections) in chunks.
- **Tokenizer alignment**: Chunking tokenizer MUST match embedding model tokenizer family (e.g., MiniLM tokenizer for MiniLM embeddings). Enforced via policy validation.
- **Default policy**: `max_tokens=450`, `overlap_tokens=60`, `heading_context=1-2` ancestor headings included.
- **Quality filtering**: Filter out chunks below minimum length (50 tokens) or signal-to-noise ratio (< 0.3). Chunks below threshold are filtered with appropriate logging.
- **Serialization**: Use `contextualize()` to include `heading_chain` + figure/table captions near chunks while keeping body text focused.
- **Large document support**: Handle documents up to 1000+ pages with effective overlap to preserve context across chunk boundaries. Windowed conversion enables processing very large documents (>1000 pages) by chunking each window immediately after conversion, then aggregating all chunks for embedding and indexing.

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

### Milestone: 002-chunk-retrieval (Project-Scoped Citable Chunk Retrieval)
**Branch**: `002-chunk-retrieval` | **Status**: ✅ Complete (2025-01-27)

**Core Accomplishments**:
- **Foundation**: Established Clean Architecture structure with domain, application, and infrastructure layers. Created domain models (`Chunk`, `CitationMeta`, `ConversionResult`), policies (`ChunkingPolicy`, `RetrievalPolicy`), and port protocols.
- **Document Ingestion**: Implemented `IngestDocument` use case with deterministic chunk ID generation, audit logging (JSONL format), and basic Docling integration (with Windows compatibility placeholders).
- **Metadata Resolution**: Enhanced citation metadata matching via `ZoteroCslJsonResolver` with DOI-first matching, normalized title fallback (Jaccard similarity), and CSL-JSON parsing.
- **Query & Retrieval**: Implemented `QueryChunks` use case with project filtering, hybrid search (manual fusion: 0.3 * text + 0.7 * vector), and citation-ready output formatting.
- **MCP Integration**: Created MCP server with 5 tools (`store_chunks`, `find_chunks`, `query_hybrid`, `inspect_collection`, `list_projects`) with time-bounded operations (8-15s) and standardized error taxonomy.
- **Vector Storage**: Implemented `QdrantIndexAdapter` with per-project collections, write-guards for embedding model consistency, payload indexes, and exponential backoff retry logic.

---

### Milestone: 003-framework-implementation (Production-Ready Document Retrieval System)
**Branch**: `003-framework-implementation` | **Status**: ✅ Complete

**Core Accomplishments**:
- **Docling v2 Integration**: Full document conversion with OCR support (Tesseract/RapidOCR), structure extraction (page maps, heading trees), and timeout handling (120s document, 10s per-page). OCR language selection: Zotero metadata → config → default ['en', 'de'].
- **Advanced Chunking**: Heading-aware chunking with tokenizer alignment validation, quality filtering (min 50 tokens, SNR ≥ 0.3), and deterministic ID generation from `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`.
- **Qdrant Named Vectors**: Per-project collections with named vectors (`dense`, `sparse`), model binding via `set_model()`/`set_sparse_model()`, and automatic RRF fusion for hybrid search.
- **FastMCP Tools**: Upgraded to FastMCP with `fastmcp.json` declarative configuration. Enhanced MCP tools with correlation IDs, output shaping (1,800 char limits), and improved error handling.
- **pyzotero Integration**: Replaced CSL-JSON resolver with `ZoteroPyzoteroResolver` using pyzotero API, Better BibTeX JSON-RPC (ports 23119/24119), and metadata extraction with language mapping for OCR.
- **Validation & Configuration**: Added `validate` and `inspect` commands for system health checks. Environment-based configuration (.env file with precedence: system env > .env file).
- **Testing & Documentation**: Comprehensive integration tests (Docling, Qdrant, FastMCP, pyzotero) and unit tests. Documentation for FastMCP configuration and environment setup.

---

### Milestone: 004-zotero-batch-import (Zotero Collection Import with Batch Processing)
**Branch**: `004-zotero-batch-import` | **Status**: ✅ Complete

**Core Accomplishments**:
- **Zotero Integration**: Implemented `ZoteroImporterAdapter` with pyzotero client, rate limiting (0.5s interval for web API), exponential backoff retry (3 retries, 1s base, 30s max, jitter), and local/remote API support. Supports collection browsing, recursive subcollections, PDF attachment fetching, and metadata extraction (title, creators, year, DOI, tags, collections).
- **Batch Import Use Case**: Created `BatchImportFromZotero` orchestrating two-phase workflow: download all attachments first (10-20 files per batch), then process through conversion/chunking/embedding pipeline. Generates correlation IDs for checkpoint naming, processes all PDF attachments per item as separate documents, preserves Zotero metadata in chunk payloads.
- **Progress Indication**: Implemented `RichProgressReporterAdapter` with document-level progress (X of Y), stage-level progress (converting, chunking, embedding, storing), elapsed time, estimated time remaining. Detects non-TTY mode and falls back to structured logging. Final summary with totals, chunks created, duration, warnings, and errors.
- **Checkpointing System**: Created `CheckpointManagerAdapter` with atomic checkpoint writes (temp file + atomic rename), JSON serialization, and validation. Implements resumable batch processing: saves checkpoint after each document/stage completion, enables resume with `--resume` flag skipping completed documents, validates checkpoint integrity before resuming. Checkpoint format: `var/checkpoints/{correlation_id}.json`.
- **Download Manifest**: Created download manifest system tracking downloaded attachments with `DownloadManifest` entity (collection_key, collection_name, download_time, items). Manifest includes `DownloadManifestItem` (item_key, title, attachments) and `DownloadManifestAttachment` (attachment_key, filename, local_path, download_status, file_size, error). Supports two-phase import: download without processing, then process downloaded files via manifest.
- **CLI Enhancements**: Added `zotero` command group with `list-collections`, `browse-collection`, `recent-items`, `list-tags` commands. Enhanced `ingest` command with `--zotero-collection`, `--zotero-tags`, `--exclude-tags`, `--resume`, `--fresh` flags. Added `ingest download` and `ingest process-downloads` commands for two-phase workflow.
- **Tag Filtering**: Implemented tag-based filtering with case-insensitive partial matching, OR logic for include tags, ANY-match logic for exclude tags. Filters items before downloading attachments to reduce unnecessary downloads.
- **Error Handling**: Comprehensive error handling for empty collections, network interruptions, corrupted PDFs, collection name typos, checkpoint file disappearance, and concurrent import processes.

---

### Milestone: 005-zotero-improvements (Comprehensive Zotero Integration Improvements)
**Branch**: `005-zotero-improvements` | **Status**: ✅ In Progress (2025-11-04)

**Scope**: 8 user stories with 130 tasks across 11 phases (MVP: 43 tasks for offline library browsing).

**Core Planned Features**:
- **Local SQLite Database Access (US1)**: `LocalZoteroDbAdapter` with platform-aware profile detection (Windows/macOS/Linux), immutable read-only snapshot isolation (SQLite URI mode with `immutable=1&mode=ro`), recursive CTE queries for subcollections, linkMode resolution (imported vs linked files), path resolution for attachment storage. CLI commands: `list-collections` (hierarchical with item counts), `browse-collection` (first N items with metadata), `recent-items`, `list-tags` (with usage counts). Error handling: `ZoteroDatabaseLockedError`, `ZoteroDatabaseNotFoundError`, `ZoteroProfileNotFoundError`, `ZoteroPathResolutionError`. ✅ **Implemented**: Old schema fallback support for pre-migration databases, migration detection with clear user guidance.
- **Full-Text Reuse (US2)**: `ZoteroFulltextResolverAdapter` querying `fulltext` table via SQLite, quality validation (non-empty, minimum 100 chars, structure checks), page-level mixed provenance tracking (`pages_from_zotero`, `pages_from_docling`), sequential page concatenation for mixed text, preference-based resolution (Zotero preference → Docling fallback). Integration into `ingest_document` use case before Docling conversion, skipping conversion when fulltext available but proceeding with chunking/embedding/indexing. Expected 50-80% speedup.
- **Annotation Indexing (US3)**: `ZoteroAnnotationResolverAdapter` fetching annotations via Web API `children()` method (`itemType=annotation`), normalization (pageIndex → page, extract quote/comment/color/tags), retry logic with exponential backoff (3 retries, base 1s, max 30s, jitter), graceful skipping on unavailability. Annotation payload structure with `type:annotation` tag, `zotero.item_key`, `zotero.attachment_key`, `zotero.annotation.*` fields. Opt-in configuration (`include_annotations=false` default).
- **Incremental Deduplication (US4)**: `ContentFingerprint` entity with `content_hash`, `file_mtime`, `file_size`, `embedding_model`, `chunking_policy_version`, `embedding_policy_version`. `ContentFingerprintService` computing fingerprints and detecting unchanged documents. Skip logic: skip processing if both hash AND metadata match; if hash matches but metadata differs, treat as changed (collision protection). Policy version checking invalidates fingerprints on policy changes. Stores fingerprint in `DownloadManifestAttachment` after download and processing.
- **Source Router (US5)**: `ZoteroSourceRouter` application service with strategy modes: `local-first` (per-file fallback to Web API), `web-first` (fallback to local DB on rate limits), `auto` (intelligent selection: prefer local if DB available and files exist, prefer web if local unavailable, smart selection based on speed/completeness), `local-only` (strict, no fallback), `web-only` (strict, backward compatible). Stores source markers (`"local" | "web"`) in `DownloadManifestAttachment.source` field. Per-file fallback strategy. ✅ **Implemented**: Automatic collection key format conversion (web ↔ local), comprehensive strategy testing, subcollection duplicate prevention.
- **Library Exploration (US6)**: Enhanced CLI commands with hierarchical collection structure, tag usage counts, recent items with metadata, publication years and creators in browse view. All operations work offline using local database.
- **Zotero Key Enrichment (US7)**: Enhanced chunk payloads with `zotero.item_key` and `zotero.attachment_key` fields, keyword indexes on both fields in `QdrantIndexAdapter.ensure_collection()`, query filtering by Zotero keys. Performance target: < 500ms for 10k chunks.
- **Embedding Model Diagnostics (US8)**: Enhanced `EmbeddingModelMismatch` error messages with collection name and resolution instructions, `--show-embedding-model` option in inspect command, embedding model display in MCP inspect tool response.

**Status**: Core infrastructure implemented (local adapter, source router, old schema fallback). Planning and task generation complete. All design artifacts (spec.md, plan.md, research.md, data-model.md, contracts/) generated. 130 tasks organized by user story. Implementation in progress.

---

---

### Milestone: 006-fix-zotero-docling (Zotero & Docling Performance and Correctness Fixes)
**Branch**: `006-fix-zotero-docling` | **Status**: ✅ Complete (2025-11-04)

**Core Accomplishments**:
- **Zotero Source Strategy Enhancements**: Implemented automatic collection key format conversion in `ZoteroSourceRouter` enabling seamless routing between local (numeric IDs) and web (alphanumeric keys) adapters. All source selection strategies (`local-first`, `web-first`, `auto`, `local-only`, `web-only`) now work with both key formats transparently. ✅ **Fixed**: Collection key format mismatch issue.
- **Subcollection Handling**: Fixed duplicate item prevention when including subcollections. Both local and web adapters now correctly handle nested subcollections with proper recursive traversal and duplicate detection. Verified with complex hierarchies (parent → subcollection → nested subcollections).
- **Adapter Consistency**: Implemented consistent attachment filtering across local and web adapters. Web adapter now filters out `attachment` and `annotation` item types to match local adapter behavior, ensuring identical results for same collections.
- **Old Schema Fallback**: Comprehensive fallback support for Zotero databases before migration (Zotero 7+ pre-migration). System automatically detects old schema (`itemData` table) and uses normalized queries to reconstruct item metadata, enabling full functionality even when database migration hasn't completed.
- **Migration Detection**: Enhanced database migration detection with clear, actionable error messages. System detects when Zotero 7+ is installed but database hasn't migrated, providing specific guidance: "Open Zotero desktop application once to trigger database migration."
- **Comprehensive Testing**: Created extensive test suite verifying all source strategies, edge cases, subcollection handling, and adapter consistency. All strategies tested and verified working correctly with both key formats.
- **Windowed Conversion System**: Implemented windowed conversion for large documents (>1000 pages) processing documents in page windows (default: 10 pages) to prevent timeouts. Features include automatic detection for large documents, manual override via `force_windowed_conversion` setting (independent of page count), progress tracking per window with time estimates, and immediate chunking after each window conversion. Verified working on 1096-page document (5 windows tested, 29 chunks created, average 21.3s per window).
- **Docling CPU Optimization**: Configured Docling for CPU-only systems with fast table mode enabled, remote services disabled, feature toggles for expensive operations (code enrichment, formula enrichment, picture classification/description, page image generation disabled), configurable timeouts (600s document, 15s page), and CPU thread auto-detection. Optimized for efficient CPU-only processing without timeouts.
- **Qdrant Bulk Indexing Optimization**: Implemented bulk indexing optimization disabling HNSW indexing during bulk upload (`indexing_threshold=0`) and re-enabling after upload (`indexing_threshold=20000`). Automatic collection existence check prevents errors during bulk operations. Integrated into batch import workflow for faster large batch uploads.
- **Heading-Aware Chunking**: Enhanced chunking with HybridChunker integration, token alignment validation, quality filtering (signal-to-noise ratio ≥0.3), section path breadcrumb extraction, and page span mapping. Per-window chunking for windowed conversion with proper chunk aggregation.
- **Documentation Consolidation**: Consolidated analysis documentation from 23 files into 4 essential documents (implementation summary, status summary, improvements tracking, recommendations). Removed temporary test scripts and redundant documentation. Created comprehensive user guides and implementation recommendations.

**Status**: ✅ Complete - All critical Zotero integration issues resolved, windowed conversion and CPU optimization implemented, production-ready with seamless local/web adapter interoperability and large document support.

---

**Version**: 1.17.0 | **Ratified**: TODO(RATIFICATION_DATE) | **Last Amended**: 2025-11-04 (Added Milestone 006 (fix-zotero-docling) completion: windowed conversion system, Docling CPU optimization, Qdrant bulk indexing optimization, heading-aware chunking enhancements, documentation consolidation)
