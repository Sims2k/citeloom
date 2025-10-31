# Implementation Plan: Production-Ready Document Retrieval System

**Branch**: `003-framework-implementation` | **Date**: 2025-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-framework-implementation/spec.md`

## Summary

This milestone hardens the production readiness of CiteLoom's document retrieval system. It completes Docling conversion with structure preservation (page maps, heading trees, OCR with language detection from Zotero metadata), implements heading-aware chunking with tokenizer alignment and quality filtering, tightens Qdrant collections with payload indexes and hybrid retrieval, finalizes MCP tool contracts with bounded outputs and standardized error codes, and adds environment-based configuration for API keys.

**Technical approach**: Complete framework-specific implementations for Docling (DocumentConverter with OCR and structure extraction, HybridChunker with tokenizer alignment), Qdrant (per-project collections with named vectors for dense+sparse hybrid search, payload indexes, on-disk storage for large projects), FastEmbed (model binding and cross-encoder rerankers), Zotero integration (language field extraction for OCR, CSL-JSON metadata resolution), and FastMCP server configuration.

## Technical Context

**Language/Version**: Python 3.12.x (pinned in `.python-version`, managed via pyenv)

**Primary Dependencies**:
- Docling v2 (DocumentConverter with OCR, HybridChunker with heading-aware chunking)
- Qdrant Python client (named vectors for dense+sparse hybrid, model binding via `set_model()` and `set_sparse_model()`, RRF fusion)
- FastEmbed (dense embeddings, sparse models BM25/SPLADE/miniCOIL, cross-encoder rerankers)
- python-dotenv (environment variable loading from `.env` files)
- Typer (CLI framework)
- Rich (terminal formatting)
- Pydantic (data validation, settings)
- FastMCP (Model Context Protocol server, `fastmcp.json` configuration)

**Storage**:
- Qdrant (per-project collections with named vectors, on-disk vectors/HNSW for large projects, payload indexes, full-text indexes)
- Local filesystem (CSL-JSON reference files, audit logs in JSONL format, `.env` files)
- No traditional relational database required

**Testing**:
- pytest (unit, integration, architecture tests)
- pytest-cov (coverage reporting)
- Domain layer: ≥90% coverage (prefer 100%)
- Overall: ≥80% coverage target

**Target Platform**:
- Local development (macOS, Linux, Windows with WSL/Docker fallback for Docling)
- Single-user local system (no multi-tenant requirements)
- FastMCP tools exposed via STDIO for editor integration (Cursor, Claude Desktop)

**Project Type**: Single Python package with CLI entrypoint and FastMCP server capabilities

**Performance Goals**:
- Document conversion: 120s per document, 10s per page timeout limits (handles complex documents)
- Query: ≤3 seconds for hybrid search on projects with ≤10,000 chunks (SC-006)
- MCP operations: 8-15 seconds per tool, 95% completion within timeouts (SC-007)
- Ingest: 90% documents successfully processed even with page timeouts or metadata mismatches (SC-010)
- Validation: ≤5 seconds for all configuration checks (SC-009)

**Constraints**:
- Deterministic chunk IDs required for idempotency (FR-008)
- Embedding model consistency enforced (write-guard, FR-011)
- Project filtering mandatory in all retrieval operations (server-side, FR-014)
- Top-k capped at 6 by default (configurable, FR-015)
- Chunk text trimmed to max 1,800 characters (FR-015)
- Tokenizer family must match embedding model family (validated, FR-007)
- Quality filter: minimum 50 tokens, signal-to-noise ratio ≥ 0.3 (FR-009)
- OCR defaults: ['en', 'de'] or Zotero metadata language field when available (FR-004)
- Environment variable precedence: system env overrides `.env` file (FR-031)

**Scale/Scope**:
- Single-user local system
- Projects: No explicit limit (user-controlled)
- Documents per project: Large documents (1000+ pages) supported with on-disk storage
- Chunks per project: Tested up to 10,000 chunks per project, supports larger with on-disk optimizations
- No automatic deletion; manual lifecycle management

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Clean Architecture Compliance
- ✅ Domain layer pure (no I/O, no frameworks)
- ✅ Application layer orchestrates domain via ports/protocols
- ✅ Infrastructure adapters implement ports (Docling, Qdrant, FastMCP)
- ✅ Dependency direction: Infrastructure → Application → Domain (inward only)

### Toolchain Compliance
- ✅ Python 3.12.x via pyenv (`.python-version` present)
- ✅ uv for package/env management (no `pip install` allowed)
- ✅ Ruff for linting/formatting
- ✅ mypy with strict typing in `src/domain`
- ✅ pytest for testing
- ✅ python-dotenv added via `uv add python-dotenv` for environment variable management

### Testing Requirements
- ✅ Domain unit tests (pure, isolated)
- ✅ Application tests with doubles for ports
- ✅ Infrastructure integration tests (Docling conversion, Qdrant operations, FastMCP tools)
- ✅ Architecture tests (dependency direction)
- ✅ Coverage: Domain ≥90% (prefer 100%), Overall ≥80%

### Observability
- ✅ Structured logging with correlation ID per ingest run
- ✅ Audit JSONL logs per ingest operation (added/updated/skipped counts, duration, model IDs)
- ✅ Minimal logging (no PII, no API keys in logs)
- ✅ Diagnostic logging for timeout/page failures with page numbers

### Security Posture
- ✅ Single-user local system (no auth required for CLI)
- ✅ Optional authentication for MCP tools
- ✅ No secrets in logs or committed files
- ✅ Environment variables for sensitive config (`.env` file with `.gitignore`, OPENAI_API_KEY, QDRANT_API_KEY)
- ✅ Environment variable precedence: system env overrides `.env` file

### Performance & Hybrid Retrieval
- ✅ Query-time hybrid retrieval (named vectors with RRF fusion, not ingest-time sparse)
- ✅ Full-text index on `chunk_text` payload field
- ✅ Score fusion: 0.3 * text_score + 0.7 * vector_score (or Qdrant RRF when using model binding)
- ✅ On-disk vectors/HNSW for large projects (memory optimization)

**Gate Status**: ✅ PASS — All constitution requirements met. Ready for Phase 0 research.

## Project Structure

### Documentation (this feature)

```text
specs/003-framework-implementation/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

**Structure Decision**: Single Python package following Clean Architecture (domain/application/infrastructure layers)

```text
src/
├── domain/              # Entities, Value Objects, Domain Services, Errors
│   ├── models/
│   ├── policy/
│   └── errors.py
├── application/         # Use cases, Ports (Protocols), DTOs
│   ├── use_cases/
│   ├── ports/
│   └── dto/
└── infrastructure/      # Adapters, frameworks, delivery mechanisms
    ├── adapters/        # Docling, Qdrant, FastEmbed, Zotero
    ├── cli/             # Typer CLI commands
    ├── mcp/             # FastMCP server and tools
    └── config/          # Settings, environment loading

tests/
├── architecture/        # Dependency direction tests
├── integration/         # Adapter tests (Docling, Qdrant, MCP)
└── unit/               # Domain and application tests

fastmcp.json            # FastMCP server configuration
citeloom.toml           # Project configuration (no secrets)
.env                    # Environment variables (gitignored)
```

## Complexity Tracking

> **No violations identified** — Implementation follows Clean Architecture principles with appropriate separation of concerns.
