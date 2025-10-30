from typing import Protocol, runtime_checkable, Sequence


@runtime_checkable
class EmbeddingPort(Protocol):
    def embed(self, texts: Sequence[str], model_id: str) -> list[list[float]]:
        """Return embeddings for the provided texts."""
        ...
