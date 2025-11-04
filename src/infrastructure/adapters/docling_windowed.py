"""Windowed conversion support for large documents using Docling page ranges."""

import json
import logging
from pathlib import Path
from typing import Any, Generator

from .docling_converter import DoclingConverterAdapter

logger = logging.getLogger(__name__)


class WindowedConversionResult:
    """Result of windowed conversion with checkpoint information."""
    
    def __init__(
        self,
        window_num: int,
        start_page: int,
        end_page: int,
        conversion_result: dict[str, Any],
        total_pages: int,
    ):
        self.window_num = window_num
        self.start_page = start_page
        self.end_page = end_page
        self.conversion_result = conversion_result
        self.total_pages = total_pages
        self.progress_pct = (end_page / total_pages * 100) if total_pages > 0 else 0.0


def convert_windowed(
    converter: DoclingConverterAdapter,
    source_path: str,
    window_size: int = 10,
    start_page: int = 1,
    end_page: int | None = None,
    ocr_languages: list[str] | None = None,
    checkpoint_path: Path | None = None,
) -> Generator[WindowedConversionResult, None, None]:
    """
    Convert a document in page windows, yielding results for each window.
    
    This enables processing very large documents (>1000 pages) without timeouts
    by processing in smaller chunks (10-30 pages per window).
    
    Args:
        converter: DoclingConverterAdapter instance
        source_path: Path to source document
        window_size: Number of pages per window (default: 10, recommended: 10-30)
        start_page: Starting page number (1-indexed, default: 1)
        end_page: Ending page number (1-indexed, None = process to end)
        ocr_languages: Optional OCR language codes
        checkpoint_path: Optional path to save checkpoint after each window
    
    Yields:
        WindowedConversionResult for each window containing:
        - window_num: Window number (1-indexed)
        - start_page: First page in window
        - end_page: Last page in window
        - conversion_result: Standard Docling conversion result dict
        - total_pages: Total pages in document
        - progress_pct: Progress percentage (0-100)
    
    Example:
        >>> converter = DoclingConverterAdapter(...)
        >>> for window_result in convert_windowed(converter, "large.pdf", window_size=10):
        ...     chunks = chunker.chunk(window_result.conversion_result, policy)
        ...     # Process chunks for this window...
    """
    # Get total page count (simplified - would need PDF parsing in production)
    # For now, we'll estimate or require end_page to be provided
    total_pages = end_page if end_page is not None else _estimate_page_count(source_path)
    
    if total_pages == 0:
        logger.warning(f"Could not determine page count for {source_path}. Processing single window.")
        total_pages = 1
    
    current_page = start_page
    window_num = 1
    
    logger.info(
        f"Starting windowed conversion: {source_path}",
        extra={
            "source_path": source_path,
            "window_size": window_size,
            "start_page": start_page,
            "end_page": end_page,
            "total_pages": total_pages,
        },
    )
    
    while current_page <= total_pages:
        window_end = min(current_page + window_size - 1, total_pages)
        page_range = (current_page, window_end)
        
        logger.info(
            f"Processing window {window_num}: pages {current_page}-{window_end}",
            extra={
                "window_num": window_num,
                "start_page": current_page,
                "end_page": window_end,
                "total_pages": total_pages,
            },
        )
        
        try:
            # Convert this window
            conversion_result = converter.convert(
                source_path=source_path,
                ocr_languages=ocr_languages,
                page_range=page_range,
            )
            
            # Create window result
            window_result = WindowedConversionResult(
                window_num=window_num,
                start_page=current_page,
                end_page=window_end,
                conversion_result=conversion_result,
                total_pages=total_pages,
            )
            
            # Save checkpoint if requested
            if checkpoint_path:
                _save_checkpoint(
                    checkpoint_path=checkpoint_path,
                    source_path=source_path,
                    last_processed_page=window_end,
                    total_pages=total_pages,
                    window_num=window_num,
                )
            
            yield window_result
            
            # Move to next window
            current_page = window_end + 1
            window_num += 1
            
        except Exception as e:
            logger.error(
                f"Window {window_num} conversion failed: {e}",
                extra={
                    "window_num": window_num,
                    "start_page": current_page,
                    "end_page": window_end,
                    "source_path": source_path,
                },
                exc_info=True,
            )
            raise
    
    logger.info(
        f"Windowed conversion complete: {window_num - 1} windows processed",
        extra={"source_path": source_path, "total_windows": window_num - 1},
    )


def _estimate_page_count(source_path: str) -> int:
    """
    Estimate page count for a PDF file.
    
    This is a simplified implementation. In production, use PyPDF2 or similar.
    """
    try:
        import PyPDF2
        with open(source_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            return len(pdf_reader.pages)
    except Exception:
        # Fallback: return 0 (will trigger single-window processing)
        logger.warning(f"Could not determine page count for {source_path}")
        return 0


def _save_checkpoint(
    checkpoint_path: Path,
    source_path: str,
    last_processed_page: int,
    total_pages: int,
    window_num: int,
) -> None:
    """Save checkpoint information to resume processing later."""
    checkpoint_data = {
        "source_path": str(source_path),
        "last_processed_page": last_processed_page,
        "total_pages": total_pages,
        "windows_processed": window_num,
        "timestamp": _get_timestamp(),
    }
    
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)
    
    logger.debug(
        f"Checkpoint saved: page {last_processed_page}/{total_pages}",
        extra={"checkpoint_path": str(checkpoint_path), "last_page": last_processed_page},
    )


def load_checkpoint(checkpoint_path: Path) -> dict[str, Any] | None:
    """
    Load checkpoint information to resume processing.
    
    Returns:
        Checkpoint dict with keys: source_path, last_processed_page, total_pages, windows_processed
        Returns None if checkpoint doesn't exist or is invalid
    """
    if not checkpoint_path.exists():
        return None
    
    try:
        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)
        return checkpoint
    except Exception as e:
        logger.warning(f"Failed to load checkpoint: {e}", extra={"checkpoint_path": str(checkpoint_path)})
        return None


def _get_timestamp() -> str:
    """Get ISO format timestamp."""
    from datetime import datetime
    return datetime.utcnow().isoformat() + 'Z'

