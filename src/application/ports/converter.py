from typing import Protocol, runtime_checkable, Mapping, Any


@runtime_checkable
class TextConverterPort(Protocol):
    def convert(
        self,
        source_path: str,
        ocr_languages: list[str] | None = None,
    ) -> Mapping[str, Any]:
        """
        Convert a document at source_path into structured text and metadata.
        
        Args:
            source_path: Path to source document (PDF, DOCX, PPTX, HTML, images)
            ocr_languages: Optional OCR language codes (default: ['en', 'de'] or from Zotero metadata)
        
        Returns:
            ConversionResult-like dict with keys:
            - doc_id (str): Stable document identifier
            - structure (dict): heading_tree (hierarchical with page anchors) and page_map (page → (start_offset, end_offset))
            - plain_text (str, optional): Converted text (normalized, hyphen-repaired)
            - ocr_languages (list[str], optional): Languages used for OCR
        
        Raises:
            DocumentConversionError: If document cannot be converted
            TimeoutError: If conversion exceeds timeout (120s document, 10s per-page)
        """
        ...
