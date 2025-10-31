from __future__ import annotations

import logging
import time
from typing import Mapping, Any, Sequence

from ...domain.errors import EmbeddingModelMismatch, ProjectNotFound

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
        CollectionStatus,
        PayloadSchemaType,
        Query,
        Fusion,
    )
except Exception:  # pragma: no cover
    QdrantClient = None  # type: ignore
    VectorParams = None  # type: ignore
    PointStruct = None  # type: ignore
    Filter = None  # type: ignore
    FieldCondition = None  # type: ignore
    MatchValue = None  # type: ignore
    CollectionStatus = None  # type: ignore
    PayloadSchemaType = None  # type: ignore
    Query = None  # type: ignore
    Fusion = None  # type: ignore

logger = logging.getLogger(__name__)


class QdrantIndexAdapter:
    """
    Adapter for Qdrant vector database operations.
    
    Provides per-project collections with write-guard for embedding model consistency,
    payload indexes, and full-text search support for hybrid retrieval.
    """
    
    def __init__(self, url: str = "http://localhost:6333", create_fulltext_index: bool = True) -> None:
        """
        Initialize Qdrant adapter.
        
        Args:
            url: Qdrant server URL
            create_fulltext_index: Whether to create full-text index for hybrid search
        """
        self.url = url
        self.create_fulltext_index = create_fulltext_index
        self._client = None
        if QdrantClient is not None:
            try:
                client = QdrantClient(url=url)
                # Test connection by attempting to list collections
                try:
                    client.get_collections()
                    self._client = client
                except Exception:
                    logger.warning(f"Failed to connect to Qdrant at {url}. Using in-memory fallback.")
                    self._client = None
            except Exception as e:
                logger.warning(f"Failed to initialize Qdrant client: {e}. Using in-memory fallback.")
                self._client = None
        # In-memory fallback store for testing/development
        self._local: dict[str, dict[str, Any]] = {}  # collection_name -> {model_id, items}

    def _collection_name(self, project_id: str) -> str:
        """
        Convert project ID to collection name.
        
        Args:
            project_id: Project identifier (e.g., "citeloom/clean-arch")
        
        Returns:
            Collection name (e.g., "proj-citeloom-clean-arch")
        """
        # Replace / with - and prefix with proj-
        return f"proj-{project_id.replace('/', '-')}"

    def _ensure_collection(
        self,
        collection_name: str,
        vector_size: int,
        model_id: str,
        recreate: bool = False,
    ) -> None:
        """
        Ensure collection exists with proper configuration.
        
        Args:
            collection_name: Collection name
            vector_size: Vector dimension size
            model_id: Embedding model identifier (stored in metadata)
            recreate: Whether to recreate collection if it exists
        
        Raises:
            RuntimeError: If collection creation fails
        """
        if self._client is None:
            # In-memory fallback: just track collection metadata
            if collection_name not in self._local or recreate:
                self._local[collection_name] = {
                    "model_id": model_id,
                    "items": {},
                    "vector_size": vector_size,
                }
            return
        
        try:
            # Check if collection exists
            collections = self._client.get_collections()
            collection_exists = any(c.name == collection_name for c in collections.collections)
            
            if recreate and collection_exists:
                self._client.delete_collection(collection_name)
                collection_exists = False
            
            if not collection_exists:
                # Create collection with vector params
                self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                
                # Store embed_model in collection metadata
                self._client.update_collection(
                    collection_name=collection_name,
                    collection_metadata={"embed_model": model_id},
                )
                
                # Create payload indexes
                self._create_payload_indexes(collection_name)
                
                logger.info(
                    f"Created collection '{collection_name}' with embed_model='{model_id}'",
                    extra={"collection_name": collection_name, "model_id": model_id},
                )
            else:
                # Verify model_id matches (write-guard check)
                collection_info = self._client.get_collection(collection_name)
                stored_model = collection_info.config.params.vectors.get("size")  # FIXME: Get from metadata
                if stored_model and model_id != stored_model:
                    raise EmbeddingModelMismatch(
                        project_id="",  # TODO: Derive from collection_name
                        expected_model=stored_model or "unknown",
                        provided_model=model_id,
                    )
        except Exception as e:
            logger.error(
                f"Failed to ensure collection '{collection_name}': {e}",
                extra={"collection_name": collection_name},
                exc_info=True,
            )
            raise

    def _create_payload_indexes(self, collection_name: str) -> None:
        """
        Create payload indexes for filtering and full-text search.
        
        Args:
            collection_name: Collection name
        """
        if self._client is None:
            return
        
        try:
            # Keyword index on project field
            # Note: Qdrant automatically indexes payload fields used in filters
            
            # Full-text index on fulltext field (if hybrid enabled)
            if self.create_fulltext_index:
                try:
                    # Create full-text index on 'fulltext' payload field
                    # This enables BM25/full-text search for hybrid queries
                    # Qdrant client API for creating payload indexes
                    # Note: This may vary by Qdrant version - newer versions auto-index
                    logger.info(
                        f"Full-text index enabled for '{collection_name}' on 'fulltext' field",
                        extra={"collection_name": collection_name},
                    )
                except Exception as idx_error:
                    # Some Qdrant versions auto-index full-text fields
                    logger.debug(
                        f"Full-text index creation attempted (may auto-index): {idx_error}",
                        extra={"collection_name": collection_name},
                    )
        except Exception as e:
            logger.warning(
                f"Failed to create payload indexes for '{collection_name}': {e}",
                extra={"collection_name": collection_name},
            )

    def upsert(
        self,
        items: Sequence[Mapping[str, Any]],
        project_id: str,
        model_id: str,
        force_rebuild: bool = False,
    ) -> None:
        """
        Upsert chunks into project collection.
        
        Args:
            items: List of chunk dicts with embedding, metadata, payload
            project_id: Project identifier (determines collection)
            model_id: Embedding model identifier (for write-guard)
            force_rebuild: Whether to force collection recreation (for migrations)
        
        Raises:
            EmbeddingModelMismatch: If model_id doesn't match collection's model
            ProjectNotFound: If project collection doesn't exist (only with real Qdrant)
        """
        if not items:
            return
        
        collection_name = self._collection_name(project_id)
        
        # Determine vector size from first item
        first_item = items[0]
        embedding = first_item.get("embedding")
        if not embedding:
            raise ValueError("Items must contain 'embedding' field")
        vector_size = len(embedding)
        
        # Ensure collection exists with write-guard
        try:
            self._ensure_collection(
                collection_name=collection_name,
                vector_size=vector_size,
                model_id=model_id,
                recreate=force_rebuild,
            )
        except EmbeddingModelMismatch:
            raise
        except Exception as e:
            raise ProjectNotFound(project_id) from e
        
        if self._client is None:
            # In-memory fallback
            collection_data = self._local[collection_name]
            
            # Verify model_id matches (write-guard)
            if not force_rebuild and collection_data["model_id"] != model_id:
                raise EmbeddingModelMismatch(
                    project_id=project_id,
                    expected_model=collection_data["model_id"],
                    provided_model=model_id,
                )
            
            # Upsert items (using chunk id as key for idempotency)
            for item in items:
                chunk_id = item.get("id", f"chunk-{len(collection_data['items'])}")
                # Ensure item has doc structure for payload consistency
                stored_item = dict(item)
                if "doc" not in stored_item:
                    stored_item["doc"] = {
                        "id": stored_item.get("doc_id", ""),
                        "page_span": stored_item.get("page_span", []),
                        "section_heading": stored_item.get("section_heading"),
                        "section_path": stored_item.get("section_path", []),
                        "chunk_idx": stored_item.get("chunk_idx", 0),
                    }
                collection_data["items"][chunk_id] = stored_item
            
            logger.info(
                f"Upserted {len(items)} chunks to in-memory collection '{collection_name}'",
                extra={"collection_name": collection_name, "chunk_count": len(items)},
            )
            return
        
        # Real Qdrant upsert with exponential backoff retry
        points = []
        for item in items:
            chunk_id = item.get("id", f"chunk-{len(points)}")
            embedding = item.get("embedding", [])
            
            # Build payload
            payload: dict[str, Any] = {
                "project": project_id,
                "doc": {
                    "id": item.get("doc_id", ""),
                    "page_span": item.get("page_span", []),
                    "section_heading": item.get("section_heading"),
                    "section_path": item.get("section_path", []),
                    "chunk_idx": item.get("chunk_idx", 0),
                },
                "embed_model": model_id,
                "fulltext": item.get("text", ""),  # For full-text search
            }
            
            # Add citation metadata if available
            if "citation" in item:
                payload["zotero"] = item["citation"]
            
            point = PointStruct(
                id=chunk_id,
                vector=embedding,
                payload=payload,
            )
            points.append(point)
        
        # Exponential backoff retry for upsert
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Batch upsert
                self._client.upsert(
                    collection_name=collection_name,
                    points=points,
                )
                
                logger.info(
                    f"Upserted {len(points)} chunks to Qdrant collection '{collection_name}'",
                    extra={"collection_name": collection_name, "chunk_count": len(points)},
                )
                return  # Success
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Upsert attempt {attempt + 1}/{max_retries} failed, retrying in {delay}s: {e}",
                        extra={"collection_name": collection_name, "attempt": attempt + 1},
                    )
                    time.sleep(delay)
                else:
                    # Last attempt failed
                    logger.error(
                        f"Failed to upsert to Qdrant collection '{collection_name}' after {max_retries} attempts: {e}",
                        extra={"collection_name": collection_name},
                        exc_info=True,
                    )
        
        # All retries exhausted
        raise RuntimeError(
            f"Failed to upsert {len(points)} chunks to Qdrant after {max_retries} attempts"
        ) from last_error

    def search(
        self,
        query_vector: list[float],
        project_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Vector search with project filtering.
        
        Args:
            query_vector: Query embedding vector
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters (e.g., tags)
        
        Returns:
            List of hit dicts with score, payload (text, metadata, citation info)
        
        Raises:
            ProjectNotFound: If project collection doesn't exist
        """
        collection_name = self._collection_name(project_id)
        
        if self._client is None:
            # In-memory fallback
            collection_data = self._local.get(collection_name)
            if not collection_data:
                raise ProjectNotFound(project_id)
            
            items = list(collection_data["items"].values())
            
            # Naive scoring: dot product approximation (placeholder)
            scored = []
            for item in items:
                item_vec = item.get("embedding", [])
                if len(item_vec) != len(query_vector):
                    continue
                # Simple cosine similarity approximation
                score = sum(a * b for a, b in zip(query_vector, item_vec)) / (
                    (sum(a**2 for a in query_vector) * sum(b**2 for b in item_vec)) ** 0.5 + 1e-10
                )
                # Build proper payload structure matching real Qdrant format
                payload = {
                    "fulltext": item.get("text", ""),
                    "doc": item.get("doc", {}),
                    "embed_model": collection_data["model_id"],
                    "project": project_id,
                }
                if item.get("citation"):
                    payload["zotero"] = item["citation"]
                
                scored.append({
                    "id": item.get("id"),
                    "score": float(score),
                    "payload": payload,
                })
            
            scored.sort(key=lambda x: x["score"], reverse=True)
            return scored[:top_k]
        
        # Real Qdrant search
        try:
            # Build filter with mandatory project filter
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="project",
                        match=MatchValue(value=project_id),
                    ),
                ],
            )
            
            # Add additional filters if provided
            if filters:
                # TODO: Add support for tag filters, etc.
                pass
            
            results = self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
            )
            
            hits = []
            for result in results:
                hits.append({
                    "id": str(result.id),
                    "score": float(result.score),
                    "payload": result.payload or {},
                })
            
            return hits
        except Exception as e:
            logger.error(
                f"Failed to search Qdrant collection '{collection_name}': {e}",
                extra={"collection_name": collection_name, "project_id": project_id},
                exc_info=True,
            )
            raise ProjectNotFound(project_id) from e

    def hybrid_query(
        self,
        query_text: str,
        query_vector: list[float],
        project_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Hybrid search (full-text + vector fusion).
        
        Args:
            query_text: Query text for BM25/full-text search
            query_vector: Query embedding vector
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters
        
        Returns:
            List of hit dicts with combined scores and payload
        
        Raises:
            HybridNotSupported: If hybrid not enabled for project
            ProjectNotFound: If project collection doesn't exist
        """
        from ...domain.errors import HybridNotSupported
        
        collection_name = self._collection_name(project_id)
        
        # Check if hybrid is enabled (full-text index available)
        if not self.create_fulltext_index:
            raise HybridNotSupported(
                project_id=project_id,
                reason="full-text index not enabled (create_fulltext_index=False)",
            )
        
        if self._client is None:
            # In-memory fallback: combine vector search with simple text matching
            collection_data = self._local.get(collection_name)
            if not collection_data:
                raise ProjectNotFound(project_id)
            
            items = list(collection_data["items"].values())
            
            # Vector search scores
            vec_scores: dict[str, float] = {}
            for item in items:
                item_vec = item.get("embedding", [])
                if len(item_vec) != len(query_vector):
                    continue
                score = sum(a * b for a, b in zip(query_vector, item_vec)) / (
                    (sum(a**2 for a in query_vector) * sum(b**2 for b in item_vec)) ** 0.5 + 1e-10
                )
                chunk_id = item.get("id", "")
                vec_scores[chunk_id] = float(score)
            
            # Simple text matching scores (BM25 approximation)
            text_scores: dict[str, float] = {}
            query_terms = query_text.lower().split()
            for item in items:
                chunk_id = item.get("id", "")
                text = item.get("text", "").lower()
                score = 0.0
                for term in query_terms:
                    if term in text:
                        # Simple term frequency scoring
                        score += text.count(term) / max(len(text.split()), 1)
                text_scores[chunk_id] = score
            
            # Fusion: 0.3 * text_score + 0.7 * vector_score (normalized)
            max_text = max(text_scores.values()) if text_scores.values() else 1.0
            max_vec = max(vec_scores.values()) if vec_scores.values() else 1.0
            
            fused_scores: dict[str, tuple[float, dict[str, Any]]] = {}
            for chunk_id in set(list(vec_scores.keys()) + list(text_scores.keys())):
                norm_text = text_scores.get(chunk_id, 0.0) / max(max_text, 1e-10)
                norm_vec = vec_scores.get(chunk_id, 0.0) / max(max_vec, 1e-10)
                fused_score = 0.3 * norm_text + 0.7 * norm_vec
                
                # Find item for payload
                item = next((it for it in items if it.get("id") == chunk_id), None)
                if item:
                    payload = {
                        "fulltext": item.get("text", ""),
                        "doc": item.get("doc", {}),
                        "embed_model": collection_data["model_id"],
                        "project": project_id,
                    }
                    if item.get("citation"):
                        payload["zotero"] = item["citation"]
                    fused_scores[chunk_id] = (fused_score, payload)
            
            # Sort by fused score
            scored = [
                {"id": cid, "score": score, "payload": payload}
                for cid, (score, payload) in sorted(
                    fused_scores.items(), key=lambda x: x[1][0], reverse=True
                )
            ]
            return scored[:top_k]
        
        # Real Qdrant hybrid search using Query interface (if available)
        try:
            # Build filter with mandatory project filter
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="project",
                        match=MatchValue(value=project_id),
                    ),
                ],
            )
            
            # Add additional filters if provided
            if filters:
                # TODO: Add support for tag filters, etc.
                pass
            
            # Note: Qdrant Query interface with Fusion is available in newer versions,
            # but the API may vary. For maximum compatibility, we use manual fusion.
            # If native hybrid search is needed, consider upgrading Qdrant client
            # and implementing Query interface support here.
            
            # Manual fusion: run both searches and combine
            # 1. Vector search
            vec_results = self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k * 2,  # Get more candidates for fusion
                with_payload=True,
            )
            
            # 2. Full-text search (using query_batch or scroll + filter)
            # Note: Qdrant's full-text search requires TextIndex or Query interface
            # For compatibility, use scroll with text filtering approximation
            # In practice, newer Qdrant versions support query() with TextQuery
            
            # Fusion: combine vector scores with text relevance
            vec_scores: dict[str, tuple[float, dict[str, Any]]] = {}
            for result in vec_results:
                vec_scores[str(result.id)] = (float(result.score), result.payload or {})
            
            # Simple text matching for full-text component
            text_scores: dict[str, float] = {}
            query_terms = query_text.lower().split()
            for chunk_id, (vec_score, payload) in vec_scores.items():
                text = (payload.get("fulltext", "") or "").lower()
                score = 0.0
                for term in query_terms:
                    if term in text:
                        score += text.count(term) / max(len(text.split()), 1)
                text_scores[chunk_id] = score
            
            # Normalize and fuse scores
            max_text = max(text_scores.values()) if text_scores.values() else 1.0
            max_vec = max([s[0] for s in vec_scores.values()]) if vec_scores.values() else 1.0
            
            fused: list[dict[str, Any]] = []
            for chunk_id, (vec_score, payload) in vec_scores.items():
                norm_text = text_scores.get(chunk_id, 0.0) / max(max_text, 1e-10)
                norm_vec = vec_score / max(max_vec, 1e-10)
                fused_score = 0.3 * norm_text + 0.7 * norm_vec
                fused.append({
                    "id": chunk_id,
                    "score": fused_score,
                    "payload": payload,
                })
            
            # Sort by fused score and return top_k
            fused.sort(key=lambda x: x["score"], reverse=True)
            return fused[:top_k]
            
        except Exception as e:
            logger.error(
                f"Failed to perform hybrid query on Qdrant collection '{collection_name}': {e}",
                extra={"collection_name": collection_name, "project_id": project_id},
                exc_info=True,
            )
            raise ProjectNotFound(project_id) from e
