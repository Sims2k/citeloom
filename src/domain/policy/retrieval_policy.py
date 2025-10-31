from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalPolicy:
    """Policy for chunk retrieval with project filtering and hybrid search."""
    
    top_k: int = 6
    hybrid_enabled: bool = True
    min_score: float = 0.0
    require_project_filter: bool = True
    max_chars_per_chunk: int = 1800
