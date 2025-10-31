from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chunk:
    """
    Semantically meaningful segment of a document with structure and citation metadata.
    
    Fields:
        id: Deterministic chunk identifier
        doc_id: Source document identifier
        text: Chunk text content
        page_span: Page span (start_page, end_page)
        section_heading: Immediate section heading containing this chunk (optional)
        section_path: Hierarchical section path (breadcrumb from root to current section)
        chunk_idx: Sequential chunk index within document
    """
    
    id: str
    doc_id: str
    text: str
    page_span: tuple[int, int]
    section_heading: str | None = None
    section_path: list[str] = field(default_factory=list)
    chunk_idx: int = 0
    
    def __post_init__(self) -> None:
        """Validate chunk data."""
        if self.page_span[0] > self.page_span[1]:
            raise ValueError(f"Invalid page span: start ({self.page_span[0]}) > end ({self.page_span[1]})")
        if self.chunk_idx < 0:
            raise ValueError(f"chunk_idx must be >= 0, got {self.chunk_idx}")

