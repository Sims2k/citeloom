"""Helper functions for windowed conversion detection and page counting."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def should_use_windowed_conversion(
    source_path: str | Path,
    enable_windowed: bool = True,
    force_windowed: bool = False,
    page_threshold: int = 1000,
) -> bool:
    """
    Determine if a document should use windowed conversion.
    
    Args:
        source_path: Path to document file
        enable_windowed: Whether windowed conversion is enabled (from settings)
        force_windowed: Force windowed conversion regardless of page count (manual override)
        page_threshold: Minimum page count to trigger windowed conversion (default: 1000)
    
    Returns:
        True if windowed conversion should be used, False otherwise
    """
    # Force windowed conversion if explicitly requested (manual override)
    if force_windowed:
        logger.info(
            f"Windowed conversion forced (manual override) for: {source_path}",
            extra={"source_path": str(source_path), "force_windowed": True},
        )
        return True
    
    if not enable_windowed:
        return False
    
    source_path_obj = Path(source_path)
    
    # Only PDFs are supported for windowed conversion currently
    if source_path_obj.suffix.lower() != '.pdf':
        return False
    
    # Check if file exists
    if not source_path_obj.exists():
        logger.warning(f"Document not found for page count check: {source_path}")
        return False
    
    # Get page count
    try:
        page_count = get_pdf_page_count(source_path_obj)
        if page_count >= page_threshold:
            logger.info(
                f"Document has {page_count} pages, using windowed conversion (threshold: {page_threshold})",
                extra={"source_path": str(source_path), "page_count": page_count, "threshold": page_threshold},
            )
            return True
        return False
    except Exception as e:
        logger.warning(
            f"Could not determine page count for {source_path}: {e}. Using standard conversion.",
            extra={"source_path": str(source_path)},
        )
        return False


def get_pdf_page_count(source_path: Path) -> int:
    """
    Get the total number of pages in a PDF file.
    
    Args:
        source_path: Path to PDF file
    
    Returns:
        Number of pages in the PDF
    
    Raises:
        ImportError: If PyPDF2 is not available
        Exception: If page count cannot be determined
    """
    try:
        import PyPDF2
        with open(source_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            return len(pdf_reader.pages)
    except ImportError:
        raise ImportError(
            "PyPDF2 is required for page count detection. "
            "Install it with: uv add PyPDF2"
        )
    except Exception as e:
        raise Exception(f"Failed to get page count for {source_path}: {e}") from e

