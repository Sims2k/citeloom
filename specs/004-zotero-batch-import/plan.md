# Implementation Plan: Zotero Collection Import with Batch Processing & Progress Indication

**Branch**: `004-zotero-batch-import` | **Date**: 2025-01-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-zotero-batch-import/spec.md`

## Summary

This feature implements Zotero collection import with batch processing, progress indication, and checkpointing/resumability. It enables importing documents from Zotero collections/subfolders into CiteLoom projects with visual progress feedback, automatic batching for large collections, and ability to resume interrupted imports. Includes collection browsing, tag-based filtering, and follows framework-specific best practices for Pyzotero rate limiting, Qdrant batch upserts, Docling sequential processing, and Rich progress bars.

**Technical approach**: Build on existing Zotero metadata resolution (ZoteroPyzoteroResolver) by adding collection browsing and import capabilities. Create new `ZoteroImporter` adapter for fetching collections, items, and attachments via pyzotero. Implement two-phase import (download then process) with download manifests and checkpoint files. Add Rich progress bars for multi-level progress indication. Implement checkpoint manager for resumable batch processing. Add CLI commands for Zotero browsing (`citeloom zotero list-collections`, `browse-collection`, etc.) and enhanced ingest command with `--zotero-collection`, `--resume`, `--zotero-tags`, `--exclude-tags` flags.

## Technical Context

**Language/Version**: Python 3.12.x (pinned in `.python-version`, managed via pyenv)

**Primary Dependencies**:
- pyzotero (Python client for Zotero API - remote via library_id/library_type/api_key, or local via local=True) - already installed
- Rich (terminal formatting, progress bars) - already installed
- Typer (CLI framework) - already installed
- Pydantic (data validation, settings) - already installed
- Python stdlib: json, pathlib, datetime, tempfile, contextvars (for correlation IDs)

**Storage**:
- Qdrant (per-project collections with existing batch upsert patterns - 100-500 points per batch)
- Local filesystem:
  - Checkpoint files: `var/checkpoints/{correlation_id}.json` (JSON format, correlation ID-based naming)
  - Download manifests: `var/zotero_downloads/{collection_key}/manifest.json` (JSON format)
  - Downloaded attachments: `var/zotero_downloads/{collection_key}/` (persistent storage)
  - Audit logs: `var/audit/` (existing JSONL format)
- Zotero library (accessed via pyzotero API - remote or local)
- Better BibTeX JSON-RPC API (port 23119 for Zotero, 24119 for Juris-M) for citekey extraction (existing)

**Testing**:
- pytest (unit, integration, architecture tests) - existing
- pytest-cov (coverage reporting) - existing
- Domain layer: ≥90% coverage (prefer 100%)
- Overall: ≥80% coverage target

**Target Platform**:
- Local development (macOS, Linux, Windows)
- Single-user local system (no multi-tenant requirements)
- Interactive terminal for Rich progress bars (TTY required for optimal display)
- Non-interactive mode fallback (log progress updates instead of visual bars)

**Project Type**: Single Python package with CLI entrypoint (extends existing structure)

**Performance Goals**:
- Zotero collection import: <5 minutes per 50 documents (download, conversion, chunking, embedding, storage) (SC-001)
- Progress indication: Accurate time estimates within 20% of actual completion time for 10+ documents (SC-003)
- Zotero browsing: <2 seconds for collections with up to 100 items (SC-005)
- Batch operations: 100+ documents complete without memory exhaustion using batched patterns (SC-010)
- Resume operations: 100% success rate skipping completed documents with valid checkpoint file (SC-002)

**Constraints**:
- Zotero web API rate limits: 0.5s minimum interval between requests, 2 requests per second maximum (FR-007)
- File download batches: 10-20 files per batch (FR-008)
- Qdrant batch upserts: 100-500 points per batch (FR-009)
- Docling conversion: Sequential processing (1 document at a time) due to CPU/memory intensity (FR-023)
- Document conversion timeouts: 120s per document, 10s per page (FR-024, existing)
- Checkpoint files: JSON format, correlation ID-based naming (`var/checkpoints/{correlation_id}.json`) (FR-029)
- Checkpoint atomic writes: Write to temp file, then atomic rename (FR-021)
- Progress indication: Requires interactive terminal (Rich library requires TTY) (Constraint from constitution)
- Tag filtering: Case-insensitive partial matching (substring matching) (FR-030)
- Multiple PDF attachments: Process all as separate documents with same metadata (FR-028)

**Scale/Scope**:
- Single-user local system
- Collections: Support recursive subcollections
- Documents per batch: No explicit limit (tested with 100+ documents, supports larger)
- Checkpoint files: One per import run (correlation ID-based)
- Download manifests: One per collection import
- No automatic cleanup of checkpoints/manifests (user-controlled via CLI flags, default: retain)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Clean Architecture Compliance
- ✅ Domain layer pure (checkpoint, download manifest entities - no I/O, no frameworks)
- ✅ Application layer orchestrates domain via ports/protocols (new use case: `BatchImportFromZotero`)
- ✅ Infrastructure adapters implement ports:
  - New: `ZoteroImporter` adapter (implements collection/item/attachment fetching)
  - Existing: `ZoteroPyzoteroResolver` (metadata resolution - already compliant)
  - New: `CheckpointManager` (checkpoint file I/O in infrastructure layer)
  - Enhanced: CLI commands with Rich progress bars (infrastructure presentation layer)
- ✅ Dependency direction: Infrastructure → Application → Domain (inward only)

### Toolchain Compliance
- ✅ Python 3.12.x via pyenv (`.python-version` present)
- ✅ uv for package/env management (no `pip install` allowed)
- ✅ Ruff for linting/formatting
- ✅ mypy with strict typing in `src/domain`
- ✅ pytest for testing
- ✅ Rich already in dependencies (no new dependencies needed)

### Testing Requirements
- ✅ Domain unit tests (checkpoint entities, download manifest entities - pure, isolated)
- ✅ Application tests with doubles for ports (ZoteroImporter port, CheckpointManager port)
- ✅ Infrastructure integration tests (pyzotero collection browsing, file downloads, checkpoint I/O, progress bars)
- ✅ Architecture tests (dependency direction)
- ✅ Coverage: Domain ≥90% (prefer 100%), Overall ≥80%

### Observability
- ✅ Structured logging with correlation ID per ingest run (existing, enhanced for batch operations)
- ✅ Audit JSONL logs per ingest operation (existing, enhanced with batch statistics)
- ✅ Progress indication: Multi-level Rich progress bars (overall batch, per-document stages) with time estimates
- ✅ Minimal logging (no PII, no API keys in logs)
- ✅ Checkpoint files: Human-readable JSON format for debugging and manual inspection

### Security Posture
- ✅ Single-user local system (no auth required for CLI)
- ✅ Optional authentication for MCP tools (existing)
- ✅ No secrets in logs or committed files
- ✅ Environment variables for Zotero config (ZOTERO_LIBRARY_ID, ZOTERO_API_KEY, etc.) - already supported
- ✅ Checkpoint files: Correlation ID-based naming (traceability, not security-sensitive)

### Batch Processing & Checkpointing Patterns
- ✅ Two-phase import: Download all attachments first, then process (enables retry without re-download)
- ✅ Checkpoint files: JSON format, correlation ID-based naming, atomic writes
- ✅ Resume capability: `--resume` flag loads checkpoint, skips completed documents
- ✅ Batch size limits: 10-20 files per download batch, 100-500 points per Qdrant upsert
- ✅ Progress indication: Multi-level Rich progress bars (overall batch, per-document stages)

### Zotero Integration Patterns
- ✅ pyzotero API access: Support both remote (library_id/api_key) and local (local=True) with automatic fallback
- ✅ Rate limiting: 0.5s minimum interval for web API, 2 requests per second maximum
- ✅ Collection browsing: List collections, browse items, list tags, get recent items (generator/iterator patterns)
- ✅ Tag-based filtering: Case-insensitive partial matching, applied before downloads
- ✅ Download manifests: Persistent storage for two-phase import workflow

**Gate Status**: ✅ PASS — All constitution requirements met. Ready for Phase 0 research.

## Project Structure

### Documentation (this feature)

```text
specs/004-zotero-batch-import/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

**Structure Decision**: Extends existing single Python package following Clean Architecture (domain/application/infrastructure layers)

```text
src/
├── domain/              # Entities, Value Objects, Domain Services, Errors
│   ├── models/
│   │   ├── chunk.py     # Existing
│   │   ├── conversion_result.py  # Existing
│   │   └── checkpoint.py        # NEW: Checkpoint entities (IngestionCheckpoint, DocumentCheckpoint)
│   ├── policy/
│   └── errors.py        # Existing
├── application/         # Use cases, Ports (Protocols), DTOs
│   ├── use_cases/
│   │   ├── ingest_document.py   # Existing (enhanced with progress callbacks)
│   │   └── batch_import_from_zotero.py  # NEW: Orchestrates batch import workflow
│   ├── ports/
│   │   ├── zotero_metadata.py   # Existing (ZoteroPyzoteroResolver)
│   │   └── zotero_importer.py    # NEW: ZoteroImporterPort protocol
│   └── dto/
├── infrastructure/      # Adapters, frameworks, delivery mechanisms
│   ├── adapters/
│   │   ├── zotero_metadata.py   # Existing (ZoteroPyzoteroResolver)
│   │   ├── zotero_importer.py    # NEW: ZoteroImporter adapter (pyzotero collection/item/attachment fetching)
│   │   ├── checkpoint_manager.py # NEW: CheckpointManager for checkpoint file I/O
│   │   └── [existing adapters...]
│   ├── cli/
│   │   ├── commands/
│   │   │   ├── ingest.py         # Enhanced with --zotero-collection, --resume, --zotero-tags, --exclude-tags, --keep-checkpoints, --cleanup-checkpoints
│   │   │   └── zotero.py         # NEW: Zotero browsing commands (list-collections, browse-collection, list-tags, recent-items)
│   │   └── app.py                # Register new commands
│   ├── mcp/
│   │   └── tools.py               # Enhanced: Replace NOT_IMPLEMENTED for Zotero import in ingest_from_source
│   └── config/

tests/
├── architecture/        # Dependency direction tests
├── integration/
│   └── test_zotero_importer.py   # NEW: Test pyzotero collection browsing, item fetching, file downloads
│   └── test_checkpoint_manager.py # NEW: Test checkpoint I/O, resume logic
│   └── test_progress_indication.py # NEW: Test Rich progress bars
└── unit/
    └── test_checkpoint_models.py  # NEW: Test checkpoint domain models
```

## Complexity Tracking

> **No violations identified** — Implementation extends existing Clean Architecture structure with new adapters and use cases following established patterns.
