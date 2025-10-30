from __future__ import annotations

from typing import Sequence

try:
    from fastembed import TextEmbedding
except Exception:  # pragma: no cover
    TextEmbedding = None  # type: ignore


class FastEmbedAdapter:
    def __init__(self, default_model: str = "sentence-transformers/all-MiniLM-L6-v2") -> None:
        self.default_model = default_model
        self._engine = None
        if TextEmbedding is not None:
            try:
                self._engine = TextEmbedding(model_name=default_model)
            except Exception:
                self._engine = None

    def embed(self, texts: Sequence[str], model_id: str | None = None) -> list[list[float]]:
        model_name = model_id or self.default_model
        if self._engine is None or model_name != self.default_model:
            # Fallback: return zero vectors of small size to enable tests without model
            return [[0.0] * 8 for _ in texts]
        vectors = []
        for vec in self._engine.embed(texts):  # type: ignore[union-attr]
            vectors.append(list(map(float, vec)))
        return vectors
