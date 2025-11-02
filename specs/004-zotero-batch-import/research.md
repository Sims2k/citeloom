# Research: Zotero Collection Import with Batch Processing & Progress Indication

**Date**: 2025-01-27  
**Feature**: 004-zotero-batch-import  
**Status**: Complete

This document consolidates research findings and technical decisions for Zotero collection import with batch processing, progress indication, and checkpointing/resumability.

## 1. Pyzotero Collection Browsing & Import Patterns

### Decision: Use pyzotero with rate limiting wrapper for collection browsing and file downloads

**Rationale**:
- pyzotero provides direct Python access to Zotero Web API and local Zotero API
- Iterator/generator patterns support large collections without memory exhaustion
- Rate limiting wrapper ensures compliance with API limits (30,000 requests/day for web API)
- Local API mode (`local=True`) provides faster access without rate limits

**Alternatives Considered**:
- **Zotero SQLite direct access**: Risk of corruption/lock conflicts when Zotero desktop is running, requires file parsing
- **CSL-JSON export + file system scanning**: Manual workflow, doesn't support browsing/live metadata
- **Zotero Web API via requests**: More verbose, pyzotero provides cleaner abstraction

**Implementation Notes**:

**Collection Browsing**:
- `zot.collections()` returns all top-level collections
- `zot.collections_sub(collection_key)` returns subcollections recursively
- `zot.collection_items(collection_key)` returns items in collection (supports pagination)
- `zot.items(sort='dateAdded', direction='desc', limit=10)` for recent items
- `zot.tags()` for all tags with usage counts
- Use generator/iterator patterns for large result sets (FR-025)

**File Attachment Download**:
- `zot.children(item_key)` returns attachments for an item
- `zot.file(item_key, attachment_key)` downloads file content (remote API)
- For local API: Access files directly from Zotero storage directory (`~/Zotero/storage/{item_key}/`)
- Process all PDF attachments as separate documents (FR-028)

**Rate Limiting**:
- Web API: 0.5s minimum interval between requests, 2 requests per second maximum (FR-007)
- Local API: No rate limits
- Apply exponential backoff retry logic (3 retries, 1s base delay, 30s max delay, with jitter) (FR-016)

**Tag-Based Filtering**:
- Tag matching: Case-insensitive partial matching (substring matching) (FR-030)
- Filter before downloading attachments to reduce unnecessary I/O (FR-012)
- Include tags: OR logic (any match selects item)
- Exclude tags: ANY-match logic (any exclude tag excludes item)

**References**:
- Pyzotero documentation: https://pyzotero.readthedocs.io/
- Best practices: `docs/analysis/best-practices-implementation.md` Section 1 (Pyzotero Best Practices)
- Zotero API documentation: https://www.zotero.org/support/dev/web_api/v3/basics

---

## 2. Checkpointing & Resumable Batch Processing

### Decision: JSON checkpoint files with correlation ID-based naming and atomic writes

**Rationale**:
- Correlation ID enables traceability to audit logs
- JSON format is human-readable for debugging and manual inspection
- Atomic writes (temp file + rename) prevent corruption during crashes
- Document-level checkpoints enable fine-grained resume capability

**Alternatives Considered**:
- **SQLite checkpoint database**: Overkill for single-user local system, adds dependency
- **Binary checkpoint format**: Not human-readable, harder to debug
- **In-memory only checkpoints**: Lost on crash, not suitable for long-running imports

**Implementation Notes**:

**Checkpoint File Structure**:
```json
{
  "correlation_id": "uuid",
  "project_id": "my/project",
  "collection_key": "ABC123",
  "start_time": "2025-01-27T10:00:00Z",
  "last_update": "2025-01-27T10:15:00Z",
  "documents": [
    {
      "path": "var/zotero_downloads/ABC123/item1.pdf",
      "status": "completed",
      "stage": "storing",
      "chunks_count": 45,
      "doc_id": "doc123",
      "zotero_item_key": "ITEM_KEY",
      "error": null
    }
  ],
  "statistics": {
    "total_documents": 100,
    "completed": 73,
    "failed": 0,
    "pending": 27
  }
}
```

**File Location**: `var/checkpoints/{correlation_id}.json` (FR-029)

**Atomic Writes**:
- Write to temp file: `var/checkpoints/{correlation_id}.json.tmp`
- Atomic rename: `os.rename(temp_path, final_path)` (FR-021)

**Resume Logic**:
- Load checkpoint file on `--resume` flag
- Validate checkpoint integrity (schema validation, timestamp checks) (FR-022)
- Skip all documents with status "completed"
- Continue from first document with status "pending", "converting", "chunking", "embedding", or "storing"
- Update checkpoint after each document completes (FR-005)

**References**:
- Constitution: `Batch Processing & Checkpointing` section
- Best practices: `docs/analysis/best-practices-implementation.md` Section 5 (Checkpointing Architecture)

---

## 3. Two-Phase Import (Download Then Process)

### Decision: Download all attachments first to persistent storage, then process downloaded files

**Rationale**:
- Enables retry of processing phase without re-downloading
- Better fault tolerance for large collections
- Reduces bandwidth waste on retries
- Separates download errors from processing errors

**Alternatives Considered**:
- **Download and process inline**: Re-download required on retry, wastes bandwidth
- **Stream processing**: Complex error recovery, requires stateful connections

**Implementation Notes**:

**Download Phase**:
- Download all attachments to `var/zotero_downloads/{collection_key}/`
- Create download manifest documenting:
  - Collection metadata (key, name)
  - Item references (item_key, title, metadata)
  - File paths (local paths for downloaded files)
  - Download status (success/failure)
  - Timestamps (FR-013)

**Manifest Structure**:
```json
{
  "collection_key": "ABC123",
  "collection_name": "Machine Learning Papers",
  "download_time": "2025-01-27T10:00:00Z",
  "items": [
    {
      "item_key": "ITEM_KEY",
      "title": "Paper Title",
      "attachments": [
        {
          "attachment_key": "ATTACH_KEY",
          "filename": "paper.pdf",
          "local_path": "var/zotero_downloads/ABC123/paper.pdf",
          "download_status": "success",
          "file_size": 1234567
        }
      ],
      "metadata": {
        "citekey": "smith2024",
        "authors": ["Smith, John"],
        "year": 2024
      }
    }
  ]
}
```

**Process Phase**:
- Read download manifest
- Process downloaded files through existing pipeline (convert → chunk → embed → store)
- Use checkpointing for resumability during processing
- Support `--process-downloads` flag to process already-downloaded files (FR-014)

**References**:
- Constitution: `Batch Processing & Checkpointing` section - Two-phase import pattern
- Best practices: `docs/analysis/best-practices-implementation.md` Section 6 (Error Handling & Retry Logic)

---

## 4. Progress Indication with Rich Library

### Decision: Multi-level Rich progress bars with time estimates and stage-level progress

**Rationale**:
- Rich library already in dependencies (no new dependency needed)
- Multi-level progress (overall batch, per-document stages) provides comprehensive feedback
- Time estimates improve user confidence for long-running operations
- Stage-level progress prevents confusion during slow conversions

**Alternatives Considered**:
- **Simple print statements**: Not visually appealing, harder to update
- **tqdm library**: Good but Rich provides better terminal integration and styling
- **Custom terminal UI**: Too complex, Rich provides proven solution

**Implementation Notes**:

**Progress Bar Structure**:
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, TaskID

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
) as progress:
    # Overall batch progress
    batch_task = progress.add_task("Processing documents", total=100)
    
    for doc_idx, doc_path in enumerate(documents):
        # Per-document stage progress
        doc_task = progress.add_task(f"[cyan]Document {doc_idx+1}/{len(documents)}", total=4)
        
        # Stage: Converting
        progress.update(doc_task, advance=1, description="Converting...")
        # ... conversion logic ...
        
        # Stage: Chunking
        progress.update(doc_task, advance=1, description="Chunking...")
        # ... chunking logic ...
        
        # Stage: Embedding
        progress.update(doc_task, advance=1, description="Embedding...")
        # ... embedding logic ...
        
        # Stage: Storing
        progress.update(doc_task, advance=1, description="Storing...")
        # ... storage logic ...
        
        # Update batch progress
        progress.update(batch_task, advance=1)
```

**Time Estimation**:
- Track elapsed time per document stage
- Estimate remaining time based on average stage duration
- Update estimates as batch progresses (FR-004, SC-003)

**Non-Interactive Mode**:
- Detect non-TTY (Rich requires TTY for optimal display)
- Fallback to structured logging instead of progress bars
- Log progress updates: `[INFO] Processing document 3/10 (converting...)`

**References**:
- Rich documentation: https://rich.readthedocs.io/en/stable/progress.html
- Best practices: `docs/analysis/best-practices-implementation.md` Section 4 (Progress Indication with Rich)

---

## 5. Checkpoint Manager Architecture

### Decision: Separate CheckpointManager adapter in infrastructure layer with port interface

**Rationale**:
- Follows Clean Architecture (infrastructure adapter implements application port)
- Enables testing with doubles (mock checkpoint manager in application tests)
- Separates file I/O concerns from business logic

**Alternatives Considered**:
- **Inline checkpoint I/O in use case**: Violates Clean Architecture, harder to test
- **Domain entity with file I/O**: Violates domain purity (no I/O in domain layer)

**Implementation Notes**:

**Port Interface (Application Layer)**:
```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class CheckpointManagerPort(ABC):
    @abstractmethod
    def save_checkpoint(self, checkpoint: IngestionCheckpoint, path: Path) -> None:
        """Save checkpoint to file atomically."""
    
    @abstractmethod
    def load_checkpoint(self, path: Path) -> Optional[IngestionCheckpoint]:
        """Load checkpoint from file, return None if invalid/corrupted."""
    
    @abstractmethod
    def validate_checkpoint(self, checkpoint: IngestionCheckpoint) -> bool:
        """Validate checkpoint integrity."""
```

**Adapter Implementation (Infrastructure Layer)**:
```python
class CheckpointManagerAdapter(CheckpointManagerPort):
    def save_checkpoint(self, checkpoint: IngestionCheckpoint, path: Path) -> None:
        """Atomic write: temp file + rename."""
        import json
        import tempfile
        
        temp_path = path.with_suffix('.tmp')
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with temp_path.open('w') as f:
            json.dump(checkpoint.to_dict(), f, indent=2)
        
        temp_path.replace(path)  # Atomic rename
```

**References**:
- Constitution: Clean Architecture patterns, Checkpoint file patterns
- Best practices: `docs/analysis/best-practices-implementation.md` Section 5 (Checkpointing Architecture)

---

## 6. Integration with Existing Components

### Decision: Build on existing ZoteroPyzoteroResolver and ingest pipeline

**Rationale**:
- Reuse existing metadata resolution logic (no duplication)
- Extend existing ingest pipeline with progress callbacks
- Leverage existing Qdrant batch upsert patterns
- Maintain consistency with existing error handling

**Implementation Notes**:

**Metadata Resolution**:
- Use existing `ZoteroPyzoteroResolver.resolve()` for metadata extraction
- Already handles Better BibTeX citekey extraction
- Already extracts language field for OCR
- No changes needed to existing resolver

**Ingest Pipeline Enhancement**:
- Add progress callbacks to `IngestDocument` use case
- Callbacks report stage progress: converting, chunking, embedding, storing
- Existing pipeline (convert → chunk → embed → store) unchanged
- Checkpoint updates after each stage completion

**Qdrant Batch Upserts**:
- Use existing `QdrantIndexAdapter.upsert()` with batch size 100-500 points
- Save checkpoint after each successful batch upsert (FR-010)
- Existing write-guard validation ensures model consistency

**References**:
- Existing implementation: `src/infrastructure/adapters/zotero_metadata.py`
- Existing use case: `src/application/use_cases/ingest_document.py`
- Existing adapter: `src/infrastructure/adapters/qdrant_index.py`

---

## Summary

All technical decisions align with existing CiteLoom architecture and constitution patterns. The implementation extends existing components (ZoteroPyzoteroResolver, ingest pipeline, Qdrant adapter) rather than replacing them, maintaining consistency and reusability. Checkpointing, progress indication, and two-phase import patterns follow framework-specific best practices documented in the analysis documents.

