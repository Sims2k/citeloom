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
    """
    
    citekey: str
    title: str
    authors: list[str]
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    collections: list[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Validate citation metadata."""
        if not self.authors:
            raise ValueError("authors must be non-empty list")
        if not (self.doi or self.url):
            raise ValueError("Either doi or url must be provided")
        if self.year is not None and self.year <= 0:
            raise ValueError(f"year must be positive integer if provided, got {self.year}")

