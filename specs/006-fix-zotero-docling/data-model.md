# Data Model: Fix Zotero & Docling Performance and Correctness Issues

**Date**: 2025-01-27  
**Feature**: 006-fix-zotero-docling  
**Status**: Design Complete

---

## Overview

This document defines the data structures and models for Zotero and Docling performance and correctness fixes, including caching, page/heading extraction, chunking improvements, and resource sharing.

**Enhanced Entities**:
- `ZoteroImporterAdapter`: Added caching parameters to methods
- `DoclingConverterAdapter`: Fixed page/heading extraction, added timeout
- `DoclingChunkerAdapter`: Improved quality filtering
- `QdrantIndexAdapter`: Added automatic model binding

**New Data Structures**:
- Command-scoped caches (in-memory, temporary)
- Module-level converter cache (process-scoped)

**Related Entities** (unchanged):
- `Chunk`: No changes (uses existing structure)
- `ConversionResult`: Enhanced with accurate page_map and heading_tree
- `DownloadManifest`: No changes

---

## 1. Command-Scoped Caches

**Purpose**: Temporary in-memory caches for reducing API calls within a single CLI command.

**Location**: Created in CLI commands (e.g., `src/infrastructure/cli/commands/zotero.py`)

**Structure**:
```python
collection_cache: dict[str, dict[str, Any]] = {
    "collection_key": {
        "key": "collection_key",
        "name": "Collection Name",
        "parentCollection": "parent_key",
        # ... other collection metadata
    }
}

item_cache: dict[str, dict[str, Any]] = {
    "item_key": {
        "title": "Item Title",
        "creators": [...],
        "year": 2025,
        # ... other item metadata
    }
}
```

**Lifetime**: 
- Created at command start
- Populated during command execution
- Cleared after command completes
- Not persisted across commands

---

## 2. Module-Level Converter Cache

**Purpose**: Process-scoped cache for expensive converter initialization.

**Location**: `src/infrastructure/adapters/docling_converter.py`

**Structure**:
```python
_converter_cache: dict[str, DoclingConverterAdapter] = {
    "default": DoclingConverterAdapter(),  # Single instance per process
}
```

**Lifetime**: 
- Created on first `get_converter()` call
- Persists for process lifetime
- Not cleared (only on process termination)
- Process-scoped (not cross-process)

---

## 3. Enhanced ConversionResult

**Purpose**: Accurate page and heading information for proper chunking.

**Location**: Returned by `DoclingConverterAdapter.convert()`

**Structure**:
```python
{
    "doc_id": "path_abc123...",
    "structure": {
        "heading_tree": {
            "Introduction": {
                "level": 1,
                "text": "Introduction",
                "page": 1,
                "children": {
                    "Background": {
                        "level": 2,
                        "text": "Background",
                        "page": 1,
                    }
                }
            }
        },
        "page_map": {
            1: (0, 5000),      # Page 1: characters 0-5000
            2: (5000, 10000),  # Page 2: characters 5000-10000
            # ... all pages
        }
    },
    "plain_text": "Full document text...",
}
```

**Changes**:
- `page_map`: Now includes ALL pages (not just page 1)
- `heading_tree`: Now properly extracted with hierarchy
- Accurate page boundaries for chunking

---

## 4. Collection Payload with Model Binding

**Purpose**: Store embedding model ID in collection for automatic binding.

**Location**: Qdrant collection payload

**Structure**:
```python
collection_payload = {
    "embedding_model": "fastembed/all-MiniLM-L6-v2",
    "chunking_policy_version": "1.0",
    # ... other metadata
}
```

**Usage**:
- Stored during ingestion
- Retrieved during query
- Validated for model mismatch

---

## 5. Progress Reporting Context

**Purpose**: Track progress state for long-running operations.

**Location**: `src/infrastructure/adapters/rich_progress_reporter.py`

**Structure**:
```python
class DocumentProgressContext:
    current_stage: str  # "downloading", "converting", "chunking", "embedding", "storing"
    stage_description: str
    document_index: int
    total_documents: int
    last_update_time: float  # For throttling
```

**Lifetime**: 
- Created per document
- Updated during processing
- Finished on completion
- Cleared after use

---

## Notes

- All caches are in-memory (not persisted)
- Command-scoped caches are temporary (cleared after command)
- Module-level cache is process-scoped (not cross-process)
- Enhanced data structures maintain backward compatibility
- No database schema changes required
