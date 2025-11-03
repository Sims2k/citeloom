# Implementation Plan: Comprehensive Zotero Integration Improvements

**Branch**: `005-zotero-improvements` | **Date**: 2025-01-27 | **Spec**: `specs/005-zotero-improvements/spec.md`
**Input**: Feature specification from `/specs/005-zotero-improvements/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement comprehensive Zotero integration improvements following patterns from zotero-mcp, enhancing performance, offline capability, and retrieval quality. Key improvements include: local SQLite database access for offline browsing and instant collection access, full-text reuse from Zotero to avoid redundant OCR processing (50-80% speedup), PDF annotation extraction and indexing as separate vector points, embedding model governance with friendly diagnostics, incremental deduplication based on content hashes, enhanced library browsing tools (offline-capable), flexible source router for local/web source selection, and payload enrichment with Zotero keys for targeted queries. All improvements maintain backward compatibility with existing Web API workflows.

**Technical Approach**: 
- Extend existing `ZoteroImporterPort` interface with new `LocalZoteroDbAdapter` implementing SQLite read-only access
- Add application service `ZoteroSourceRouter` for intelligent source selection
- Create infrastructure adapters: `FulltextResolver`, `AnnotationResolver` for text and annotation extraction
- Enhance domain models with `ContentFingerprint` for deduplication
- Extend download manifest with source markers and fingerprints
- Follow zotero-mcp patterns for SQLite immutable read-only access and annotation handling

## Technical Context

**Language/Version**: Python 3.12.x via pyenv (as per constitution)  
**Primary Dependencies**: 
- SQLite3 (stdlib, no external dependency)
- pyzotero (existing, for Web API and annotation extraction)
- Existing: Docling, Qdrant client, FastEmbed, Typer, Rich, Pydantic
- Platform detection: Python stdlib `platform` module
- JSON parsing: Python stdlib `json` and SQLite JSON1 extension
- Content hashing: Python stdlib `hashlib` module

**Storage**: 
- Zotero SQLite database (read-only via immutable mode)
- Qdrant vector database (existing, per-project collections)
- Local filesystem (download manifests, audit logs, checkpoints)
- No new storage systems required

**Testing**: pytest (as per constitution)
- Unit tests: Domain models (ContentFingerprint), adapters (LocalZoteroDbAdapter, FulltextResolver, AnnotationResolver)
- Application tests: Source router logic with doubles for ports
- Integration tests: End-to-end import with local DB, full-text reuse, annotation indexing, deduplication
- Architecture tests: Dependency direction validation

**Target Platform**: Cross-platform (Windows, macOS, Linux)
- Platform-aware profile detection required
- SQLite immutable read-only mode works across all platforms
- Local database access requires Zotero desktop installation

**Project Type**: Single project (Python application with CLI and MCP server)

**Performance Goals**:
- Collection browsing: < 2 seconds using local DB (SC-001)
- Import speedup: 50-80% for collections with 70%+ Zotero fulltext (SC-002)
- Annotation indexing: < 20% overhead on total import time (SC-003)
- Re-import unchanged collections: < 30 seconds (manifest validation only) (SC-004)
- Source router fallback success: 95% when primary source fails (SC-005)
- Query by Zotero keys: < 500ms for collections up to 10,000 chunks (SC-006)

**Constraints**:
- Must work with Zotero desktop application running concurrently (immutable read-only mode)
- Must maintain backward compatibility with existing Web API workflows
- SQLite 3.8.0+ required for immutable read-only mode (widely available)
- Platform-specific profile paths must be correctly detected (Windows/macOS/Linux)
- Content hashing must balance accuracy vs performance (1MB preview + metadata)
- Full-text reuse only skips conversion/OCR step - chunking, embedding, indexing still required

**Scale/Scope**:
- Handles large libraries (100+ documents)
- Collections up to 10,000 chunks (query performance target)
- Multiple Zotero profiles (detect default or allow override)
- Mixed document types (PDFs, images, Office documents)
- Annotations: average 5 per document, 100+ documents per collection

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Clean Architecture Dependency Rule
- ✅ **Domain layer**: New domain models (`ContentFingerprint`) are pure, no I/O, deterministic
- ✅ **Application layer**: New use case services (`ZoteroSourceRouter`) depend only on domain and ports
- ✅ **Infrastructure layer**: New adapters (`LocalZoteroDbAdapter`, `FulltextResolver`, `AnnotationResolver`) implement ports and translate external formats
- ✅ **No inward dependencies**: All new code follows dependency direction (infrastructure → application → domain)

### Separation of Concerns (Domain, Application, Infrastructure)
- ✅ **Domain**: `ContentFingerprint` entity (pure, no I/O), enhanced `DownloadManifestAttachment` value object
- ✅ **Application**: `ZoteroSourceRouter` service (orchestrates adapters), enhanced `batch_import_from_zotero` use case
- ✅ **Infrastructure**: `LocalZoteroDbAdapter`, `FulltextResolver`, `AnnotationResolver` implement ports

### Framework Independence
- ✅ **Domain**: No framework imports (uses only stdlib: `hashlib`, `pathlib`, `datetime`)
- ✅ **Application**: No framework imports (only domain types and port interfaces)
- ✅ **Infrastructure**: SQLite3 (stdlib), pyzotero (existing dependency), platform detection (stdlib)
- ✅ **Framework swapping**: SQLite adapter can be replaced without changing domain/application

### Stable Boundaries via Ports and DTOs
- ✅ **Extends existing ports**: `ZoteroImporterPort` interface already defined, new adapter implements same interface
- ✅ **New ports if needed**: Potential new port for full-text resolution (or integrate into existing converter port)
- ✅ **DTOs**: Enhanced `DownloadManifestAttachment` with `source` and `content_fingerprint` fields
- ✅ **Type safety**: All interfaces use typed request/response models

### Tests as Architectural Feedback
- ✅ **Unit tests**: Domain models (ContentFingerprint) in isolation
- ✅ **Application tests**: Source router with doubles for ports (no real I/O)
- ✅ **Infrastructure tests**: Adapter integration tests (local DB, fulltext, annotations)
- ✅ **Architecture tests**: Dependency direction validation (no new violations expected)

### Toolchain & Execution Policy
- ✅ **Python**: 3.12.x via pyenv (matches constitution)
- ✅ **Dependencies**: SQLite3 (stdlib, no new dependency), pyzotero (existing)
- ✅ **No new tooling**: Uses existing pytest, ruff, mypy setup

### Performance & Hybrid Retrieval
- ✅ **No changes to vector database patterns**: Existing Qdrant patterns remain unchanged
- ✅ **No changes to retrieval**: Query patterns unchanged, only ingestion improved

### Observability
- ✅ **Audit logs**: Enhanced to include fulltext source markers and annotation indexing stats
- ✅ **Structured logging**: Maintains correlation IDs and structured format
- ✅ **Error messages**: Friendly diagnostics for embedding model mismatches (FR-030, FR-031)

### Security & Privacy
- ✅ **No new secrets**: Uses existing Zotero API key configuration
- ✅ **Local DB access**: Read-only immutable mode prevents corruption (safe)
- ✅ **No PII logging**: No new sensitive data logged

### Operational Clarifications
- ✅ **CLI integration**: New browsing commands (`list-collections`, `browse-collection`, `list-tags`, `recent-items`)
- ✅ **MCP integration**: No new MCP tools required (existing tools work with enhanced adapters)
- ✅ **Backward compatibility**: Default to `web-first` strategy, existing workflows unchanged

### Zotero Integration Patterns
- ✅ **Rate limiting**: Annotation extraction follows existing retry patterns (FR-016)
- ✅ **Local/Web API**: Source router handles both, maintaining existing patterns
- ✅ **Tag filtering**: Preserved from existing implementation

**Gate Status**: ✅ PASS — All constitution requirements met. Ready for Phase 0 research.

## Project Structure

### Documentation (this feature)

```text
specs/005-zotero-improvements/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

**Structure Decision**: Extends existing single Python package following Clean Architecture (domain/application/infrastructure layers). All new code integrates into existing structure without requiring new directories.

```text
src/
├── domain/              # Entities, Value Objects, Domain Services, Errors
│   ├── models/
│   │   ├── chunk.py              # Existing
│   │   ├── conversion_result.py   # Existing
│   │   ├── citation_meta.py      # Existing
│   │   ├── download_manifest.py  # Existing - ENHANCED: Add source field, content_fingerprint
│   │   └── content_fingerprint.py # NEW: ContentFingerprint entity for deduplication
│   ├── policy/                   # Existing (no changes)
│   └── errors.py                 # Existing (no changes)
│
├── application/         # Use cases, Ports (Protocols), DTOs
│   ├── use_cases/
│   │   ├── ingest_document.py             # Existing - ENHANCED: Integrate FulltextResolver
│   │   ├── batch_import_from_zotero.py   # Existing - ENHANCED: Integrate SourceRouter, AnnotationResolver, deduplication
│   │   └── query_chunks.py                # Existing (no changes)
│   ├── ports/
│   │   ├── zotero_importer.py    # Existing - ENHANCED: May extend with additional methods (list_tags, get_recent_items)
│   │   └── converter.py          # Existing - May extend with fulltext preference option
│   ├── services/        # NEW: Application services
│   │   └── zotero_source_router.py  # NEW: ZoteroSourceRouter service for source selection
│   └── dto/             # Existing (no changes)
│
└── infrastructure/      # Adapters: controllers, presenters, gateways, frameworks/drivers
    ├── adapters/
    │   ├── zotero_importer.py        # Existing - ENHANCED: Extend or refactor to support local DB
    │   ├── zotero_local_db.py        # NEW: LocalZoteroDbAdapter (implements ZoteroImporterPort)
    │   ├── zotero_fulltext_resolver.py  # NEW: FulltextResolver (checks Zotero fulltext table)
    │   ├── zotero_annotation_resolver.py  # NEW: AnnotationResolver (fetches annotations via Web API)
    │   ├── docling_converter.py     # Existing - ENHANCED: Integrate with FulltextResolver
    │   ├── qdrant_index.py          # Existing - ENHANCED: Add zotero.item_key, zotero.attachment_key indexes
    │   └── zotero_metadata.py       # Existing (no changes)
    │
    ├── cli/
    │   ├── commands/
    │   │   ├── ingest.py      # Existing - ENHANCED: Support new Zotero options (mode, include_annotations, prefer_zotero_fulltext)
    │   │   ├── inspect.py     # Existing - ENHANCED: Add --show-embedding-model option
    │   │   └── zotero.py      # NEW: Zotero browsing commands (list-collections, browse-collection, list-tags, recent-items)
    │   └── main.py            # Existing - ENHANCED: Register new zotero commands
    │
    ├── mcp/
    │   ├── server.py    # Existing (no changes)
    │   └── tools.py     # Existing - ENHANCED: Expose embedding model in inspect responses
    │
    └── config/
        └── settings.py  # Existing - ENHANCED: Add Zotero configuration section (mode, db_path, storage_dir, include_annotations, prefer_zotero_fulltext)

tests/
├── unit/
│   ├── test_domain_models.py     # Existing - ENHANCED: Test ContentFingerprint entity
│   └── test_zotero_source_router.py  # NEW: Test source router logic with doubles
│
├── integration/
│   ├── test_zotero_local_db.py      # NEW: Test LocalZoteroDbAdapter (profile detection, SQL queries, path resolution)
│   ├── test_zotero_fulltext.py      # NEW: Test FulltextResolver (fulltext preference, fallback, mixed provenance)
│   ├── test_zotero_annotations.py   # NEW: Test AnnotationResolver (extraction, normalization, indexing)
│   ├── test_zotero_deduplication.py # NEW: Test incremental deduplication (hash matching, fingerprint comparison)
│   └── test_zotero_source_router.py # NEW: Test source router strategies (local-first, web-first, auto, fallback)
│
└── architecture/
    └── test_dependency_direction.py  # Existing - VERIFY: No new violations introduced
```

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _None_ | _All design follows constitution patterns_ | _No violations_ |

---

## Phase Completion Status

**Phase 0: Outline & Research** ✅ Complete
- Generated `research.md` with implementation patterns from zotero-mcp
- Documented SQLite immutable read-only access patterns
- Documented platform-aware profile detection
- Documented full-text quality validation
- Documented annotation extraction patterns
- Documented content hashing strategies
- Documented source routing and fallback strategies
- All NEEDS CLARIFICATION items resolved

**Phase 1: Design & Contracts** ✅ Complete
- Generated `data-model.md` with entity definitions:
  - New: `ContentFingerprint` entity
  - Enhanced: `DownloadManifestAttachment` (source, content_fingerprint)
  - Enhanced: Chunk payload (zotero.item_key, zotero.attachment_key)
  - New: Annotation point payload structure
- Generated `contracts/ports.md` with port interfaces:
  - Enhanced: `ZoteroImporterPort` (new LocalZoteroDbAdapter implementation)
  - New: `FulltextResolverPort` for full-text resolution
  - New: `AnnotationResolverPort` for annotation extraction
  - New: `ZoteroSourceRouter` application service
  - Enhanced: `VectorIndexPort` (Zotero key indexes, annotation support)
- Generated `quickstart.md` with implementation guide:
  - Step-by-step instructions for all phases
  - Testing strategies
  - Configuration examples
  - Common pitfalls and solutions
- Updated agent context: Added Python 3.12.x and project type information

**Phase 2: Tasks & Implementation Plan** ⏳ Pending
- Will be generated by `/speckit.tasks` command (not part of `/speckit.plan`)

---

## Implementation Summary

**Key Deliverables**:
1. **Local SQLite Adapter**: Read-only database access for offline browsing
2. **Source Router**: Intelligent source selection with fallback strategies
3. **Full-Text Resolver**: Zotero fulltext reuse for 50-80% speedup
4. **Annotation Resolver**: PDF annotation extraction and indexing
5. **Content Fingerprinting**: Incremental deduplication to skip unchanged documents
6. **Enhanced Payloads**: Zotero keys in chunk payloads for traceability
7. **Library Browsing**: CLI commands for offline library exploration
8. **Embedding Diagnostics**: Friendly error messages for model mismatches

**Architecture Compliance**:
- ✅ All new code follows Clean Architecture patterns
- ✅ Domain layer remains pure (no I/O)
- ✅ Application layer orchestrates via ports
- ✅ Infrastructure adapters implement ports
- ✅ No framework imports in domain/application
- ✅ Backward compatible with existing workflows

**Next Steps**:
1. Run `/speckit.tasks` to generate detailed task breakdown
2. Begin implementation with Phase 1.1 (Local SQLite Adapter)
3. Follow quickstart guide for step-by-step implementation
4. Reference research.md for implementation patterns
5. Use contracts/ports.md for interface definitions

---

**Plan Status**: ✅ Phase 0 and Phase 1 Complete - Ready for task generation
