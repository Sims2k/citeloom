# Implementation Plan: Project-Scoped Citable Chunk Retrieval

**Branch**: `002-chunk-retrieval` | **Date**: 2025-01-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-chunk-retrieval/spec.md`

## Summary

This milestone implements the core ingestion, chunking, retrieval, and MCP integration capabilities for CiteLoom. Researchers can ingest long-form documents (PDFs, books up to 1000+ pages) into project-scoped collections, with documents automatically chunked using heading-aware segmentation, enriched with citation metadata from Zotero CSL-JSON exports, and stored in Qdrant vector databases. Queries support semantic and hybrid (query-time fusion) retrieval with strict project filtering, returning trimmed chunks with citation-ready metadata. MCP tools expose these capabilities to AI development environments (Cursor, Claude Desktop) with safe, time-bounded operations.

**Technical approach**: Clean Architecture with Docling (conversion/chunking), Qdrant (vector store with hybrid retrieval), FastEmbed/OpenAI (embeddings), Zotero CSL-JSON (metadata resolution), and MCP protocol (editor integration).

## Technical Context

**Language/Version**: Python 3.12.x (pinned in `.python-version`, managed via pyenv)  
**Primary Dependencies**: 
- Docling (document conversion with OCR, heading tree, page mapping)
- Qdrant Python client (vector database operations, hybrid retrieval)
- FastEmbed (local embeddings, default MiniLM)
- OpenAI Python SDK (optional embeddings via env)
- Typer (CLI framework)
- Rich (terminal formatting)
- Pydantic (data validation, settings)
- MCP SDK (Model Context Protocol for editor integration)

**Storage**: 
- Qdrant (vector database, per-project collections)
- Local filesystem (CSL-JSON reference files, audit logs in JSONL format)
- No traditional relational database required

**Testing**: 
- pytest (unit, integration, architecture tests)
- pytest-cov (coverage reporting)
- Domain layer: ≥90% coverage (prefer 100%)
- Overall: ≥80% coverage target

**Target Platform**: 
- Local development (macOS, Linux, Windows)
- Single-user local system (no multi-tenant requirements)
- MCP tools exposed via stdio/SSE for editor integration

**Project Type**: Single Python package with CLI entrypoint and MCP server capabilities

**Performance Goals**: 
- Ingest: ≤2 minutes for two 50+ page PDFs with complex layouts (SC-001)
- Query: ≤1 second for semantic search on projects with ≤10,000 chunks (SC-003)
- Hybrid query: ≤1.5 seconds with combined scoring (SC-004)
- MCP operations: ≤15 seconds for typical queries, <1% timeout rate (SC-005)
- Validation: ≤5 seconds for all checks (SC-006)

**Constraints**: 
- Deterministic chunk IDs required for idempotency
- Embedding model consistency enforced (write-guard in Qdrant)
- Project filtering mandatory in all retrieval operations
- Top-k capped at 6 by default (configurable)
- Chunk text trimmed to max_chars_per_chunk policy limit
- Tokenizer family must match embedding model family (validated)

**Scale/Scope**: 
- Single-user local system
- Projects: No explicit limit (user-controlled via directory selection)
- Documents per project: Large documents (1000+ pages) supported
- Chunks per project: Tested up to 10,000 chunks per project
- No automatic deletion; manual lifecycle management

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Clean Architecture Compliance
- ✅ Domain layer pure (no I/O, no frameworks)
- ✅ Application layer orchestrates domain via ports/protocols
- ✅ Infrastructure adapters implement ports
- ✅ Dependency direction: Infrastructure → Application → Domain (inward only)

### Toolchain Compliance
- ✅ Python 3.12.x via pyenv (`.python-version` present)
- ✅ uv for package/env management (no `pip install` allowed)
- ✅ Ruff for linting/formatting
- ✅ mypy with strict typing in `src/domain`
- ✅ pytest for testing

### Testing Requirements
- ✅ Domain unit tests (pure, isolated)
- ✅ Application tests with doubles for ports
- ✅ Infrastructure integration tests
- ✅ Architecture tests (dependency direction)
- ✅ Coverage: Domain ≥90% (prefer 100%), Overall ≥80%

### Observability
- ✅ Structured logging with correlation ID per ingest run
- ✅ Audit JSONL logs per ingest operation
- ✅ Minimal logging (no PII in logs)

### Security Posture
- ✅ Single-user local system (no auth required for CLI)
- ✅ Optional authentication for MCP tools
- ✅ No secrets in logs or committed files
- ✅ Environment variables for sensitive config (OPENAI_API_KEY)

**Gate Status**: ✅ PASS — All constitution requirements met. Ready for Phase 0 research.

## Project Structure

### Documentation (this feature)

```text
specs/002-chunk-retrieval/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── ports.md         # Application layer port contracts
│   └── mcp-tools.md     # MCP tool contracts
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── domain/
│   ├── policy/
│   │   ├── chunking_policy.py    # ChunkingPolicy (max_tokens, overlap, heading_context, tokenizer_id)
│   │   └── retrieval_policy.py    # RetrievalPolicy (top_k, hybrid_enabled, min_score, max_chars_per_chunk)
│   ├── models/
│   │   ├── conversion_result.py   # ConversionResult (doc_id, structure, plain_text)
│   │   ├── chunk.py               # Chunk (id, doc_id, text, page_span, section_heading, section_path, chunk_idx)
│   │   └── citation_meta.py      # CitationMeta (citekey, title, authors, year, doi/url, tags, collections)
│   ├── errors.py                  # Domain errors (EmbeddingModelMismatch, ProjectNotFound, etc.)
│   └── types.py                   # Value objects (ProjectId, CiteKey, PageSpan, SectionPath)
│
├── application/
│   ├── ports/
│   │   ├── converter.py           # TextConverterPort (Protocol)
│   │   ├── chunker.py              # ChunkerPort (Protocol)
│   │   ├── metadata_resolver.py   # MetadataResolverPort (Protocol)
│   │   ├── embeddings.py           # EmbeddingPort (Protocol)
│   │   └── vector_index.py         # VectorIndexPort (Protocol)
│   ├── dto/
│   │   ├── ingest.py               # IngestRequest, IngestResult
│   │   └── query.py                 # QueryRequest, QueryResult, QueryResultItem
│   └── use_cases/
│       ├── ingest_document.py      # IngestDocument orchestrator
│       ├── reindex_project.py      # ReindexProject orchestrator
│       ├── query_chunks.py         # QueryChunks orchestrator
│       ├── inspect_index.py        # InspectIndex orchestrator
│       └── validate_index.py       # ValidateIndex orchestrator
│
└── infrastructure/
    ├── adapters/
    │   ├── docling_converter.py    # DoclingConverterAdapter (TextConverterPort)
    │   ├── docling_chunker.py      # DoclingHybridChunkerAdapter (ChunkerPort)
    │   ├── zotero_metadata.py      # ZoteroCslJsonResolver (MetadataResolverPort)
    │   ├── fastembed_embeddings.py  # FastEmbedAdapter (EmbeddingPort)
    │   ├── openai_embeddings.py     # OpenAIAdapter (EmbeddingPort, optional)
    │   └── qdrant_index.py         # QdrantIndexAdapter (VectorIndexPort)
    ├── cli/
    │   ├── main.py                 # Typer app entrypoint
    │   └── commands/
    │       ├── ingest.py           # ingest command
    │       ├── reindex.py           # reindex command
    │       ├── query.py             # query command
    │       ├── inspect.py           # inspect command
    │       └── validate.py          # validate command
    ├── mcp/
    │   ├── server.py                # MCP server setup
    │   └── tools.py                 # MCP tool implementations
    ├── config/
    │   └── settings.py             # Pydantic settings from citeloom.toml
    └── logging.py                   # Structured logging setup

tests/
├── unit/
│   ├── test_domain_policies.py     # ChunkingPolicy, RetrievalPolicy tests
│   ├── test_domain_types.py        # Value objects tests
│   └── test_domain_models.py       # ConversionResult, Chunk, CitationMeta tests
├── integration/
│   ├── test_docling_smoke.py       # Docling conversion/chunking integration
│   ├── test_qdrant_smoke.py        # Qdrant operations integration
│   ├── test_zotero_metadata.py    # Zotero CSL-JSON matching
│   ├── test_query_hybrid.py        # Hybrid search integration
│   ├── test_perf_smoke.py          # Performance smoke tests (skipped by default)
│   └── test_logging.py             # Correlation ID logging
└── architecture/
    └── test_import_linter.py       # Dependency direction enforcement
```

**Structure Decision**: Single Python package following Clean Architecture with three layers (domain, application, infrastructure). CLI and MCP server entrypoints in infrastructure layer. All adapters implement ports defined in application layer. Domain layer is pure with no framework dependencies.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations detected. All architecture decisions align with Clean Architecture principles and constitution requirements.
