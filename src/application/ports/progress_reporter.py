"""Port interface for reporting progress during batch processing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    pass


class ProgressContext(Protocol):
    """Context manager for batch progress."""

    def update(self, completed: int) -> None:
        """Update batch progress with number of completed documents."""
        ...

    def finish(self) -> None:
        """Mark batch as complete."""
        ...


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
        ...

    def finish(self) -> None:
        """Mark document processing as complete."""
        ...

    def fail(self, error: str) -> None:
        """
        Mark document processing as failed.
        
        Args:
            error: Error message
        """
        ...


class ProgressReporterPort(ABC):
    """Port for reporting progress during batch processing."""

    @abstractmethod
    def start_batch(
        self,
        total_documents: int,
        description: str = "Processing documents",
    ) -> ProgressContext:
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
    ) -> DocumentProgressContext:
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

