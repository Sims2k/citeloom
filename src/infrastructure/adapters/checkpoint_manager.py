"""Checkpoint manager adapter for atomic checkpoint file I/O."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...domain.models.checkpoint import IngestionCheckpoint

logger = logging.getLogger(__name__)


class CheckpointWriteError(Exception):
    """Raised when checkpoint save fails."""

    pass


class CheckpointReadError(Exception):
    """Raised when checkpoint load fails."""

    pass


class CheckpointManagerAdapter:
    """Adapter for managing checkpoint files with atomic writes."""

    def __init__(self, checkpoints_dir: Path | None = None) -> None:
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoints_dir: Directory for checkpoint files (default: var/checkpoints)
        """
        if checkpoints_dir is None:
            checkpoints_dir = Path("var/checkpoints")
        
        self.checkpoints_dir = Path(checkpoints_dir)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpoint_path(self, correlation_id: str) -> Path:
        """
        Generate checkpoint file path using correlation ID.
        
        Args:
            correlation_id: Correlation ID for checkpoint file naming
            
        Returns:
            Path to checkpoint file (var/checkpoints/{correlation_id}.json)
        """
        return self.checkpoints_dir / f"{correlation_id}.json"

    def checkpoint_exists(self, path: Path | None = None, correlation_id: str | None = None) -> bool:
        """
        Check if checkpoint file exists.
        
        Args:
            path: File path to check (preferred)
            correlation_id: Correlation ID to generate path (used if path not provided)
        
        Returns:
            True if file exists, False otherwise
        """
        if path is None:
            if correlation_id is None:
                raise ValueError("Either path or correlation_id must be provided")
            path = self.get_checkpoint_path(correlation_id)
        
        return Path(path).exists()

    def save_checkpoint(
        self,
        checkpoint: IngestionCheckpoint,
        path: Path | None = None,
    ) -> None:
        """
        Save checkpoint to file atomically (write to temp file, then rename).
        
        Args:
            checkpoint: IngestionCheckpoint domain entity
            path: File path where checkpoint should be saved (if None, uses correlation_id)
        
        Raises:
            CheckpointWriteError: If save fails
        """
        if path is None:
            path = self.get_checkpoint_path(checkpoint.correlation_id)
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file first for atomic operation
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=path.parent,
                prefix=f".{path.name}.tmp.",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                
                # Serialize checkpoint to JSON
                checkpoint_dict = checkpoint.to_dict()
                json.dump(checkpoint_dict, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                
                # Ensure data is written to disk
                import os
                os.fsync(temp_file.fileno())
            
            # Atomic rename (move) from temp file to final path
            import shutil
            shutil.move(str(temp_path), str(path))
            
            logger.debug(
                f"Checkpoint saved: {path}",
                extra={"correlation_id": checkpoint.correlation_id, "path": str(path)},
            )
            
        except Exception as e:
            # Clean up temp file if it exists
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            
            error_msg = f"Failed to save checkpoint to {path}: {e}"
            logger.error(error_msg, extra={"correlation_id": checkpoint.correlation_id}, exc_info=True)
            raise CheckpointWriteError(error_msg) from e

    def load_checkpoint(
        self,
        path: Path | None = None,
        correlation_id: str | None = None,
    ) -> IngestionCheckpoint | None:
        """
        Load checkpoint from file.
        
        Args:
            path: File path to checkpoint file (preferred)
            correlation_id: Correlation ID to generate path (used if path not provided)
        
        Returns:
            IngestionCheckpoint domain entity, or None if file doesn't exist or is invalid
        
        Raises:
            CheckpointReadError: If file exists but cannot be read/parsed
        """
        if path is None:
            if correlation_id is None:
                raise ValueError("Either path or correlation_id must be provided")
            path = self.get_checkpoint_path(correlation_id)
        
        path = Path(path)
        
        if not path.exists():
            logger.debug(f"Checkpoint file not found: {path}")
            return None
        
        try:
            with path.open("r") as f:
                checkpoint_dict = json.load(f)
            
            # Deserialize checkpoint from dict
            from ...domain.models.checkpoint import IngestionCheckpoint
            checkpoint = IngestionCheckpoint.from_dict(checkpoint_dict)
            
            logger.debug(
                f"Checkpoint loaded: {path}",
                extra={"correlation_id": checkpoint.correlation_id, "path": str(path)},
            )
            
            return checkpoint
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in checkpoint file {path}: {e}"
            logger.error(error_msg, exc_info=True)
            raise CheckpointReadError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load checkpoint from {path}: {e}"
            logger.error(error_msg, exc_info=True)
            raise CheckpointReadError(error_msg) from e

    def validate_checkpoint(
        self,
        checkpoint: IngestionCheckpoint,
    ) -> bool:
        """
        Validate checkpoint integrity.
        
        Checks:
        - Schema validity (correlation_id, project_id, timestamps, documents list)
        - Timestamp consistency (start_time <= last_update)
        - Document checkpoint validity (paths, statuses, stages)
        
        Args:
            checkpoint: IngestionCheckpoint to validate
        
        Returns:
            True if checkpoint is valid, False otherwise
        """
        try:
            # Basic schema validation (should already be validated by domain model __post_init__)
            if not checkpoint.correlation_id:
                logger.warning("Checkpoint validation failed: missing correlation_id")
                return False
            
            if not checkpoint.project_id:
                logger.warning("Checkpoint validation failed: missing project_id")
                return False
            
            # Timestamp consistency
            if checkpoint.start_time > checkpoint.last_update:
                logger.warning(
                    "Checkpoint validation failed: start_time > last_update",
                    extra={
                        "correlation_id": checkpoint.correlation_id,
                        "start_time": checkpoint.start_time.isoformat(),
                        "last_update": checkpoint.last_update.isoformat(),
                    },
                )
                return False
            
            # Validate all document checkpoints
            for doc in checkpoint.documents:
                if not doc.path:
                    logger.warning(
                        "Checkpoint validation failed: document checkpoint missing path",
                        extra={"correlation_id": checkpoint.correlation_id},
                    )
                    return False
                
                # Check if status is valid
                from ...domain.models.checkpoint import VALID_STATUSES
                if doc.status not in VALID_STATUSES:
                    logger.warning(
                        f"Checkpoint validation failed: invalid document status '{doc.status}'",
                        extra={"correlation_id": checkpoint.correlation_id, "path": doc.path},
                    )
                    return False
                
                # If failed, must have error message
                if doc.status == "failed" and not doc.error:
                    logger.warning(
                        "Checkpoint validation failed: failed document missing error message",
                        extra={"correlation_id": checkpoint.correlation_id, "path": doc.path},
                    )
                    return False
            
            # Validate statistics consistency
            checkpoint.update_statistics()  # Recalculate to ensure consistency
            if checkpoint.statistics.total_documents != len(checkpoint.documents):
                logger.warning(
                    "Checkpoint validation failed: statistics total_documents mismatch",
                    extra={
                        "correlation_id": checkpoint.correlation_id,
                        "statistics_total": checkpoint.statistics.total_documents,
                        "documents_count": len(checkpoint.documents),
                    },
                )
                return False
            
            return True
            
        except Exception as e:
            logger.warning(
                f"Checkpoint validation error: {e}",
                extra={"correlation_id": checkpoint.correlation_id if checkpoint else None},
                exc_info=True,
            )
            return False

