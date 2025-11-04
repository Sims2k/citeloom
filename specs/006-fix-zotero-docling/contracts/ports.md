# Port Contracts: Fix Zotero & Docling Performance and Correctness Issues

**Date**: 2025-01-27  
**Feature**: 006-fix-zotero-docling  
**Status**: Design Complete

This document defines the port (protocol) interface enhancements for Zotero and Docling performance and correctness fixes, including caching, progress reporting, and timeout handling.

---

## 1. ZoteroImporterPort (ENHANCED)

**Purpose**: Interface for importing documents from Zotero collections. Enhanced with optional caching parameters.

**Location**: `src/application/ports/zotero_importer.py`

**Status**: Backward compatible enhancement (caching parameters are optional)

**Enhanced Methods**:

### `get_collection_info(collection_key, collection_cache=None)`

**New Parameter**: `collection_cache: dict[str, Any] | None = None`
- Optional command-scoped cache for collection metadata
- Cache lookup before API call
- Cache population after API call

**Contract**:
```python
def get_collection_info(
    self,
    collection_key: str,
    collection_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get collection information with optional caching.
    
    Args:
        collection_key: Zotero collection key
        collection_cache: Optional command-scoped cache (lookup before API call, populate after)
    
    Returns:
        Collection info dict with keys: 'key', 'name', 'parentCollection'
    
    Behavior:
        - If collection_cache provided and collection_key in cache: return cached data
        - Otherwise: make API call, populate cache if provided, return result
    """
    pass
```

### `get_item_metadata(item_key, collection_cache=None)`

**New Parameter**: `collection_cache: dict[str, Any] | None = None`
- Optional command-scoped cache for collection info lookup
- Reduces redundant collection API calls

**Contract**:
```python
def get_item_metadata(
    self,
    item_key: str,
    collection_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Get item metadata with optional collection cache.
    
    Args:
        item_key: Zotero item key
        collection_cache: Optional command-scoped cache for collection info
    
    Returns:
        Item metadata dict
    
    Behavior:
        - Uses collection_cache if provided to avoid redundant collection API calls
        - Caches collection info if not already cached
    """
    pass
```

---

## 2. TextConverterPort (ENHANCED)

**Purpose**: Interface for document conversion. Enhanced with progress reporting and timeout handling.

**Location**: `src/application/ports/converter.py`

**Status**: Backward compatible enhancement (progress_reporter is optional)

**Enhanced Method**:

### `convert(source_path, ocr_languages=None, progress_reporter=None)`

**New Parameter**: `progress_reporter: ProgressReporterPort | None = None`
- Optional progress reporter for document-level progress updates
- Non-blocking progress indication

**Contract**:
```python
def convert(
    self,
    source_path: str,
    ocr_languages: list[str] | None = None,
    progress_reporter: ProgressReporterPort | None = None,
) -> Mapping[str, Any]:
    """
    Convert document with optional progress reporting.
    
    Args:
        source_path: Path to source document
        ocr_languages: Optional OCR language codes
        progress_reporter: Optional progress reporter for document-level updates
    
    Returns:
        ConversionResult-like dict with:
        - doc_id: Document identifier
        - structure: heading_tree and page_map (all pages, not just page 1)
        - plain_text: Converted text
    
    Behavior:
        - Extracts ALL pages (not just page 1)
        - Extracts heading hierarchy accurately
        - Reports progress if progress_reporter provided
        - Applies timeout protection (120s document, 10s per-page)
    """
    pass
```

---

## 3. ChunkerPort (ENHANCED)

**Purpose**: Interface for document chunking. Enhanced with improved quality filtering.

**Location**: `src/application/ports/chunker.py`

**Status**: No interface changes (implementation improvements only)

**Contract** (unchanged):
```python
def chunk(
    self,
    conversion_result: Mapping[str, Any],
    policy: ChunkingPolicy,
) -> Sequence[Chunk]:
    """
    Chunk document with improved quality filtering.
    
    Args:
        conversion_result: ConversionResult with accurate page_map and heading_tree
        policy: Chunking policy
    
    Returns:
        List of Chunk objects (15-40 for 20+ page documents)
    
    Behavior:
        - Produces multiple chunks for large documents (not just 1)
        - Applies quality filtering correctly (not filtering all chunks)
        - Preserves heading context in chunks
        - Validates chunk ID uniqueness
        - Logs filtering decisions for debugging
    """
    pass
```

---

## 4. VectorIndexPort (ENHANCED)

**Purpose**: Interface for vector storage. Enhanced with automatic model binding.

**Location**: `src/application/ports/vector_index.py`

**Status**: Backward compatible enhancement (automatic binding transparent)

**Enhanced Method**:

### `upsert(items, project_id, model_id)`

**New Behavior**: Automatically stores model_id in collection payload

**Contract**:
```python
def upsert(
    self,
    items: list[dict[str, Any]],
    project_id: str,
    model_id: str,
) -> None:
    """
    Upsert chunks with automatic model binding.
    
    Args:
        items: List of chunk dicts
        project_id: Project identifier
        model_id: Embedding model identifier
    
    Behavior:
        - Stores model_id in collection payload automatically
        - Creates collection if not exists
        - Binds model to collection for subsequent queries
        - No manual model binding required
    """
    pass
```

### `search(query_vector, project_id, top_k, model_id=None)`

**Enhanced Behavior**: Automatic model ID retrieval from collection

**Contract**:
```python
def search(
    self,
    query_vector: list[float],
    project_id: str,
    top_k: int,
    model_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Search with automatic model binding.
    
    Args:
        query_vector: Query embedding vector
        project_id: Project identifier
        top_k: Number of results
        model_id: Optional model ID (if None, retrieved from collection)
    
    Behavior:
        - If model_id not provided: retrieve from collection payload
        - Validate model match (raise error if mismatch)
        - Provide actionable guidance in error messages
    """
    pass
```

---

## 5. ProgressReporterPort (NEW)

**Purpose**: Interface for progress reporting during long operations.

**Location**: `src/application/ports/progress_reporter.py`

**Status**: New interface (already exists in codebase)

**Key Methods**:
- `start_batch(total_documents, description)` → Batch context
- `start_document(document_index, total_documents, description)` → Document context
- `update_stage(stage, description)` → Update current stage
- `finish()` → Complete progress reporting

**Contract**: Already defined in existing codebase

---

## Notes

- All enhancements are backward compatible
- Caching parameters are optional (default None)
- Progress reporting is optional (default None)
- Automatic model binding is transparent to callers
- No breaking changes to existing interfaces


