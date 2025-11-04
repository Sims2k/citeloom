# Research: Fix Zotero & Docling Performance and Correctness Issues

**Date**: 2025-01-27  
**Feature**: 006-fix-zotero-docling  
**Status**: Complete  

---

## Research Summary

This research investigates performance bottlenecks and correctness issues in Zotero integration and Docling document conversion, focusing on API call optimization, page/heading extraction accuracy, chunking quality, and cross-platform compatibility.

**Key Research Areas**:
1. Zotero API call patterns and caching strategies
2. Docling page and heading extraction mechanisms
3. Chunking quality filtering and token counting
4. Cross-platform timeout enforcement
5. Resource sharing and process-scoped caching
6. Progress reporting patterns
7. Model binding and collection metadata

---

## 1. Zotero API Call Optimization

### Decision: Command-Scoped Caching

**Rationale**: 
- Zotero API calls are slow (network latency, rate limits)
- Collection info and item metadata are relatively static within a command
- Command-scoped cache avoids stale data issues
- Memory cleanup after command completes prevents bloat

**Implementation Pattern**:
```python
# Command-scoped cache (cleared after command)
collection_cache: dict[str, dict[str, Any]] = {}
item_cache: dict[str, dict[str, Any]] = {}

# Cache lookup before API call
if item_key in item_cache:
    return item_cache[item_key]

# API call only if cache miss
metadata = zotero_importer.get_item_metadata(item_key, collection_cache=collection_cache)
item_cache[item_key] = metadata
```

**Key Points**:
- Cache is command-scoped (not global)
- Cache cleared after command completes
- Cache passed as parameter to adapter methods
- Reduces redundant API calls by 50%+

---

## 2. Docling Page Extraction

### Decision: Fix Page Map Extraction from Document Structure

**Rationale**: 
- Current implementation extracts only page 1 for multi-page documents
- Docling provides page boundaries in document structure
- Need to extract all pages for accurate chunking

**Implementation Pattern**:
```python
def _extract_page_map(self, doc: Document) -> dict[int, tuple[int, int]]:
    """Extract page boundaries from Docling Document."""
    page_map: dict[int, tuple[int, int]] = {}
    
    # Extract from document structure
    for page_num, page_content in enumerate(doc.pages, start=1):
        # Calculate text offsets
        start_offset = previous_end_offset
        end_offset = start_offset + len(page_content.text)
        page_map[page_num] = (start_offset, end_offset)
    
    return page_map
```

**Key Points**:
- Extract all pages from document structure
- Build accurate page map with text offsets
- Handle extraction failures gracefully
- Log diagnostic information on failure

---

## 3. Heading Tree Extraction

### Decision: Extract Hierarchical Heading Structure

**Rationale**: 
- Headings provide important context for chunks
- Docling extracts heading hierarchy
- Need to preserve heading paths in chunk metadata

**Implementation Pattern**:
```python
def _extract_heading_tree(self, doc: Document) -> dict[str, Any]:
    """Extract heading hierarchy from Docling Document."""
    heading_tree = {}
    
    # Extract from document structure
    for heading in doc.headings:
        # Build hierarchical structure
        heading_path = build_heading_path(heading)
        heading_tree[heading_path] = {
            "level": heading.level,
            "text": heading.text,
            "page": heading.page_number,
        }
    
    return heading_tree
```

**Key Points**:
- Extract all headings with hierarchy
- Preserve heading context in chunks
- Handle extraction failures gracefully
- Log diagnostic information on failure

---

## 4. Chunking Quality Filtering

### Decision: Fix Quality Filtering to Produce Multiple Chunks

**Rationale**: 
- Current implementation filters too aggressively
- Large documents should produce multiple chunks
- Quality thresholds need adjustment

**Implementation Pattern**:
```python
# Quality filtering thresholds
MIN_CHUNK_LENGTH = 50  # tokens (not too high)
MIN_SIGNAL_TO_NOISE = 0.3  # reasonable threshold

# Filter chunks
valid_chunks = [
    chunk for chunk in chunks
    if chunk.token_count >= MIN_CHUNK_LENGTH
    and chunk.signal_to_noise >= MIN_SIGNAL_TO_NOISE
]

# Log filtering decisions
if len(valid_chunks) < len(chunks):
    logger.debug(f"Filtered {len(chunks) - len(valid_chunks)} chunks")
```

**Key Points**:
- Adjust thresholds to avoid over-filtering
- Log filtering decisions for debugging
- Ensure reasonable chunk counts (15-40 for 20+ pages)
- Validate chunk ID uniqueness

---

## 5. Cross-Platform Timeout Enforcement

### Decision: Use ThreadPoolExecutor for Cross-Platform Timeouts

**Rationale**: 
- `signal.SIGALRM` only works on Unix (not Windows)
- ThreadPoolExecutor works cross-platform
- Provides timeout without platform-specific code

**Implementation Pattern**:
```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError

def _convert_with_timeout(self, source_path: str) -> dict[str, Any]:
    """Convert document with timeout protection."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(self._perform_conversion, source_path)
        try:
            result = future.result(timeout=self.DOCUMENT_TIMEOUT_SECONDS)
            return result
        except TimeoutError:
            raise TimeoutError(f"Document conversion exceeded {self.DOCUMENT_TIMEOUT_SECONDS}s timeout")
```

**Key Points**:
- Works on Windows, macOS, Linux
- No platform-specific code required
- Timeout applies to entire conversion
- Per-page timeout also supported

---

## 6. Resource Sharing (Process-Scoped Caching)

### Decision: Module-Level Converter Cache

**Rationale**: 
- Converter initialization is expensive (2-3 seconds)
- Same process can reuse converter instance
- Process-scoped cache (not cross-process)

**Implementation Pattern**:
```python
# Module-level cache
_converter_cache: dict[str, DoclingConverterAdapter] = {}

def get_converter() -> DoclingConverterAdapter:
    """Get converter instance (cached per process)."""
    cache_key = "default"
    if cache_key not in _converter_cache:
        _converter_cache[cache_key] = DoclingConverterAdapter()
    return _converter_cache[cache_key]
```

**Key Points**:
- Process-scoped (module-level)
- Single instance per process
- No inactivity-based cleanup
- Cache persists for process lifetime

---

## 7. Progress Reporting

### Decision: Rich Progress Bars with Non-Interactive Fallback

**Rationale**: 
- Users need feedback for long operations
- Rich provides excellent progress bars
- Non-interactive mode detection for CI/automation

**Implementation Pattern**:
```python
# Check if interactive
if sys.stdout.isatty():
    # Use Rich progress bars
    progress_reporter = RichProgressReporterAdapter()
else:
    # Use structured logging
    logger.info("Processing document 1/10...")
```

**Key Points**:
- Automatic interactive mode detection
- Progress visible within 5 seconds
- Throttled updates (max once per second)
- Non-interactive uses structured logging

---

## 8. Automatic Model Binding

### Decision: Store Model ID in Collection Payload

**Rationale**: 
- Users shouldn't need manual model binding
- Model ID used for ingestion should be stored
- Query can retrieve model ID from collection payload

**Implementation Pattern**:
```python
# During ingestion
collection_payload = {
    "embedding_model": model_id,
    # ... other metadata
}
index.upsert(chunks, project_id=project_id, model_id=model_id)

# During query
collection_info = index.get_collection_info(project_id)
stored_model_id = collection_info.get("embedding_model")

if stored_model_id != query_model_id:
    raise EmbeddingModelMismatch(...)
```

**Key Points**:
- Model ID stored in collection payload
- Automatic binding on first query
- Clear error messages on mismatch
- Actionable guidance for resolution

---

## References

- Docling documentation for page/heading extraction
- Rich documentation for progress reporting
- Python concurrent.futures for cross-platform timeouts
- Qdrant payload documentation for model binding
