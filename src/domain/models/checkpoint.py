"""Domain models for batch ingestion checkpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

VALID_STATUSES = {"pending", "converting", "chunking", "embedding", "storing", "completed", "failed"}


@dataclass
class CheckpointStatistics:
    """
    Aggregated statistics for batch ingestion operation.
    
    Value object that calculates completion statistics from document checkpoints.
    """

    total_documents: int
    completed: int = 0
    failed: int = 0
    pending: int = 0

    def completion_percentage(self) -> float:
        """Calculate completion percentage (0.0 to 1.0)."""
        if self.total_documents == 0:
            return 1.0
        return (self.completed + self.failed) / self.total_documents

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "total_documents": self.total_documents,
            "completed": self.completed,
            "failed": self.failed,
            "pending": self.pending,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CheckpointStatistics:
        """Deserialize from dict."""
        return cls(
            total_documents=data["total_documents"],
            completed=data.get("completed", 0),
            failed=data.get("failed", 0),
            pending=data.get("pending", 0),
        )

    def __post_init__(self) -> None:
        """Validate statistics consistency."""
        if self.total_documents < 0:
            raise ValueError("total_documents must be >= 0")
        if self.completed < 0:
            raise ValueError("completed must be >= 0")
        if self.failed < 0:
            raise ValueError("failed must be >= 0")
        if self.pending < 0:
            raise ValueError("pending must be >= 0")
        calculated_total = self.completed + self.failed + self.pending
        if calculated_total != self.total_documents:
            raise ValueError(
                f"Statistics inconsistent: completed={self.completed}, "
                f"failed={self.failed}, pending={self.pending} "
                f"does not sum to total_documents={self.total_documents}"
            )
        if self.completion_percentage() > 1.0:
            raise ValueError("completion_percentage() must be <= 1.0")


@dataclass
class DocumentCheckpoint:
    """
    Represents the state of a single document within a batch ingestion operation.
    
    Attributes:
        path: File path to document (absolute path)
        status: Current status: "pending" | "converting" | "chunking" | "embedding" | "storing" | "completed" | "failed"
        stage: Current processing stage (same as status when active)
        chunks_count: Number of chunks created (0 if not yet chunked)
        doc_id: Document identifier (generated during processing)
        zotero_item_key: Zotero item key (if from Zotero import)
        zotero_attachment_key: Zotero attachment key (if from Zotero import)
        error: Error message if status is "failed"
        updated_at: Last update timestamp
    """

    path: str
    status: str = "pending"
    stage: str | None = None
    chunks_count: int = 0
    doc_id: str | None = None
    zotero_item_key: str | None = None
    zotero_attachment_key: str | None = None
    error: str | None = None
    updated_at: datetime = field(default_factory=datetime.now)

    def mark_stage(self, stage: str) -> None:
        """Update status and stage."""
        if stage not in VALID_STATUSES:
            raise ValueError(f"Invalid stage: {stage}. Must be one of {VALID_STATUSES}")
        self.status = stage
        self.stage = stage
        self.updated_at = datetime.now()

    def mark_completed(self, chunks_count: int, doc_id: str) -> None:
        """Mark as completed with results."""
        if chunks_count < 0:
            raise ValueError("chunks_count must be >= 0")
        if not doc_id:
            raise ValueError("doc_id must be non-empty")
        self.status = "completed"
        self.stage = "storing"
        self.chunks_count = chunks_count
        self.doc_id = doc_id
        self.updated_at = datetime.now()

    def mark_failed(self, error: str) -> None:
        """Mark as failed with error message."""
        if not error:
            raise ValueError("error must be non-empty when marking as failed")
        self.status = "failed"
        self.stage = None
        self.error = error
        self.updated_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result: dict[str, Any] = {
            "path": self.path,
            "status": self.status,
            "stage": self.stage,
            "chunks_count": self.chunks_count,
            "updated_at": self.updated_at.isoformat(),
        }
        if self.doc_id is not None:
            result["doc_id"] = self.doc_id
        if self.zotero_item_key is not None:
            result["zotero_item_key"] = self.zotero_item_key
        if self.zotero_attachment_key is not None:
            result["zotero_attachment_key"] = self.zotero_attachment_key
        if self.error is not None:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DocumentCheckpoint:
        """Deserialize from dict."""
        updated_at = datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else datetime.now()
        return cls(
            path=data["path"],
            status=data.get("status", "pending"),
            stage=data.get("stage"),
            chunks_count=data.get("chunks_count", 0),
            doc_id=data.get("doc_id"),
            zotero_item_key=data.get("zotero_item_key"),
            zotero_attachment_key=data.get("zotero_attachment_key"),
            error=data.get("error"),
            updated_at=updated_at,
        )

    def __post_init__(self) -> None:
        """Validate document checkpoint."""
        if not self.path:
            raise ValueError("path must be non-empty")
        # Note: path validation for absolute path is done at use case level
        if self.status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}, got {self.status}")
        if self.chunks_count < 0:
            raise ValueError("chunks_count must be >= 0")
        if self.status == "failed" and not self.error:
            raise ValueError("error must be non-empty when status is 'failed'")
        if self.stage is not None and self.stage not in VALID_STATUSES:
            raise ValueError(f"stage must be one of {VALID_STATUSES} or None, got {self.stage}")


@dataclass
class IngestionCheckpoint:
    """
    Represents the state of a batch ingestion operation, enabling resumable processing.
    
    Attributes:
        correlation_id: Unique identifier linking to audit logs (UUID format)
        project_id: Project identifier (e.g., "my/project")
        collection_key: Zotero collection key (if Zotero import)
        start_time: Batch start timestamp (ISO 8601)
        last_update: Last checkpoint update timestamp (ISO 8601)
        documents: List of document checkpoints
        statistics: Aggregated statistics
    """

    correlation_id: str
    project_id: str
    collection_key: str | None = None
    start_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    documents: list[DocumentCheckpoint] = field(default_factory=list)
    statistics: CheckpointStatistics = field(default_factory=lambda: CheckpointStatistics(total_documents=0))

    def add_document_checkpoint(self, doc: DocumentCheckpoint) -> None:
        """Add/update document checkpoint."""
        # Check if document with same path exists and update it, otherwise append
        for idx, existing_doc in enumerate(self.documents):
            if existing_doc.path == doc.path:
                self.documents[idx] = doc
                self.update_statistics()
                self.last_update = datetime.now()
                return
        self.documents.append(doc)
        self.update_statistics()
        self.last_update = datetime.now()

    def get_incomplete_documents(self) -> list[DocumentCheckpoint]:
        """Filter documents not yet completed."""
        return [doc for doc in self.documents if doc.status not in {"completed", "failed"}]

    def get_completed_documents(self) -> list[DocumentCheckpoint]:
        """Filter completed documents."""
        return [doc for doc in self.documents if doc.status == "completed"]

    def update_statistics(self) -> None:
        """Recalculate statistics from document checkpoints."""
        total = len(self.documents)
        completed = sum(1 for doc in self.documents if doc.status == "completed")
        failed = sum(1 for doc in self.documents if doc.status == "failed")
        pending = total - completed - failed
        
        self.statistics = CheckpointStatistics(
            total_documents=total,
            completed=completed,
            failed=failed,
            pending=pending,
        )
        self.last_update = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result: dict[str, Any] = {
            "correlation_id": self.correlation_id,
            "project_id": self.project_id,
            "start_time": self.start_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "documents": [doc.to_dict() for doc in self.documents],
            "statistics": self.statistics.to_dict(),
        }
        if self.collection_key is not None:
            result["collection_key"] = self.collection_key
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IngestionCheckpoint:
        """Deserialize from dict."""
        start_time = datetime.fromisoformat(data["start_time"]) if isinstance(data.get("start_time"), str) else datetime.now()
        last_update = datetime.fromisoformat(data["last_update"]) if isinstance(data.get("last_update"), str) else datetime.now()
        documents = [DocumentCheckpoint.from_dict(doc_data) for doc_data in data.get("documents", [])]
        statistics = CheckpointStatistics.from_dict(data.get("statistics", {"total_documents": len(documents)}))
        
        return cls(
            correlation_id=data["correlation_id"],
            project_id=data["project_id"],
            collection_key=data.get("collection_key"),
            start_time=start_time,
            last_update=last_update,
            documents=documents,
            statistics=statistics,
        )

    def __post_init__(self) -> None:
        """Validate ingestion checkpoint."""
        if not self.correlation_id:
            raise ValueError("correlation_id must be non-empty")
        # Validate UUID format (basic check - 8-4-4-4-12 hex characters with dashes)
        if len(self.correlation_id) < 36:  # Minimal UUID length
            raise ValueError(f"correlation_id must be valid UUID format, got: {self.correlation_id}")
        if not self.project_id:
            raise ValueError("project_id must be non-empty")
        if self.start_time > self.last_update:
            raise ValueError("last_update cannot be before start_time")
        # Validate all document checkpoints have valid paths
        for doc in self.documents:
            if not doc.path:
                raise ValueError(f"All document checkpoints must have valid paths, got: {doc}")
        # Ensure statistics are consistent with documents
        self.update_statistics()

