from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class VectorIndexPort(Protocol):
    """Protocol for storing and retrieving chunks from vector database."""
    
    def upsert(
        self, 
        items: list[dict[str, Any]], 
        project_id: str, 
        model_id: str
    ) -> None:
        """
        Upsert chunks into project collection.
        
        Args:
            items: List of chunk dicts with embedding, metadata, payload
            project_id: Project identifier (determines collection)
            model_id: Embedding model identifier (for write-guard)
        
        Raises:
            EmbeddingModelMismatch: If model_id doesn't match collection's model
            ProjectNotFound: If project collection doesn't exist
        """
        ...
    
    def search(
        self, 
        query_vector: list[float] | None = None,
        query_text: str | None = None,
        project_id: str = "",
        top_k: int = 6,
        filters: dict[str, Any] | None = None,
        use_named_vectors: bool = True
    ) -> list[dict[str, Any]]:
        """
        Vector search with project filtering.
        
        Supports both vector-based and text-based queries (when model binding enabled).
        
        Args:
            query_vector: Query embedding vector (required if query_text not provided)
            query_text: Query text for text-based search (requires model binding via set_model())
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters (e.g., tags)
            use_named_vectors: Whether to use named vector 'dense' (default: True)
        
        Returns:
            List of hit dicts with score, payload (text, metadata, citation info)
        
        Raises:
            ValueError: If neither query_vector nor query_text provided
            ProjectNotFound: If project collection doesn't exist
        
        Note:
            Text-based queries require model binding via set_model().
            When query_text is provided and model is bound, Qdrant handles embedding automatically.
        """
        ...
    
    def hybrid_query(
        self,
        query_text: str,
        query_vector: list[float] | None = None,
        project_id: str = "",
        top_k: int = 6,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Hybrid search using RRF fusion (named vectors with dense + sparse).
        
        Performs hybrid search combining semantic (dense) and lexical (sparse) retrieval.
        When both dense and sparse models are bound, Qdrant automatically fuses results
        using Reciprocal Rank Fusion (RRF).
        
        Args:
            query_text: Query text for both sparse (BM25) and dense (if model binding) search
            query_vector: Optional query embedding vector (used if model binding not available)
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters (tags with AND semantics, optional section prefix)
        
        Returns:
            List of hit dicts with RRF-fused scores and payload
        
        Raises:
            HybridNotSupported: If hybrid not enabled for project or sparse model not bound
            ProjectNotFound: If project collection doesn't exist
        
        Note:
            T044: Requires both dense and sparse models bound via set_model() and set_sparse_model()
            RRF fusion is automatic when both named vectors are configured
        """
        ...
    
    def ensure_collection(
        self,
        project_id: str,
        dense_model_id: str,
        sparse_model_id: str | None = None,
        on_disk_vectors: bool = False,
        on_disk_hnsw: bool = False
    ) -> None:
        """
        Ensure collection exists with named vectors and model bindings.
        
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
        ...