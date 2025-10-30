from __future__ import annotations

from ..dto.query import QueryRequest, QueryResult, QueryResultItem
from ..ports.vector_index import VectorIndexPort
from ..ports.embeddings import EmbeddingPort


def query_chunks(
    request: QueryRequest,
    embedder: EmbeddingPort,
    index: VectorIndexPort,
) -> QueryResult:
    # For now dense-only; hybrid path handled later (Phase F)
    query_vec = embedder.embed([request.query_text], model_id="default")[0]
    hits = index.search(query_vec, project_id=request.project_id, top_k=request.top_k)
    items = []
    for h in hits:
        span = h.get("page_span")
        if isinstance(span, (list, tuple)) and len(span) == 2:
            page_span = (int(span[0]), int(span[1]))
        else:
            page_span = None
        items.append(
            QueryResultItem(
                text=h.get("text", ""),
                score=float(h.get("score", 0.0)),
                citekey=h.get("citation", {}).get("citekey") if h.get("citation") else None,
                section=h.get("section"),
                page_span=page_span,
            )
        )
    return QueryResult(items=items)
