from dataclasses import dataclass, field


@dataclass(frozen=True)
class CitationMeta:
    """
    Bibliographic metadata for a document, extracted from Zotero CSL-JSON.
    
    Fields:
        citekey: Citation key from Better BibTeX (e.g., 'cleanArchitecture2023')
        title: Document title
        authors: List of author names
        year: Publication year (optional)
        doi: DOI identifier (optional)
        url: URL if DOI not available (optional)
        tags: Tags from Zotero collection
        collections: Collection names from Zotero
        language: Language code from Zotero metadata (e.g., 'en', 'de', 'en-US') - used for OCR language selection (optional)
    """
    
    citekey: str
    title: str
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)
    language: str | None = None
    
    def __post_init__(self) -> None:
        """Validate citation metadata."""
        if not self.authors:
            raise ValueError("authors must be non-empty list")
        # Note: doi or url is optional for metadata resolution (may be missing from Zotero)
        # Validation removed to allow graceful handling of incomplete metadata
        if self.year is not None and self.year <= 0:
            raise ValueError(f"year must be positive integer if provided, got {self.year}")

