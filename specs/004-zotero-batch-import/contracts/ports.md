# Port Contracts: Zotero Collection Import with Batch Processing

**Date**: 2025-01-27  
**Feature**: 004-zotero-batch-import  
**Status**: Complete

This document defines the port (protocol) interfaces for Zotero collection import, checkpointing, and batch processing. Ports are defined in the application layer and implemented by infrastructure adapters.

## ZoteroImporterPort

**Purpose**: Interface for importing documents from Zotero collections, including browsing collections, fetching items, and downloading attachments.

**Location**: `src/application/ports/zotero_importer.py`

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Optional

class ZoteroImporterPort(ABC):
    """Port for importing documents from Zotero collections."""
    
    @abstractmethod
    def list_collections(self) -> list[dict[str, Any]]:
        """
        List all top-level collections in Zotero library.
        
        Returns:
            List of collections with keys: 'key', 'name', 'parentCollection'
        """
        pass
    
    @abstractmethod
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Get items in a collection (generator to avoid loading all into memory).
        
        Args:
            collection_key: Zotero collection key
            include_subcollections: If True, recursively include items from subcollections
        
        Yields:
            Zotero items with keys: 'key', 'data' (containing title, itemType, etc.)
        """
        pass
    
    @abstractmethod
    def get_item_attachments(
        self,
        item_key: str,
    ) -> list[dict[str, Any]]:
        """
        Get PDF attachments for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            List of attachments with keys: 'key', 'data' (containing filename, contentType, linkMode)
        """
        pass
    
    @abstractmethod
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> Path:
        """
        Download a file attachment from Zotero.
        
        Args:
            item_key: Zotero item key
            attachment_key: Zotero attachment key
            output_path: Local path where file should be saved
        
        Returns:
            Path to downloaded file
        
        Raises:
            ZoteroAPIError: If download fails after retries
        """
        pass
    
    @abstractmethod
    def get_item_metadata(
        self,
        item_key: str,
    ) -> dict[str, Any]:
        """
        Get full metadata for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            Item metadata dict with keys: title, creators (authors), date (year), DOI, tags, collections
        """
        pass
    
    @abstractmethod
    def list_tags(self) -> list[dict[str, Any]]:
        """
        List all tags used in Zotero library.
        
        Returns:
            List of tags with keys: 'tag', 'meta' (containing numItems count)
        """
        pass
    
    @abstractmethod
    def get_recent_items(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recently added items to Zotero library.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of items sorted by dateAdded (descending)
        """
        pass
    
    @abstractmethod
    def find_collection_by_name(
        self,
        collection_name: str,
    ) -> Optional[dict[str, Any]]:
        """
        Find collection by name (case-insensitive partial match).
        
        Args:
            collection_name: Collection name to search for
        
        Returns:
            Collection dict with keys: 'key', 'name', or None if not found
        """
        pass
```

**Error Types**:
- `ZoteroAPIError`: Base exception for Zotero API errors
- `ZoteroConnectionError`: Connection failures (invalid API key, library ID, Zotero not running)
- `ZoteroRateLimitError`: Rate limit exceeded (web API only)

---

## CheckpointManagerPort

**Purpose**: Interface for saving and loading checkpoint files for resumable batch processing.

**Location**: `src/application/ports/checkpoint_manager.py`

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class CheckpointManagerPort(ABC):
    """Port for managing checkpoint files."""
    
    @abstractmethod
    def save_checkpoint(
        self,
        checkpoint: 'IngestionCheckpoint',
        path: Path,
    ) -> None:
        """
        Save checkpoint to file atomically (write to temp file, then rename).
        
        Args:
            checkpoint: IngestionCheckpoint domain entity
            path: File path where checkpoint should be saved
        
        Raises:
            CheckpointWriteError: If save fails
        """
        pass
    
    @abstractmethod
    def load_checkpoint(
        self,
        path: Path,
    ) -> Optional['IngestionCheckpoint']:
        """
        Load checkpoint from file.
        
        Args:
            path: File path to checkpoint file
        
        Returns:
            IngestionCheckpoint domain entity, or None if file doesn't exist or is invalid
        
        Raises:
            CheckpointReadError: If file exists but cannot be read/parsed
        """
        pass
    
    @abstractmethod
    def validate_checkpoint(
        self,
        checkpoint: 'IngestionCheckpoint',
    ) -> bool:
        """
        Validate checkpoint integrity.
        
        Args:
            checkpoint: IngestionCheckpoint to validate
        
        Returns:
            True if checkpoint is valid, False otherwise
        """
        pass
    
    @abstractmethod
    def checkpoint_exists(
        self,
        path: Path,
    ) -> bool:
        """
        Check if checkpoint file exists.
        
        Args:
            path: File path to check
        
        Returns:
            True if file exists, False otherwise
        """
        pass
```

**Error Types**:
- `CheckpointWriteError`: Failed to write checkpoint file
- `CheckpointReadError`: Failed to read/parse checkpoint file
- `CheckpointValidationError`: Checkpoint file is invalid or corrupted

---

## ProgressReporterPort

**Purpose**: Interface for reporting progress during batch processing (allows testing with doubles).

**Location**: `src/application/ports/progress_reporter.py`

```python
from abc import ABC, abstractmethod
from typing import Protocol

class ProgressReporterPort(ABC):
    """Port for reporting progress during batch processing."""
    
    @abstractmethod
    def start_batch(
        self,
        total_documents: int,
        description: str = "Processing documents",
    ) -> 'ProgressContext':
        """
        Start progress reporting for a batch operation.
        
        Args:
            total_documents: Total number of documents to process
            description: Description for progress bar
        
        Returns:
            ProgressContext for updating progress
        """
        pass
    
    @abstractmethod
    def start_document(
        self,
        document_index: int,
        total_documents: int,
        document_name: str,
    ) -> 'DocumentProgressContext':
        """
        Start progress reporting for a single document.
        
        Args:
            document_index: Index of current document (1-based)
            total_documents: Total number of documents
            document_name: Name/identifier for document
        
        Returns:
            DocumentProgressContext for updating document-level progress
        """
        pass


class ProgressContext(Protocol):
    """Context manager for batch progress."""
    
    def update(self, completed: int) -> None:
        """Update batch progress with number of completed documents."""
        pass
    
    def finish(self) -> None:
        """Mark batch as complete."""
        pass


class DocumentProgressContext(Protocol):
    """Context manager for document-level progress."""
    
    def update_stage(
        self,
        stage: str,
        description: str,
    ) -> None:
        """
        Update current processing stage.
        
        Args:
            stage: Stage name (converting, chunking, embedding, storing)
            description: Human-readable description
        """
        pass
    
    def finish(self) -> None:
        """Mark document processing as complete."""
        pass
    
    def fail(self, error: str) -> None:
        """
        Mark document processing as failed.
        
        Args:
            error: Error message
        """
        pass
```

**Note**: This port enables dependency inversion for progress indication. Infrastructure layer implements Rich progress bars, but application layer doesn't depend on Rich directly.

---

## Integration with Existing Ports

### Enhanced: IngestDocument Use Case

The existing `IngestDocument` use case will be enhanced to accept progress callbacks:

```python
# Existing signature (unchanged):
def ingest_document(
    request: IngestRequest,
    converter: TextConverterPort,
    chunker: ChunkerPort,
    resolver: MetadataResolverPort,
    embedder: EmbeddingPort,
    index: VectorIndexPort,
    audit_dir: Path | None = None,
    correlation_id: str | None = None,
) -> IngestResult:

# Enhanced signature (optional progress reporter):
def ingest_document(
    request: IngestRequest,
    converter: TextConverterPort,
    chunker: ChunkerPort,
    resolver: MetadataResolverPort,
    embedder: EmbeddingPort,
    index: VectorIndexPort,
    audit_dir: Path | None = None,
    correlation_id: str | None = None,
    progress_reporter: ProgressReporterPort | None = None,  # NEW
) -> IngestResult:
```

### Existing Ports (No Changes)

- `TextConverterPort` - Document conversion
- `ChunkerPort` - Document chunking
- `MetadataResolverPort` - Metadata resolution (existing ZoteroPyzoteroResolver)
- `EmbeddingPort` - Embedding generation
- `VectorIndexPort` - Vector storage (Qdrant)

---

## Implementation Responsibilities

### Infrastructure Adapters

**ZoteroImporterAdapter** (implements `ZoteroImporterPort`):
- Uses pyzotero library for API access
- Implements rate limiting wrapper (0.5s interval for web API)
- Handles local vs remote API fallback
- Implements retry logic with exponential backoff

**CheckpointManagerAdapter** (implements `CheckpointManagerPort`):
- Handles JSON serialization/deserialization
- Implements atomic writes (temp file + rename)
- Validates checkpoint schema and integrity
- Manages checkpoint file paths

**RichProgressReporterAdapter** (implements `ProgressReporterPort`):
- Uses Rich library for visual progress bars
- Detects non-interactive mode (non-TTY) and falls back to logging
- Provides multi-level progress (batch, document, stage)
- Estimates time remaining based on elapsed time

### Application Use Cases

**BatchImportFromZotero** (new use case):
- Orchestrates two-phase import (download then process)
- Manages checkpoint updates
- Coordinates progress reporting
- Handles errors and retries

