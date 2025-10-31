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
        query_vector: list[float], 
        project_id: str, 
        top_k: int,
        filters: dict[str, Any] | None = None
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
        ...
    
    def hybrid_query(
        self,
        query_text: str,
        query_vector: list[float],
        project_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None
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
        
        Note:
            Optional method - only required if hybrid_enabled=True
        """
        ...
