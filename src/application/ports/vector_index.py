from typing import Protocol, runtime_checkable, Mapping, Any, Sequence


@runtime_checkable
class VectorIndexPort(Protocol):
    def upsert(self, items: Sequence[Mapping[str, Any]], project_id: str, model_id: str) -> None:
        """Upsert items into the vector index for a project and embed model."""
        ...

    def search(
        self, query_embedding: list[float], project_id: str, top_k: int
    ) -> Sequence[Mapping[str, Any]]:
        """Search top_k items within a project collection by embedding."""
        ...
