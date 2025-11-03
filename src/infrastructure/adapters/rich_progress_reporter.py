"""Rich-based progress reporter adapter for batch processing."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ...application.ports.progress_reporter import (
    DocumentProgressContext,
    ProgressContext,
    ProgressReporterPort,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RichProgressContext:
    """Context manager for batch-level progress using Rich."""

    def __init__(
        self,
        progress: Progress,
        task_id: TaskID,
        total_documents: int,
    ) -> None:
        """
        Initialize batch progress context.
        
        Args:
            progress: Rich Progress instance
            task_id: Task ID for batch progress
            total_documents: Total number of documents
        """
        self.progress = progress
        self.task_id = task_id
        self.total_documents = total_documents
        self.completed = 0

    def update(self, completed: int) -> None:
        """
        Update batch progress with number of completed documents.
        
        Args:
            completed: Number of documents completed
        """
        self.completed = completed
        self.progress.update(self.task_id, completed=completed)

    def finish(self) -> None:
        """Mark batch as complete."""
        self.progress.update(self.task_id, completed=self.total_documents)
        self.progress.stop_task(self.task_id)


class RichDocumentProgressContext:
    """Context manager for document-level progress using Rich."""

    def __init__(
        self,
        progress: Progress,
        task_id: TaskID,
        document_name: str,
    ) -> None:
        """
        Initialize document progress context.
        
        Args:
            progress: Rich Progress instance
            task_id: Task ID for document progress
            document_name: Name/identifier for document
        """
        self.progress = progress
        self.task_id = task_id
        self.document_name = document_name
        self.current_stage = "pending"
        self.stage_start_time: dict[str, float] = {}
        self.stage_durations: dict[str, list[float]] = {}
        # T034: Progress update throttling (maximum once per second)
        self._last_update_time = 0.0
        self._update_interval = 1.0  # seconds

    def update_stage(
        self,
        stage: str,
        description: str,
    ) -> None:
        """
        Update current processing stage.
        
        T034: Implements progress update throttling (maximum once per second).
        
        Args:
            stage: Stage name (converting, chunking, embedding, storing)
            description: Human-readable description
        """
        # T034: Throttle progress updates (maximum once per second)
        now = time.time()
        if now - self._last_update_time < self._update_interval:
            # Skip update if less than 1 second has passed
            return
        
        self._last_update_time = now
        
        # Record stage duration for time estimation
        if self.current_stage != "pending" and self.current_stage in self.stage_start_time:
            elapsed = time.time() - self.stage_start_time[self.current_stage]
            if self.current_stage not in self.stage_durations:
                self.stage_durations[self.current_stage] = []
            self.stage_durations[self.current_stage].append(elapsed)
        
        self.current_stage = stage
        self.stage_start_time[stage] = time.time()
        
        # Update progress description with stage
        full_description = f"[cyan]{self.document_name}[/cyan] - {description}"
        self.progress.update(
            self.task_id,
            description=full_description,
            advance=1,
        )

    def finish(self) -> None:
        """Mark document processing as complete."""
        # Advance to completion (all 4 stages done)
        self.progress.update(
            self.task_id,
            completed=4,  # 4 stages: converting, chunking, embedding, storing
        )
        self.progress.stop_task(self.task_id)

    def fail(self, error: str) -> None:
        """
        Mark document processing as failed.
        
        Args:
            error: Error message
        """
        # Update description to show error
        error_description = f"[red]{self.document_name}[/red] - Failed: {error[:50]}"
        self.progress.update(
            self.task_id,
            description=error_description,
        )
        self.progress.stop_task(self.task_id)


class LoggingProgressContext:
    """Fallback progress context for non-interactive mode using logging."""

    def __init__(
        self,
        total_documents: int,
        description: str,
    ) -> None:
        """
        Initialize logging-based progress context.
        
        Args:
            total_documents: Total number of documents
            description: Description for progress
        """
        self.total_documents = total_documents
        self.description = description
        self.completed = 0
        self.start_time = time.time()
        logger.info(f"Starting: {description} ({total_documents} documents)")

    def update(self, completed: int) -> None:
        """
        Update batch progress with number of completed documents.
        
        Args:
            completed: Number of documents completed
        """
        self.completed = completed
        elapsed = time.time() - self.start_time
        percentage = (completed / self.total_documents * 100) if self.total_documents > 0 else 0
        
        # Estimate time remaining
        if completed > 0:
            avg_time_per_doc = elapsed / completed
            remaining_docs = self.total_documents - completed
            estimated_remaining = avg_time_per_doc * remaining_docs
            logger.info(
                f"Progress: {completed}/{self.total_documents} documents "
                f"({percentage:.1f}%) - Elapsed: {elapsed:.1f}s, "
                f"Estimated remaining: {estimated_remaining:.1f}s"
            )
        else:
            logger.info(
                f"Progress: {completed}/{self.total_documents} documents "
                f"({percentage:.1f}%) - Elapsed: {elapsed:.1f}s"
            )

    def finish(self) -> None:
        """Mark batch as complete."""
        elapsed = time.time() - self.start_time
        logger.info(
            f"Completed: {self.description} - "
            f"{self.total_documents} documents in {elapsed:.1f}s"
        )


class LoggingDocumentProgressContext:
    """Fallback document progress context for non-interactive mode using logging."""

    def __init__(
        self,
        document_index: int,
        total_documents: int,
        document_name: str,
    ) -> None:
        """
        Initialize logging-based document progress context.
        
        Args:
            document_index: Index of current document (1-based)
            total_documents: Total number of documents
            document_name: Name/identifier for document
        """
        self.document_index = document_index
        self.total_documents = total_documents
        self.document_name = document_name
        self.current_stage = "pending"
        self.stage_start_time: dict[str, float] = {}
        logger.info(
            f"Processing document {document_index}/{total_documents}: {document_name}"
        )

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
        # Record stage duration
        if self.current_stage != "pending" and self.current_stage in self.stage_start_time:
            elapsed = time.time() - self.stage_start_time[self.current_stage]
            logger.debug(
                f"Document {self.document_index}/{self.total_documents} "
                f"({self.document_name}): Completed stage '{self.current_stage}' "
                f"in {elapsed:.2f}s"
            )
        
        self.current_stage = stage
        self.stage_start_time[stage] = time.time()
        logger.info(
            f"Document {self.document_index}/{self.total_documents} "
            f"({self.document_name}): {description}"
        )

    def finish(self) -> None:
        """Mark document processing as complete."""
        # Record final stage duration
        if self.current_stage in self.stage_start_time:
            elapsed = time.time() - self.stage_start_time[self.current_stage]
            logger.debug(
                f"Document {self.document_index}/{self.total_documents} "
                f"({self.document_name}): Completed stage '{self.current_stage}' "
                f"in {elapsed:.2f}s"
            )
        
        total_time = sum(
            time.time() - start
            for start in self.stage_start_time.values()
            if start is not None
        )
        logger.info(
            f"Document {self.document_index}/{self.total_documents} "
            f"({self.document_name}): Completed in {total_time:.2f}s"
        )

    def fail(self, error: str) -> None:
        """
        Mark document processing as failed.
        
        Args:
            error: Error message
        """
        logger.error(
            f"Document {self.document_index}/{self.total_documents} "
            f"({self.document_name}): Failed - {error}"
        )


class RichProgressReporterAdapter(ProgressReporterPort):
    """Rich-based progress reporter adapter."""

    def __init__(self) -> None:
        """Initialize Rich progress reporter."""
        # Detect non-interactive mode (non-TTY)
        self.is_interactive = sys.stdout.isatty()
        self.console = Console(file=sys.stdout if self.is_interactive else sys.stderr)
        self.progress: Progress | None = None
        self._progress_entered = False
        
        if not self.is_interactive:
            logger.info("Non-interactive mode detected - using structured logging for progress")

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
        if self.is_interactive:
            # Create and enter Progress context if not already done
            if self.progress is None:
                self.progress = Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=self.console,
                    expand=True,
                )
                self.progress.__enter__()
                self._progress_entered = True
            
            task_id = self.progress.add_task(
                description,
                total=total_documents,
            )
            return RichProgressContext(
                progress=self.progress,
                task_id=task_id,
                total_documents=total_documents,
            )
        else:
            return LoggingProgressContext(
                total_documents=total_documents,
                description=description,
            )

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
        if self.is_interactive and self.progress:
            # Create per-document progress task
            task_description = f"Document {document_index}/{total_documents}: {Path(document_name).name}"
            task_id = self.progress.add_task(
                task_description,
                total=4,  # 4 stages: converting, chunking, embedding, storing
            )
            return RichDocumentProgressContext(
                progress=self.progress,
                task_id=task_id,
                document_name=Path(document_name).name,
            )
        else:
            return LoggingDocumentProgressContext(
                document_index=document_index,
                total_documents=total_documents,
                document_name=document_name,
            )

    def display_summary(
        self,
        total_documents: int,
        chunks_created: int,
        duration_seconds: float,
        warnings: list[str],
        errors: list[str],
    ) -> None:
        """
        Display final summary after batch completion.
        
        Args:
            total_documents: Total documents processed
            chunks_created: Total chunks created
            duration_seconds: Total duration in seconds
            warnings: List of warning messages
            errors: List of error messages
        """
        from rich.table import Table
        from rich.panel import Panel
        
        summary_table = Table(title="Batch Import Summary", show_header=True, header_style="bold")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")
        
        summary_table.add_row("Documents Processed", str(total_documents))
        summary_table.add_row("Chunks Created", str(chunks_created))
        summary_table.add_row("Duration", f"{duration_seconds:.2f}s")
        
        if warnings:
            summary_table.add_row("Warnings", str(len(warnings)))
        if errors:
            summary_table.add_row("Errors", str(len(errors)))
        
        self.console.print(summary_table)
        
        # Display warnings and errors if any
        if warnings:
            warning_text = "\n".join(f"⚠️  {w}" for w in warnings[:10])  # Limit to 10
            if len(warnings) > 10:
                warning_text += f"\n... and {len(warnings) - 10} more warnings"
            self.console.print(Panel(warning_text, title="Warnings", border_style="yellow"))
        
        if errors:
            error_text = "\n".join(f"❌ {e}" for e in errors[:10])  # Limit to 10
            if len(errors) > 10:
                error_text += f"\n... and {len(errors) - 10} more errors"
            self.console.print(Panel(error_text, title="Errors", border_style="red"))
        
        # Also log summary for non-interactive mode
        logger.info(
            f"Batch import completed: {total_documents} documents, "
            f"{chunks_created} chunks, {duration_seconds:.2f}s"
        )
        if warnings:
            logger.warning(f"Batch import had {len(warnings)} warnings")
        if errors:
            logger.error(f"Batch import had {len(errors)} errors")

    def cleanup(self) -> None:
        """Clean up progress context (call when done)."""
        if self.progress and self._progress_entered:
            try:
                self.progress.__exit__(None, None, None)  # Stop progress context
                self._progress_entered = False
            except Exception:
                pass
            self.progress = None

