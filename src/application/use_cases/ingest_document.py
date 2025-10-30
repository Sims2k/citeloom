from __future__ import annotations

from typing import Mapping, Any, Sequence

from ..dto.ingest import IngestRequest, IngestResult
from ..ports.converter import TextConverterPort
from ..ports.chunker import ChunkerPort
from ..ports.metadata_resolver import MetadataResolverPort
from ..ports.embeddings import EmbeddingPort
from ..ports.vector_index import VectorIndexPort


def ingest_document(
    request: IngestRequest,
    converter: TextConverterPort,
    chunker: ChunkerPort,
    resolver: MetadataResolverPort,
    embedder: EmbeddingPort,
    index: VectorIndexPort,
) -> IngestResult:
    conversion: Mapping[str, Any] = converter.convert(request.source_path)
    chunks: Sequence[Mapping[str, Any]] = chunker.chunk(conversion)

    texts: list[str] = []
    enriched: list[Mapping[str, Any]] = []
    for ch in chunks:
        meta = resolver.resolve(citekey=ch.get("citekey"), references_path=request.references_path)
        item = {**ch, "citation": meta}
        enriched.append(item)
        texts.append(ch.get("text", ""))

    vectors = embedder.embed(texts, model_id=request.embedding_model)
    to_store = []
    for item, vec in zip(enriched, vectors):
        to_store.append({**item, "embedding": vec, "embed_model": request.embedding_model})

    index.upsert(to_store, project_id=request.project_id, model_id=request.embedding_model)
    return IngestResult(chunks_written=len(to_store))
