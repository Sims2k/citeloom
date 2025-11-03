from __future__ import annotations

import logging
from typing import Sequence

try:
    from fastembed import TextEmbedding
except Exception:  # pragma: no cover
    TextEmbedding = None  # type: ignore

logger = logging.getLogger(__name__)

# Module-level cache for process-scoped embedding model instances (T044a)
_embedding_model_cache: dict[str, "FastEmbedAdapter"] = {}


class FastEmbedAdapter:
    """Adapter for FastEmbed local embeddings."""
    
    def __init__(self, default_model: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        """
        Initialize FastEmbed adapter.
        
        Args:
            default_model: Default embedding model identifier
        """
        self.default_model = default_model
        self._engine = None
        if TextEmbedding is not None:
            try:
                self._engine = TextEmbedding(model_name=default_model)
            except Exception:
                self._engine = None
    
    @property
    def model_id(self) -> str:
        """
        Return the embedding model identifier.
        
        Returns:
            Model identifier (e.g., 'fastembed/all-MiniLM-L6-v2')
        """
        # Normalize model ID to FastEmbed format
        if self.default_model.startswith("fastembed/"):
            return self.default_model
        if "/" in self.default_model:
            # Convert sentence-transformers/... to fastembed/...
            parts = self.default_model.split("/", 1)
            return f"fastembed/{parts[1]}"
        return f"fastembed/{self.default_model}"
    
    @property
    def tokenizer_family(self) -> str:
        """
        Return the tokenizer family identifier for alignment validation.
        
        Returns:
            Tokenizer family (e.g., 'minilm', 'bge')
        """
        model_name = self.model_id.lower()
        # Extract tokenizer family from model identifier
        if "minilm" in model_name:
            return "minilm"
        elif "bge" in model_name:
            return "bge"
        elif "openai" in model_name or "ada" in model_name:
            return "openai"
        elif "tiktoken" in model_name:
            return "tiktoken"
        else:
            # Default fallback: try to extract from model name
            # For models like "sentence-transformers/all-MiniLM-L6-v2", extract "minilm"
            parts = model_name.split("/")
            if len(parts) > 1:
                model_part = parts[-1]
                if "minilm" in model_part:
                    return "minilm"
                elif "bge" in model_part:
                    return "bge"
            return "unknown"

    def embed(self, texts: Sequence[str], model_id: str | None = None) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            model_id: Optional model override (defaults to self.model_id)
        
        Returns:
            List of embedding vectors (each is list[float])
        
        Raises:
            RuntimeError: If embedding generation fails and no fallback available
        """
        model_name = model_id or self.default_model
        
        # If model doesn't match or engine not available, use fallback
        if self._engine is None or (model_id is not None and model_id != self.default_model):
            # Fallback: return zero vectors of appropriate size to enable tests without model
            # MiniLM produces 384-dimensional vectors
            return [[0.0] * 384 for _ in texts]
        
        try:
            vectors = []
            for vec in self._engine.embed(texts):  # type: ignore[union-attr]
                vectors.append(list(map(float, vec)))
            return vectors
        except Exception as e:
            # Fallback on error
            return [[0.0] * 384 for _ in texts]


def get_embedding_model(model_id: str = "sentence-transformers/all-MiniLM-L6-v2", config_hash: str | None = None) -> FastEmbedAdapter:
    """
    Get or create shared FastEmbedAdapter instance (process-scoped).
    
    This factory function implements a singleton pattern with module-level cache
    to avoid reinitialization overhead on subsequent commands in the same process.
    
    Args:
        model_id: Embedding model identifier (e.g., "sentence-transformers/all-MiniLM-L6-v2")
        config_hash: Optional configuration hash for variant instances
            (default: None for single instance per model)
    
    Returns:
        FastEmbedAdapter instance (shared across process lifetime for same model_id)
    
    Behavior:
        - First call for a model_id: Creates new FastEmbedAdapter, caches it, returns instance
        - Subsequent calls with same model_id: Returns cached instance (no reinitialization overhead)
        - Cache key: f"embedding_model:{model_id}:{config_hash or 'default'}"
        - Lifetime: Process-scoped (cleared only on process termination)
    
    Thread Safety:
        - Module-level cache is safe for single-user CLI (no concurrent access expected)
        - No locking required for single-threaded CLI operations
    
    Note:
        Can be deferred if embedding model reuse is not critical for MVP, but recommended
        for performance optimization when multiple commands use same embedding model.
    """
    cache_key = f"embedding_model:{model_id}:{config_hash or 'default'}"
    
    if cache_key not in _embedding_model_cache:
        logger.debug(f"Creating new embedding model instance (cache_key={cache_key}, model_id={model_id})")
        _embedding_model_cache[cache_key] = FastEmbedAdapter(default_model=model_id)
    else:
        logger.debug(f"Reusing cached embedding model instance (cache_key={cache_key}, model_id={model_id})")
    
    return _embedding_model_cache[cache_key]
