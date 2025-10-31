from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConversionResult:
    """
    Structured output of document conversion with structure and text.
    
    Fields:
        doc_id: Stable document identifier (content hash or file path hash)
        structure: Document structure with heading_tree and page_map
        plain_text: Converted plain text content (optional)
        ocr_languages: OCR languages used during conversion (if OCR was performed) (optional)
    """
    
    doc_id: str
    structure: dict[str, Any]
    plain_text: str | None = None
    ocr_languages: list[str] | None = None
    
    def __post_init__(self) -> None:
        """Validate structure contains required keys."""
        if "heading_tree" not in self.structure:
            raise ValueError("structure must contain 'heading_tree'")
        if "page_map" not in self.structure:
            raise ValueError("structure must contain 'page_map'")

