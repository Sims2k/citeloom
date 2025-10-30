from __future__ import annotations

from ..dto.query import QueryRequest, QueryResult, QueryResultItem
from ..ports.vector_index import VectorIndexPort
from ..ports.embeddings import EmbeddingPort


def query_chunks(
    request: QueryRequest,
    embedder: EmbeddingPort,
    index: VectorIndexPort,
) -> QueryResult:
    # Dense path
    query_vec = embedder.embed([request.query_text], model_id="default")[0]
    dense_hits = list(index.search(query_vec, project_id=request.project_id, top_k=request.top_k))

    hits = dense_hits
    if request.hybrid:
        # Naive sparse path: score by substring overlap length as a placeholder
        def sparse_score(text: str) -> float:
            q = request.query_text.lower()
            t = (text or "").lower()
            return float(len(q)) if q in t else 0.0

        # Fetch some more from index (reuse dense result set here for stubbed adapter)
        combined = []
        for h in dense_hits:
            s = sparse_score(h.get("text", ""))
            combined.append({**h, "score": float(h.get("score", 0.0)) + s})
        combined.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        hits = combined[: request.top_k]
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
