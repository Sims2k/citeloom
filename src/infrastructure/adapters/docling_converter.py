"""Docling converter adapter with optional import handling for Windows compatibility."""

from typing import Mapping, Any

try:
    import docling
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


class DoclingConverterAdapter:
    """Adapter for Docling document conversion (optional on Windows)."""

    def __init__(self):
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "Docling is not available on Windows (Python 3.12). "
                "deepsearch-glm dependency lacks Windows wheels for Python 3.12. "
                "Windows users should either:\n"
                "1. Use WSL (Windows Subsystem for Linux)\n"
                "2. Use Python 3.11 (not recommended - project requires 3.12)\n"
                "3. Wait for Windows support from docling/deepsearch-glm"
            )

    def convert(self, source_path: str) -> Mapping[str, Any]:
        """
        Convert a document at source_path into structured text and metadata.
        
        Args:
            source_path: Path to source document (PDF, etc.)
        
        Returns:
            ConversionResult-like dict with keys:
            - doc_id (str): Stable document identifier
            - structure (dict): heading_tree and page_map
            - plain_text (str, optional): Converted text
        
        Raises:
            ImportError: If docling is not available (Windows compatibility)
        """
        if not DOCLING_AVAILABLE:
            raise ImportError("Docling is not installed. See __init__ error for details.")
        
        # TODO: Replace with real Docling conversion implementation
        # from docling import DocumentConverter
        # converter = DocumentConverter()
        # result = converter.convert(source_path)
        # return {
        #     "doc_id": result.doc_id,
        #     "structure": {
        #         "heading_tree": result.heading_tree,
        #         "page_map": result.page_map,
        #     },
        #     "plain_text": result.plain_text,
        # }
        
        # Placeholder implementation
        return {
            "doc_id": f"hash_{source_path}",
            "structure": {
                "heading_tree": {},
                "page_map": {1: 0},
            },
            "plain_text": "Placeholder text - Docling conversion not yet implemented",
        }
