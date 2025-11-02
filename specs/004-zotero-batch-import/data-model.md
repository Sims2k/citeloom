# Data Model: Zotero Collection Import with Batch Processing & Progress Indication

**Date**: 2025-01-27  
**Feature**: 004-zotero-batch-import  
**Status**: Complete

This document defines the domain entities, value objects, and data structures for Zotero collection import with batch processing, checkpointing, and progress indication.

## Domain Entities

### IngestionCheckpoint

**Purpose**: Represents the state of a batch ingestion operation, enabling resumable processing.

**Location**: `src/domain/models/checkpoint.py`

**Attributes**:
- `correlation_id: str` - Unique identifier linking to audit logs (UUID format)
- `project_id: str` - Project identifier (e.g., "my/project")
- `collection_key: str | None` - Zotero collection key (if Zotero import)
- `start_time: datetime` - Batch start timestamp (ISO 8601)
- `last_update: datetime` - Last checkpoint update timestamp (ISO 8601)
- `documents: list[DocumentCheckpoint]` - List of document checkpoints
- `statistics: CheckpointStatistics` - Aggregated statistics

**Behavior**:
- `add_document_checkpoint(doc: DocumentCheckpoint) -> None` - Add/update document checkpoint
- `get_incomplete_documents() -> list[DocumentCheckpoint]` - Filter documents not yet completed
- `get_completed_documents() -> list[DocumentCheckpoint]` - Filter completed documents
- `update_statistics() -> None` - Recalculate statistics from document checkpoints
- `to_dict() -> dict` - Serialize to JSON-compatible dict
- `from_dict(data: dict) -> IngestionCheckpoint` - Deserialize from dict

**Validation Rules**:
- `correlation_id` must be valid UUID format
- `project_id` must match project ID format (no empty strings)
- `start_time <= last_update` (last_update cannot be before start_time)
- All document checkpoints must have valid paths

**State Transitions**:
- Created: New checkpoint with `start_time`, empty `documents` list
- Updated: `last_update` timestamp updated, `documents` list modified
- Completed: All documents have status "completed" or "failed", statistics finalized

---

### DocumentCheckpoint

**Purpose**: Represents the state of a single document within a batch ingestion operation.

**Location**: `src/domain/models/checkpoint.py`

**Attributes**:
- `path: str` - File path to document (absolute path)
- `status: str` - Current status: "pending" | "converting" | "chunking" | "embedding" | "storing" | "completed" | "failed"
- `stage: str | None` - Current processing stage (same as status when active)
- `chunks_count: int` - Number of chunks created (0 if not yet chunked)
- `doc_id: str | None` - Document identifier (generated during processing)
- `zotero_item_key: str | None` - Zotero item key (if from Zotero import)
- `zotero_attachment_key: str | None` - Zotero attachment key (if from Zotero import)
- `error: str | None` - Error message if status is "failed"
- `updated_at: datetime` - Last update timestamp

**Behavior**:
- `mark_stage(stage: str) -> None` - Update status and stage
- `mark_completed(chunks_count: int, doc_id: str) -> None` - Mark as completed with results
- `mark_failed(error: str) -> None` - Mark as failed with error message
- `to_dict() -> dict` - Serialize to JSON-compatible dict
- `from_dict(data: dict) -> DocumentCheckpoint` - Deserialize from dict

**Validation Rules**:
- `path` must be non-empty, absolute path
- `status` must be one of valid status values
- `chunks_count >= 0` when provided
- `error` must be non-empty when status is "failed"

**State Transitions**:
- `pending` → `converting` (conversion starts)
- `converting` → `chunking` (conversion completes)
- `chunking` → `embedding` (chunking completes)
- `embedding` → `storing` (embedding completes)
- `storing` → `completed` (storage completes) or `failed` (error occurs)
- Any stage → `failed` (error occurs at any point)

---

### CheckpointStatistics

**Purpose**: Aggregated statistics for batch ingestion operation.

**Location**: `src/domain/models/checkpoint.py`

**Attributes**:
- `total_documents: int` - Total documents in batch
- `completed: int` - Number of completed documents
- `failed: int` - Number of failed documents
- `pending: int` - Number of pending/in-progress documents

**Behavior**:
- `calculate(documents: list[DocumentCheckpoint]) -> CheckpointStatistics` - Calculate from document list
- `completion_percentage() -> float` - Calculate completion percentage (0.0 to 1.0)
- `to_dict() -> dict` - Serialize to JSON-compatible dict

**Validation Rules**:
- `total_documents = completed + failed + pending`
- All counts >= 0
- `completion_percentage() <= 1.0`

---

### DownloadManifest

**Purpose**: Documents downloaded files from a Zotero collection for two-phase import.

**Location**: `src/domain/models/download_manifest.py`

**Attributes**:
- `collection_key: str` - Zotero collection key
- `collection_name: str` - Zotero collection name
- `download_time: datetime` - Download operation timestamp
- `items: list[DownloadManifestItem]` - List of items with downloaded attachments

**Behavior**:
- `add_item(item: DownloadManifestItem) -> None` - Add item to manifest
- `get_item_by_key(item_key: str) -> DownloadManifestItem | None` - Find item by Zotero key
- `get_all_file_paths() -> list[Path]` - Get all downloaded file paths
- `get_successful_downloads() -> list[DownloadManifestItem]` - Filter items with successful downloads
- `to_dict() -> dict` - Serialize to JSON-compatible dict
- `from_dict(data: dict) -> DownloadManifest` - Deserialize from dict

**Validation Rules**:
- `collection_key` must be non-empty
- `download_time` must be valid datetime
- All items must have valid `item_key`

---

### DownloadManifestItem

**Purpose**: Represents a Zotero item with its downloaded attachments in the manifest.

**Location**: `src/domain/models/download_manifest.py`

**Attributes**:
- `item_key: str` - Zotero item key
- `title: str` - Item title
- `attachments: list[DownloadManifestAttachment]` - List of downloaded attachments
- `metadata: dict[str, Any]` - Zotero item metadata (citekey, authors, year, tags, collections)

**Behavior**:
- `add_attachment(attachment: DownloadManifestAttachment) -> None` - Add attachment to item
- `get_pdf_attachments() -> list[DownloadManifestAttachment]` - Filter PDF attachments only
- `to_dict() -> dict` - Serialize to JSON-compatible dict

**Validation Rules**:
- `item_key` must be non-empty
- `title` can be empty (optional field in Zotero)
- All attachments must have valid `attachment_key`

---

### DownloadManifestAttachment

**Purpose**: Represents a downloaded file attachment in the manifest.

**Location**: `src/domain/models/download_manifest.py`

**Attributes**:
- `attachment_key: str` - Zotero attachment key
- `filename: str` - Original filename
- `local_path: Path` - Local file path where downloaded
- `download_status: str` - "success" | "failed"
- `file_size: int | None` - File size in bytes (if download succeeded)
- `error: str | None` - Error message (if download failed)

**Behavior**:
- `to_dict() -> dict` - Serialize to JSON-compatible dict
- `from_dict(data: dict) -> DownloadManifestAttachment` - Deserialize from dict

**Validation Rules**:
- `attachment_key` must be non-empty
- `local_path` must be absolute path when download_status is "success"
- `error` must be non-empty when download_status is "failed"

---

## Value Objects

### ZoteroCollectionKey

**Purpose**: Validates Zotero collection key format.

**Location**: `src/domain/models/zotero.py` (new file or extend existing)

**Attributes**:
- `value: str` - Collection key (alphanumeric, typically 8 characters)

**Validation Rules**:
- Non-empty string
- Alphanumeric characters only
- Length typically 8 characters (Zotero standard)

---

### ZoteroItemKey

**Purpose**: Validates Zotero item key format.

**Location**: `src/domain/models/zotero.py`

**Attributes**:
- `value: str` - Item key (alphanumeric, typically 8 characters)

**Validation Rules**:
- Non-empty string
- Alphanumeric characters only
- Length typically 8 characters (Zotero standard)

---

## Relationships

```
IngestionCheckpoint
├── contains many → DocumentCheckpoint
└── aggregates → CheckpointStatistics (calculated from DocumentCheckpoint list)

DownloadManifest
└── contains many → DownloadManifestItem
    └── contains many → DownloadManifestAttachment
```

## Data Storage

### Checkpoint Files

**Location**: `var/checkpoints/{correlation_id}.json`

**Format**: JSON (human-readable)

**Example**:
```json
{
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "project_id": "my/project",
  "collection_key": "ABC12345",
  "start_time": "2025-01-27T10:00:00Z",
  "last_update": "2025-01-27T10:15:30Z",
  "documents": [
    {
      "path": "var/zotero_downloads/ABC12345/paper1.pdf",
      "status": "completed",
      "stage": "storing",
      "chunks_count": 45,
      "doc_id": "doc_a1b2c3d4",
      "zotero_item_key": "ITEM1234",
      "zotero_attachment_key": "ATTACH5678",
      "error": null,
      "updated_at": "2025-01-27T10:05:15Z"
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

### Download Manifest Files

**Location**: `var/zotero_downloads/{collection_key}/manifest.json`

**Format**: JSON (human-readable)

**Example**:
```json
{
  "collection_key": "ABC12345",
  "collection_name": "Machine Learning Papers",
  "download_time": "2025-01-27T10:00:00Z",
  "items": [
    {
      "item_key": "ITEM1234",
      "title": "Neural Networks for NLP",
      "attachments": [
        {
          "attachment_key": "ATTACH5678",
          "filename": "paper.pdf",
          "local_path": "var/zotero_downloads/ABC12345/paper.pdf",
          "download_status": "success",
          "file_size": 1234567,
          "error": null
        }
      ],
      "metadata": {
        "citekey": "smith2024",
        "authors": ["Smith, John"],
        "year": 2024,
        "tags": ["#MachineLearning", "#NLP"],
        "collections": ["ABC12345"]
      }
    }
  ]
}
```

## Integration with Existing Models

### Existing Domain Models (No Changes)

- `Chunk` - Used during chunking stage, stored in Qdrant
- `ConversionResult` - Used during conversion stage
- `CitationMeta` - Extracted via existing ZoteroPyzoteroResolver

### Application DTOs (Enhanced)

- `IngestRequest` - Enhanced with Zotero collection/key, tag filters, resume flag
- `IngestResult` - Enhanced with batch statistics, checkpoint path

## Constraints

- Checkpoint files must be human-readable JSON for debugging (constitution requirement)
- Checkpoint writes must be atomic (temp file + rename) to prevent corruption
- Download manifests must persist until user-controlled cleanup (default: retain)
- Correlation ID links checkpoints to audit logs for traceability

