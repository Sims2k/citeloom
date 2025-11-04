# Implementation Plan: Fix Zotero & Docling Performance and Correctness Issues

**Branch**: `006-fix-zotero-docling` | **Date**: 2025-01-27 | **Spec**: `specs/006-fix-zotero-docling/spec.md`
**Input**: Feature specification from `/specs/006-fix-zotero-docling/spec.md`

## Summary

Fix critical performance and correctness issues in Zotero integration and Docling document conversion. Key fixes include: command-scoped caching to reduce Zotero API calls by 50%+ (browsing 10 items in <10 seconds), accurate page and heading extraction ensuring multi-page documents produce multiple chunks (15-40 for 20+ pages), progress feedback for long-running operations, resource sharing (converter reuse), automatic model binding, improved HTTP logging, and enhanced Windows profile detection.

**Technical Approach**: 
- Add command-scoped caching to ZoteroImporterAdapter for collection and item metadata
- Fix page and heading extraction bugs in DoclingConverterAdapter
- Improve chunking logic to produce multiple chunks for large documents
- Integrate RichProgressReporterAdapter for user feedback
- Implement module-level converter cache for resource sharing
- Add automatic model binding to Qdrant collections
- Adjust logging levels to reduce HTTP verbosity
- Enhance Windows Zotero profile detection

## Technical Context

**Language/Version**: Python 3.12.x via pyenv (as per constitution)  
**Primary Dependencies**: 
- Existing: Docling, Qdrant client, FastEmbed, Typer, Rich, Pydantic, pyzotero
- Rich for progress reporting (already included)
- Python stdlib: `concurrent.futures` for cross-platform timeouts

**Storage**: 
- Qdrant vector database (existing, per-project collections with payload)
- Local filesystem (caches are in-memory, process-scoped)
- No new storage systems required

**Testing**: pytest (as per constitution)
- Unit tests: Caching logic, page/heading extraction, chunking quality filtering
- Integration tests: End-to-end browsing performance, document conversion accuracy, chunking correctness
- Architecture tests: Dependency direction validation

**Target Platform**: Cross-platform (Windows, macOS, Linux)
- Cross-platform timeout enforcement using ThreadPoolExecutor
- Windows-specific profile detection improvements
- All fixes work across all platforms

**Project Type**: Single project (Python application with CLI and MCP server)

**Performance Goals**:
- Zotero browsing: <10 seconds for 10 items (50%+ API call reduction)
- Document conversion: Accurate page extraction (all pages, not just page 1)
- Chunking: 15-40 chunks for 20+ page documents
- Resource reuse: 2-3s overhead eliminated on subsequent commands

## Implementation Strategy

### MVP First (User Stories 1 & 2 - P1 Priority)

1. **Phase 1**: Setup verification
2. **Phase 2**: Foundational (converter factory, progress reporter)
3. **Phase 3**: User Story 1 (Fast Zotero Browsing) - Command-scoped caching
4. **Phase 4**: User Story 2 (Accurate Conversion/Chunking) - Page/heading extraction fixes
5. **STOP and VALIDATE**: Test both stories independently

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 (P1) → Test independently → Deploy/Demo
3. Add User Story 2 (P1) → Test independently → Deploy/Demo
4. Add User Story 3 (P2) → Progress feedback
5. Add User Story 4 (P2) → Resource sharing
6. Add User Story 5 (P2) → Automatic model binding
7. Add User Stories 6 & 7 (P3) → Logging and Windows improvements
8. Cross-platform timeout and additional fixes

## Risk Assessment

**Low Risk**:
- Command-scoped caching (isolated, no cross-process issues)
- Progress reporting (non-blocking, optional)
- Logging improvements (non-breaking)

**Medium Risk**:
- Page/heading extraction fixes (requires careful testing)
- Chunking quality filtering (may affect chunk counts)
- Cross-platform timeout (Windows compatibility)

**Mitigation**:
- Comprehensive integration tests for correctness fixes
- Performance benchmarks for caching improvements
- Fallback strategies for extraction failures

## Success Metrics

1. **Performance**: Zotero browsing <10s for 10 items (from 35+s)
2. **API Calls**: 50%+ reduction in API calls
3. **Correctness**: 20-page docs produce 15-40 chunks (not 1)
4. **Progress**: Visible within 5s for operations >5s
5. **Resource Reuse**: 2-3s overhead eliminated
6. **Model Binding**: Queries work immediately after ingestion
7. **Logging**: Clean INFO logs, HTTP at DEBUG
8. **Windows**: Profile detection works or clear guidance
