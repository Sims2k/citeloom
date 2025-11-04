# Quickstart: Fix Zotero & Docling Performance and Correctness Issues

**Feature**: 006-fix-zotero-docling  
**Status**: Implementation Guide

---

## Overview

This quickstart guide provides step-by-step instructions for implementing fixes to Zotero integration and Docling document conversion, focusing on performance improvements and correctness fixes.

---

## Prerequisites

- Python 3.12.x environment active
- Dependencies synced (`uv sync`)
- Existing test suite passes
- Rich progress reporter available
- Docling converter factory implemented

---

## Implementation Steps

### Phase 1: Setup Verification

1. Verify Python 3.12.x environment
2. Sync dependencies (`uv sync`)
3. Run existing test suite (`uv run pytest -q`)

**Checkpoint**: Project ready for feature implementation

---

### Phase 2: Foundational

1. Create `get_converter()` factory function with module-level cache
2. Verify `RichProgressReporterAdapter` exists and is functional

**Checkpoint**: Foundation ready - user story implementation can begin

---

### Phase 3: User Story 1 - Fast Zotero Browsing

**Goal**: Reduce API calls by 50%+, browse 10 items in <10 seconds

**Steps**:
1. Add `collection_cache` parameter to `get_collection_info()` and `get_item_metadata()`
2. Implement cache lookup logic in adapter methods
3. Create command-scoped caches in `browse_collection()` CLI command
4. Pass caches to adapter methods
5. Reuse cached data when displaying items

**Verification**:
```bash
# Measure API calls and time
time citeloom zotero browse-collection "Collection Name" --limit 10
# Should complete in <10 seconds with 50%+ fewer API calls
```

**Checkpoint**: Browsing 10 items completes in <10 seconds

---

### Phase 4: User Story 2 - Accurate Conversion/Chunking

**Goal**: 20-page documents produce 15-40 chunks with accurate page mapping

**Steps**:
1. Fix `_extract_page_map()` to extract all pages (not just page 1)
2. Fix `_extract_heading_tree()` to extract heading hierarchy
3. Improve chunking quality filtering (not filtering all chunks)
4. Add diagnostic logging for extraction failures
5. Validate chunk ID uniqueness

**Verification**:
```bash
# Ingest a 20-page document
uv run citeloom ingest run --project test/docling ./assets/raw/large-document.pdf

# Verify chunks created
uv run citeloom inspect collection --project test/docling
# Should show 15-40 chunks, not 1
```

**Checkpoint**: 20-page document produces 15-40 chunks with accurate page mapping

---

### Phase 5: User Story 3 - Progress Feedback

**Goal**: Progress visible within 5 seconds for operations >5 seconds

**Steps**:
1. Integrate `RichProgressReporterAdapter` into converter
2. Add progress indication to `browse_collection()` for long operations
3. Implement progress update throttling (max once per second)
4. Add progress stages to `IngestDocument` use case

**Verification**:
- Run long operation and verify progress appears within 5 seconds
- Verify non-interactive mode uses structured logging

**Checkpoint**: Progress indication visible for long operations

---

### Phase 6: User Story 4 - Resource Sharing

**Goal**: Second command reuses converter, eliminating 2-3s overhead

**Steps**:
1. Implement module-level `_converter_cache` dictionary
2. Implement `get_converter()` factory function
3. Update CLI commands to use factory
4. Verify process-scoped lifetime

**Verification**:
```bash
# First command (has initialization overhead)
time uv run citeloom ingest run --project test/docling ./doc1.pdf

# Second command (should reuse converter)
time uv run citeloom ingest run --project test/docling ./doc2.pdf
# Should start immediately without 2-3s delay
```

**Checkpoint**: Second command reuses converter instance

---

### Phase 7: User Story 5 - Automatic Model Binding

**Goal**: Queries work immediately after ingestion

**Steps**:
1. Store model ID in collection payload during ingestion
2. Retrieve model ID from collection during query
3. Validate model match with clear error messages
4. Add actionable guidance in error messages

**Verification**:
```bash
# Ingest document
uv run citeloom ingest run --project test/docling ./doc.pdf

# Query immediately (should work)
uv run citeloom query run --project test/docling --query "test"
# Should succeed without manual model binding
```

**Checkpoint**: Queries succeed immediately after ingestion

---

### Phase 8: User Story 6 - HTTP Logging

**Goal**: Clean INFO logs, HTTP details at DEBUG level

**Steps**:
1. Move HTTP request logs from INFO to DEBUG level
2. Configure HTTP client logging
3. Add API call summary logging at INFO level
4. Verify important information remains at INFO

**Verification**:
```bash
# Default logging (INFO level)
uv run citeloom zotero list-collections
# Should show operations without HTTP details

# Verbose logging (DEBUG level)
uv run citeloom --verbose zotero list-collections
# Should show HTTP request/response details
```

**Checkpoint**: Clean logs at INFO, HTTP at DEBUG

---

### Phase 9: User Story 7 - Windows Profile Detection

**Goal**: Profile detection works or provides clear guidance

**Steps**:
1. Add Windows profile path checks (`%APPDATA%`, `%LOCALAPPDATA%`, `%USERPROFILE%\Documents`)
2. Improve error messages with configuration instructions
3. Update setup guide with Windows-specific examples

**Verification**:
- Test on Windows with Zotero installed
- Verify profile detection or clear error messages
- Test configuration instructions

**Checkpoint**: Windows profile detection improved

---

## Testing

### Performance Tests

```bash
# Zotero browsing performance
time citeloom zotero browse-collection "Collection" --limit 10
# Target: <10 seconds

# Document conversion accuracy
uv run citeloom ingest run --project test/docling ./large-doc.pdf
uv run citeloom inspect collection --project test/docling
# Target: 15-40 chunks for 20+ pages
```

### Correctness Tests

```bash
# Run integration tests
uv run pytest tests/integration/test_zotero_browsing_performance.py
uv run pytest tests/integration/test_docling_chunking.py
uv run pytest tests/integration/test_docling_page_extraction.py
```

---

## Validation

After implementation, verify:
- ✅ Zotero browsing <10s for 10 items
- ✅ 20-page docs produce 15-40 chunks
- ✅ Progress visible within 5s
- ✅ Second command reuses converter
- ✅ Queries work immediately after ingestion
- ✅ Clean INFO logs
- ✅ Windows profile detection works

---

## Notes

- All fixes maintain backward compatibility
- No breaking changes to existing APIs
- Performance improvements are transparent to users
- Correctness fixes improve accuracy without changing interfaces
