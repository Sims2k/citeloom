import hashlib
from dataclasses import dataclass, field


def generate_chunk_id(
    doc_id: str,
    page_span: tuple[int, int],
    section_path: list[str],
    embedding_model_id: str,
    chunk_idx: int,
) -> str:
    """
    Generate deterministic chunk ID from chunk attributes.
    
    The ID is derived from:
    - doc_id: Source document identifier
    - page_span or section_path: Location within document
    - embedding_model_id: Embedding model used (for versioning)
    - chunk_idx: Sequential chunk index within document
    
    Args:
        doc_id: Source document identifier
        page_span: Page span (start_page, end_page)
        section_path: Hierarchical section path (breadcrumb)
        embedding_model_id: Embedding model identifier
        chunk_idx: Sequential chunk index
    
    Returns:
        Deterministic chunk ID (SHA256 hash hex digest, truncated to 16 chars)
    """
    # Use section_path if available, otherwise use page_span
    location_key: str
    if section_path:
        location_key = "|".join(section_path)
    else:
        location_key = f"p{page_span[0]}-{page_span[1]}"
    
    # Create deterministic string representation
    components = [
        doc_id,
        location_key,
        embedding_model_id,
        str(chunk_idx),
    ]
    id_string = ":".join(components)
    
    # Generate SHA256 hash and truncate to 16 characters for readability
    hash_obj = hashlib.sha256(id_string.encode("utf-8"))
    return hash_obj.hexdigest()[:16]


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
        token_count: Token count according to embedding model's tokenizer (optional)
        signal_to_noise_ratio: Quality metric (≥ 0.3 threshold) (optional)
    """
    
    id: str
    doc_id: str
    text: str
    page_span: tuple[int, int]
    section_heading: str | None = None
    section_path: list[str] = field(default_factory=list)
    chunk_idx: int = 0
    token_count: int | None = None
    signal_to_noise_ratio: float | None = None
    
    def __post_init__(self) -> None:
        """Validate chunk data."""
        if self.page_span[0] > self.page_span[1]:
            raise ValueError(f"Invalid page span: start ({self.page_span[0]}) > end ({self.page_span[1]})")
        if self.chunk_idx < 0:
            raise ValueError(f"chunk_idx must be >= 0, got {self.chunk_idx}")
        if self.signal_to_noise_ratio is not None and self.signal_to_noise_ratio < 0.0:
            raise ValueError(
                f"signal_to_noise_ratio must be >= 0.0 if provided, got {self.signal_to_noise_ratio}"
            )

