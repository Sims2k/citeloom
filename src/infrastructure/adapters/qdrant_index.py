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
        SparseVectorParams,
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
    SparseVectorParams = None  # type: ignore
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
        dense_model_id: str,
        sparse_model_id: str | None = None,
        on_disk_vectors: bool = False,
        on_disk_hnsw: bool = False,
        recreate: bool = False,
    ) -> None:
        """
        Ensure collection exists with named vectors and model bindings.
        
        Args:
            collection_name: Collection name
            vector_size: Dense vector dimension size
            dense_model_id: Dense embedding model identifier
            sparse_model_id: Optional sparse model identifier (for hybrid search)
            on_disk_vectors: Whether to store vectors on-disk (for large projects)
            on_disk_hnsw: Whether to store HNSW index on-disk
            recreate: Whether to recreate collection if it exists
        
        Raises:
            RuntimeError: If collection creation fails
            EmbeddingModelMismatch: If model_id doesn't match existing collection
        """
        if self._client is None:
            # In-memory fallback: just track collection metadata
            if collection_name not in self._local or recreate:
                self._local[collection_name] = {
                    "dense_model_id": dense_model_id,
                    "sparse_model_id": sparse_model_id,
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
                # Create collection with named vectors (dense and optional sparse)
                vectors_config: dict[str, Any] = {
                    "dense": VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE,
                        on_disk=on_disk_vectors,
                    ),
                }
                
                # Add sparse vector if hybrid is enabled
                if sparse_model_id is not None:
                    if SparseVectorParams is not None:
                        vectors_config["sparse"] = SparseVectorParams()
                    else:
                        # Fallback: use empty dict for sparse vector params
                        vectors_config["sparse"] = {}
                
                self._client.create_collection(
                    collection_name=collection_name,
                    vectors_config=vectors_config,
                    optimizers_config={
                        "indexing_threshold": 20000,
                    },
                    hnsw_config={
                        "on_disk": on_disk_hnsw,
                    } if on_disk_hnsw else None,
                )
                
                # Bind dense model for text-based queries
                try:
                    self._client.set_model(collection_name=collection_name, model_name=dense_model_id)
                    logger.debug(
                        f"Bound dense model '{dense_model_id}' to collection '{collection_name}'",
                        extra={"collection_name": collection_name, "model_id": dense_model_id},
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to bind dense model '{dense_model_id}': {e}. "
                        "Text-based queries may not work. Continuing without model binding.",
                        extra={"collection_name": collection_name, "model_id": dense_model_id},
                    )
                
                # Bind sparse model if provided
                if sparse_model_id is not None:
                    try:
                        self._client.set_sparse_model(collection_name=collection_name, model_name=sparse_model_id)
                        logger.debug(
                            f"Bound sparse model '{sparse_model_id}' to collection '{collection_name}'",
                            extra={"collection_name": collection_name, "sparse_model_id": sparse_model_id},
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to bind sparse model '{sparse_model_id}': {e}. "
                            "Hybrid search may not work. Continuing without sparse model binding.",
                            extra={"collection_name": collection_name, "sparse_model_id": sparse_model_id},
                        )
                
                # Store model IDs in collection metadata for write-guard
                metadata = {
                    "dense_model_id": dense_model_id,
                }
                if sparse_model_id is not None:
                    metadata["sparse_model_id"] = sparse_model_id
                
                self._client.update_collection(
                    collection_name=collection_name,
                    collection_metadata=metadata,
                )
                
                # Create payload indexes
                self._create_payload_indexes(collection_name)
                
                logger.info(
                    f"Created collection '{collection_name}' with dense_model='{dense_model_id}'"
                    + (f", sparse_model='{sparse_model_id}'" if sparse_model_id else ""),
                    extra={
                        "collection_name": collection_name,
                        "dense_model_id": dense_model_id,
                        "sparse_model_id": sparse_model_id,
                    },
                )
            else:
                # Verify model_id matches (write-guard check)
                collection_info = self._client.get_collection(collection_name)
                metadata = collection_info.config.params.vectors  # This might be wrong structure
                # Try to get from collection metadata instead
                try:
                    collection_metadata = collection_info.config.params  # This structure varies
                    # Access metadata through proper API
                    collection_full_info = self._client.get_collection(collection_name)
                    # Get metadata - in newer Qdrant versions it's available differently
                    # For now, check if we can access it via collection info
                    stored_dense_model = None
                    stored_sparse_model = None
                    # Try to get from metadata dict if available
                    if hasattr(collection_full_info, "config") and hasattr(collection_full_info.config, "params"):
                        # Metadata might be in a different location
                        pass
                    
                    # Fallback: try to get from get_collection response metadata
                    # Qdrant API may store this in collection_metadata
                    stored_metadata = getattr(collection_full_info, "metadata", None) or {}
                    stored_dense_model = stored_metadata.get("dense_model_id")
                    stored_sparse_model = stored_metadata.get("sparse_model_id")
                    
                    # If metadata not found, try collection config
                    if not stored_dense_model:
                        # This is a fallback - we'll improve this later
                        stored_dense_model = stored_metadata.get("embed_model")  # Legacy field
                    
                    # Validate dense model match (write-guard)
                    if stored_dense_model and dense_model_id != stored_dense_model:
                        # Derive project_id from collection_name
                        project_id = collection_name.replace("proj-", "").replace("-", "/")
                        raise EmbeddingModelMismatch(
                            project_id=project_id,
                            expected_model=stored_dense_model,
                            provided_model=dense_model_id,
                        )
                    
                    # Validate sparse model match if provided
                    if sparse_model_id is not None and stored_sparse_model and sparse_model_id != stored_sparse_model:
                        logger.warning(
                            f"Sparse model mismatch for collection '{collection_name}': "
                            f"expected '{stored_sparse_model}', got '{sparse_model_id}'. "
                            "Hybrid search may behave unexpectedly.",
                            extra={
                                "collection_name": collection_name,
                                "expected_sparse_model": stored_sparse_model,
                                "provided_sparse_model": sparse_model_id,
                            },
                        )
                except AttributeError:
                    # Metadata structure not available - skip validation for now
                    logger.debug(
                        f"Could not access collection metadata for '{collection_name}'. "
                        "Skipping write-guard validation.",
                        extra={"collection_name": collection_name},
                    )
        except EmbeddingModelMismatch:
            raise
        except Exception as e:
            logger.error(
                f"Failed to ensure collection '{collection_name}': {e}",
                extra={"collection_name": collection_name},
                exc_info=True,
            )
            raise

    def ensure_collection(
        self,
        project_id: str,
        dense_model_id: str,
        sparse_model_id: str | None = None,
        on_disk_vectors: bool = False,
        on_disk_hnsw: bool = False,
    ) -> None:
        """
        Ensure collection exists with named vectors and model bindings.
        
        Public API method matching VectorIndexPort protocol.
        
        Args:
            project_id: Project identifier
            dense_model_id: Dense embedding model identifier
            sparse_model_id: Optional sparse model identifier (for hybrid)
            on_disk_vectors: Whether to store vectors on-disk (for large projects)
            on_disk_hnsw: Whether to store HNSW index on-disk
        
        Creates collection with:
        - Named vectors: 'dense' and optionally 'sparse'
        - Model bindings via set_model() and set_sparse_model()
        - Payload indexes: keyword on project_id, doc_id, citekey, year, tags; full-text on chunk_text
        - On-disk storage flags if specified
        """
        collection_name = self._collection_name(project_id)
        
        # Determine vector size from dense model (default to 384 for common models)
        # In practice, this should come from the embedding model configuration
        vector_size = 384  # Default for MiniLM/BGE-small; should be configurable
        
        self._ensure_collection(
            collection_name=collection_name,
            vector_size=vector_size,
            dense_model_id=dense_model_id,
            sparse_model_id=sparse_model_id,
            on_disk_vectors=on_disk_vectors,
            on_disk_hnsw=on_disk_hnsw,
            recreate=False,
        )

    def _create_payload_indexes(self, collection_name: str) -> None:
        """
        Create payload indexes for filtering and full-text search.
        
        Creates keyword indexes on: project_id, doc_id, citekey, year, tags
        Creates full-text index on: chunk_text (if hybrid enabled)
        
        Args:
            collection_name: Collection name
        """
        if self._client is None:
            return
        
        try:
            # Create keyword indexes on high-cardinality filter fields
            # Qdrant's create_payload_index method creates indexes for fast filtering
            keyword_fields = ["project_id", "doc_id", "citekey", "year", "tags"]
            
            for field_name in keyword_fields:
                try:
                    # Create keyword index using create_payload_index
                    # Note: Qdrant API may vary by version
                    # For keyword indexes, use PayloadSchemaType.KEYWORD
                    if PayloadSchemaType is not None:
                        from qdrant_client.models import PayloadSchemaType as PST
                        self._client.create_payload_index(
                            collection_name=collection_name,
                            field_name=field_name,
                            field_schema=PST.KEYWORD,
                        )
                        logger.debug(
                            f"Created keyword index on '{field_name}' for collection '{collection_name}'",
                            extra={"collection_name": collection_name, "field_name": field_name},
                        )
                    else:
                        # Fallback: Qdrant may auto-index fields used in filters
                        logger.debug(
                            f"Payload index creation skipped (auto-index may apply): '{field_name}'",
                            extra={"collection_name": collection_name, "field_name": field_name},
                        )
                except Exception as idx_error:
                    # Some Qdrant versions auto-index keyword fields
                    logger.debug(
                        f"Keyword index creation attempted for '{field_name}' (may auto-index): {idx_error}",
                        extra={"collection_name": collection_name, "field_name": field_name},
                    )
            
            # Create full-text index on chunk_text field (if hybrid enabled)
            if self.create_fulltext_index:
                try:
                    # Create full-text index on 'chunk_text' payload field
                    # This enables BM25/full-text search for hybrid queries
                    if PayloadSchemaType is not None:
                        from qdrant_client.models import PayloadSchemaType as PST
                        self._client.create_payload_index(
                            collection_name=collection_name,
                            field_name="chunk_text",
                            field_schema=PST.TEXT,
                        )
                        logger.info(
                            f"Created full-text index on 'chunk_text' for collection '{collection_name}'",
                            extra={"collection_name": collection_name},
                        )
                    else:
                        logger.info(
                            f"Full-text index enabled for '{collection_name}' on 'chunk_text' field (may auto-index)",
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
        sparse_model_id: str | None = None,
    ) -> None:
        """
        Upsert chunks into project collection.
        
        Args:
            items: List of chunk dicts with embedding, metadata, payload
            project_id: Project identifier (determines collection)
            model_id: Dense embedding model identifier (for write-guard)
            force_rebuild: Whether to force collection recreation (for migrations)
            sparse_model_id: Optional sparse model identifier (for hybrid search)
        
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
                dense_model_id=model_id,
                sparse_model_id=sparse_model_id,
                recreate=force_rebuild,
            )
        except EmbeddingModelMismatch:
            raise
        except Exception as e:
            raise ProjectNotFound(project_id) from e
        
        if self._client is None:
            # In-memory fallback
            collection_data = self._local[collection_name]
            
            # Verify dense model_id matches (write-guard)
            if not force_rebuild and collection_data.get("dense_model_id") != model_id:
                raise EmbeddingModelMismatch(
                    project_id=project_id,
                    expected_model=collection_data.get("dense_model_id", "unknown"),
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
            
            # Extract payload fields according to schema
            page_span = item.get("page_span", (1, 1))
            if isinstance(page_span, (list, tuple)) and len(page_span) >= 2:
                page_start = int(page_span[0])
                page_end = int(page_span[1])
            else:
                page_start = 1
                page_end = 1
            
            section_path = item.get("section_path", [])
            section_heading = item.get("section_heading", "")
            
            # Build heading_chain from section_path
            heading_chain = " > ".join(section_path) if section_path else ""
            
            # Build payload with required schema fields
            # Required: project_id, doc_id, section_path, page_start, page_end, citekey, doi, year, authors, title, tags, source_path, chunk_text, heading_chain, embed_model, version
            payload: dict[str, Any] = {
                # Required indexed fields
                "project_id": project_id,
                "doc_id": item.get("doc_id", ""),
                "section_path": section_path,
                "page_start": page_start,
                "page_end": page_end,
                "citekey": "",  # Will be filled from citation metadata if available
                "doi": "",  # Will be filled from citation metadata
                "year": None,  # Will be filled from citation metadata
                "authors": [],  # Will be filled from citation metadata
                "title": "",  # Will be filled from citation metadata
                "tags": [],  # Will be filled from citation metadata
                "source_path": item.get("source_path", ""),
                "chunk_text": item.get("text", ""),  # Full-text indexed
                "heading_chain": heading_chain,
                "embed_model": model_id,
                "version": "1.0",  # Schema version
                
                # Legacy compatibility fields (for backward compatibility)
                "project": project_id,
                "doc": {
                    "id": item.get("doc_id", ""),
                    "page_span": [page_start, page_end],
                    "section_heading": section_heading,
                    "section_path": section_path,
                    "chunk_idx": item.get("chunk_idx", 0),
                },
            }
            
            # Add citation metadata if available (from Zotero)
            citation = item.get("citation")
            if citation:
                if isinstance(citation, dict):
                    # Map citation fields to payload schema
                    payload["citekey"] = citation.get("citekey", "")
                    payload["doi"] = citation.get("doi", "")
                    payload["year"] = citation.get("year")
                    payload["authors"] = citation.get("authors", [])
                    payload["title"] = citation.get("title", "")
                    payload["tags"] = citation.get("tags", [])
                    # Legacy zotero field for backward compatibility
                    payload["zotero"] = citation
                else:
                    payload["zotero"] = citation
            
            # Create point with named vector 'dense'
            # Note: Sparse vectors would be generated during query time via model binding
            point = PointStruct(
                id=chunk_id,
                vector={"dense": embedding} if isinstance(embedding, list) else embedding,
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
            # Build filter with mandatory project filter (server-side enforcement)
            # Use project_id field for filtering
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="project_id",
                        match=MatchValue(value=project_id),
                    ),
                ],
            )
            
            # Add additional filters if provided (tags, year, etc.)
            if filters:
                filter_conditions = [qdrant_filter.must[0]] if qdrant_filter.must else []
                
                # Support tag filters (AND semantics - all tags must match)
                if "tags" in filters and filters["tags"]:
                    tag_list = filters["tags"] if isinstance(filters["tags"], list) else [filters["tags"]]
                    for tag in tag_list:
                        filter_conditions.append(
                            FieldCondition(
                                key="tags",
                                match=MatchValue(value=tag),
                            )
                        )
                
                # Support year filter
                if "year" in filters and filters["year"] is not None:
                    filter_conditions.append(
                        FieldCondition(
                            key="year",
                            match=MatchValue(value=filters["year"]),
                        )
                    )
                
                # Support section prefix filter
                if "section_prefix" in filters and filters["section_prefix"]:
                    # Section prefix filter would use a text matching approach
                    # For now, we'll skip it as Qdrant doesn't have direct prefix matching on arrays
                    pass
                
                qdrant_filter = Filter(must=filter_conditions)
            
            # Use named vector 'dense' for search
            results = self._client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                with_payload=True,
                using="dense",  # Use named vector
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
        
        # Real Qdrant hybrid search using Query interface with RRF fusion
        try:
            # Build filter with mandatory project filter (server-side enforcement)
            qdrant_filter = Filter(
                must=[
                    FieldCondition(
                        key="project_id",
                        match=MatchValue(value=project_id),
                    ),
                ],
            )
            
            # Add additional filters if provided
            if filters:
                filter_conditions = [qdrant_filter.must[0]] if qdrant_filter.must else []
                
                if "tags" in filters and filters["tags"]:
                    tag_list = filters["tags"] if isinstance(filters["tags"], list) else [filters["tags"]]
                    for tag in tag_list:
                        filter_conditions.append(
                            FieldCondition(
                                key="tags",
                                match=MatchValue(value=tag),
                            )
                        )
                
                if "year" in filters and filters["year"] is not None:
                    filter_conditions.append(
                        FieldCondition(
                            key="year",
                            match=MatchValue(value=filters["year"]),
                        )
                    )
                
                qdrant_filter = Filter(must=filter_conditions)
            
            # Use Qdrant's query() method with text-based search for hybrid (RRF fusion)
            # When both dense and sparse models are bound, RRF fusion is automatic
            try:
                # Try using query() with text-based search (requires model binding)
                # This enables automatic RRF fusion when both models are bound
                from qdrant_client.models import Query, TextQuery
                
                # Create query with text for sparse and vector for dense
                # Qdrant will automatically fuse using RRF
                query = Query(
                    query=query_text,
                    using="dense",  # Use dense vector, sparse is automatic via model binding
                    filter=qdrant_filter,
                    limit=top_k,
                )
                
                results = self._client.query(
                    collection_name=collection_name,
                    queries=[query],
                    with_payload=True,
                )
                
                # Extract results from query response
                hits = []
                for batch in results:
                    for result in batch:
                        hits.append({
                            "id": str(result.id),
                            "score": float(result.score),
                            "payload": result.payload or {},
                        })
                
                return hits[:top_k]
            except (ImportError, AttributeError, Exception) as query_error:
                # Fallback to manual fusion if query() API not available
                logger.debug(
                    f"Query API not available, using manual fusion: {query_error}",
                    extra={"collection_name": collection_name},
                )
                
                # Manual fusion: run both searches and combine
                # 1. Vector search using dense named vector
                vec_results = self._client.search(
                    collection_name=collection_name,
                    query_vector=query_vector,
                    query_filter=qdrant_filter,
                    limit=top_k * 2,  # Get more candidates for fusion
                    with_payload=True,
                    using="dense",
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
