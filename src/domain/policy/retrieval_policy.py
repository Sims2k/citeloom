from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalPolicy:
    top_k: int = 6
    hybrid: bool = True
    project_filter_required: bool = True
