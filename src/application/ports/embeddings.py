from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingPort(Protocol):
    """Protocol for generating embeddings for text chunks."""
    
    @property
    def model_id(self) -> str:
        """Return the embedding model identifier (e.g., 'fastembed/all-MiniLM-L6-v2')."""
        ...
    
    def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            model_id: Optional model override (defaults to self.model_id)
        
        Returns:
            List of embedding vectors (each is list[float])
        
        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...
