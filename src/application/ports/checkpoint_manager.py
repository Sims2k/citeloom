"""Port interface for managing checkpoint files."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.models.checkpoint import IngestionCheckpoint


class CheckpointManagerPort(ABC):
    """Port for managing checkpoint files."""

    @abstractmethod
    def save_checkpoint(
        self,
        checkpoint: IngestionCheckpoint,
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
    ) -> IngestionCheckpoint | None:
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
        checkpoint: IngestionCheckpoint,
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

