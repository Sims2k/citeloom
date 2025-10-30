from __future__ import annotations

from typing import Mapping, Any, Sequence

try:
    from qdrant_client import QdrantClient
except Exception:  # pragma: no cover
    QdrantClient = None  # type: ignore


class QdrantIndexAdapter:
    def __init__(self, url: str = "http://localhost:6333") -> None:
        self.url = url
        self._client = None
        if QdrantClient is not None:
            try:
                self._client = QdrantClient(url=url)
            except Exception:
                self._client = None
        # In-memory fallback store
        self._local: dict[str, list[Mapping[str, Any]]] = {}

    def _collection(self, project_id: str) -> str:
        return project_id.replace("/", "-")

    def upsert(self, items: Sequence[Mapping[str, Any]], project_id: str, model_id: str) -> None:
        # For now, just store locally to enable tests; real Qdrant integration to follow
        coll = self._collection(project_id)
        self._local.setdefault(coll, []).extend(items)

    def search(self, query_embedding: list[float], project_id: str, top_k: int) -> Sequence[Mapping[str, Any]]:
        coll = self._collection(project_id)
        items = self._local.get(coll, [])
        # Naive scoring: length of text as a proxy (placeholder)
        scored = [
            {**it, "score": float(len(str(it.get("text", ""))))}
            for it in items
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
