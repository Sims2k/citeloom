from __future__ import annotations

import logging

from ...domain.errors import HybridNotSupported, ProjectNotFound
from ...domain.policy.retrieval_policy import RetrievalPolicy
from ..dto.query import QueryRequest, QueryResult, QueryResultItem
from ..ports.vector_index import VectorIndexPort
from ..ports.embeddings import EmbeddingPort

logger = logging.getLogger(__name__)


def query_chunks(
    request: QueryRequest,
    embedder: EmbeddingPort,
    index: VectorIndexPort,
    policy: RetrievalPolicy | None = None,
) -> QueryResult:
    """
    Query chunks with project filtering, top_k limit, text trimming, and retrieval policy.
    
    Args:
        request: QueryRequest with project_id, query_text, top_k, hybrid, filters
        embedder: EmbeddingPort for generating query embeddings
        index: VectorIndexPort for vector/hybrid search
        policy: Optional RetrievalPolicy for filtering and trimming (defaults to policy from request)
    
    Returns:
        QueryResult with trimmed chunk items and citation metadata
    
    Raises:
        ProjectNotFound: If project collection doesn't exist
        HybridNotSupported: If hybrid search requested but not enabled for project
    """
    # Use provided policy or default policy
    if policy is None:
        policy = RetrievalPolicy(
            top_k=request.top_k,
            hybrid_enabled=request.hybrid,
            max_chars_per_chunk=1800,  # Default from domain policy
            require_project_filter=True,
            min_score=0.0,
        )
    
    # Enforce project filter (mandatory per policy)
    if not request.project_id:
        raise ValueError("project_id is required")
    
    # Enforce top_k limit from policy
    effective_top_k = min(request.top_k, policy.top_k)
    
    # Generate query embedding
    try:
        query_vec = embedder.embed([request.query_text], model_id=None)[0]
    except Exception as e:
        logger.error(f"Failed to generate query embedding: {e}", exc_info=True)
        raise
    
    # Perform search (vector or hybrid)
    try:
        if request.hybrid and policy.hybrid_enabled:
            # Hybrid search: full-text + vector fusion
            hits = index.hybrid_query(
                query_text=request.query_text,
                query_vector=query_vec,
                project_id=request.project_id,
                top_k=effective_top_k,
                filters=request.filters,
            )
        else:
            # Dense-only vector search
            if request.hybrid and not policy.hybrid_enabled:
                raise HybridNotSupported(
                    project_id=request.project_id,
                    reason="hybrid_enabled=False in retrieval policy",
                )
            hits = index.search(
                query_vector=query_vec,
                project_id=request.project_id,
                top_k=effective_top_k,
                filters=request.filters,
            )
    except ProjectNotFound:
        raise
    except HybridNotSupported:
        raise
    except Exception as e:
        logger.error(
            f"Search failed for project '{request.project_id}': {e}",
            extra={"project_id": request.project_id},
            exc_info=True,
        )
        raise ProjectNotFound(request.project_id) from e
    
    # Process hits into QueryResultItems with text trimming and citation metadata
    items: list[QueryResultItem] = []
    for hit in hits:
        # Extract payload (Qdrant returns payload at hit["payload"])
        payload = hit.get("payload", {})
        
        # Extract text and trim to max_chars_per_chunk
        text = payload.get("fulltext", hit.get("text", ""))
        if isinstance(text, str):
            if len(text) > policy.max_chars_per_chunk:
                text = text[: policy.max_chars_per_chunk].rsplit(" ", 1)[0] + "..."
        
        # Extract page span from doc payload
        doc_payload = payload.get("doc", {})
        page_span_raw = doc_payload.get("page_span", hit.get("page_span"))
        page_span: tuple[int, int] | None = None
        if page_span_raw:
            if isinstance(page_span_raw, (list, tuple)) and len(page_span_raw) == 2:
                try:
                    page_span = (int(page_span_raw[0]), int(page_span_raw[1]))
                except (ValueError, TypeError):
                    page_span = None
        
        # Extract section information
        section_heading = doc_payload.get("section_heading", payload.get("section"))
        section_path_raw = doc_payload.get("section_path", [])
        section_path: list[str] | None = None
        if section_path_raw and isinstance(section_path_raw, list):
            section_path = [str(s) for s in section_path_raw if s]
        
        # Extract citation metadata from zotero payload
        zotero_payload = payload.get("zotero", {})
        citekey = zotero_payload.get("citekey") if zotero_payload else None
        doi = zotero_payload.get("doi") if zotero_payload else None
        url = zotero_payload.get("url") if zotero_payload else None
        
        # Apply min_score filter from policy
        score = float(hit.get("score", 0.0))
        if score < policy.min_score:
            continue
        
        items.append(
            QueryResultItem(
                text=text,
                score=score,
                citekey=citekey,
                section=section_heading,
                page_span=page_span,
                section_path=section_path,
                doi=doi,
                url=url,
            )
        )
    
    # Limit to top_k (already enforced, but ensure)
    items = items[:effective_top_k]
    
    logger.info(
        f"Query completed: {len(items)} results for project '{request.project_id}'",
        extra={
            "project_id": request.project_id,
            "query_text": request.query_text[:50],  # Truncate for logging
            "result_count": len(items),
            "hybrid": request.hybrid,
        },
    )
    
    return QueryResult(items=items)
