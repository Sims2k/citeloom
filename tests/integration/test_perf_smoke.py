import os
import time
import pytest

from infrastructure.adapters.docling_converter import DoclingConverterAdapter
from infrastructure.adapters.docling_chunker import DoclingHybridChunkerAdapter
from infrastructure.adapters.qdrant_index import QdrantIndexAdapter
from application.dto.ingest import IngestRequest
from application.use_cases.ingest_document import ingest_document

RUN_PERF = os.environ.get("CITELOOM_RUN_PERF") == "1"

pytestmark = pytest.mark.skipif(not RUN_PERF, reason="perf smoke disabled; set CITELOOM_RUN_PERF=1 to enable")


@pytest.mark.slow
def test_ingest_perf_smoke_under_120s():
    start = time.perf_counter()
    req = IngestRequest(
        project_id="citeloom/perf",
        source_path="assets/raw/clean-arch.pdf",
        references_path="references/clean-arch.json",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    # Import embedding adapter lazily to avoid heavy deps during collection
    from infrastructure.adapters.fastembed_embeddings import FastEmbedAdapter
    result = ingest_document(
        req,
        DoclingConverterAdapter(),
        DoclingHybridChunkerAdapter(),
        lambda citekey, references_path: None,  # type: ignore
        FastEmbedAdapter(),
        QdrantIndexAdapter(),
    )
    elapsed = time.perf_counter() - start
    assert elapsed <= 120.0
    assert result.chunks_written >= 1


@pytest.mark.slow
def test_query_perf_smoke_under_1s():
    idx = QdrantIndexAdapter()
    idx.upsert([{"text": "foo"}], project_id="citeloom/perf", model_id="m")
    start = time.perf_counter()
    _ = idx.search([0.0] * 8, project_id="citeloom/perf", top_k=6)
    elapsed = time.perf_counter() - start
    assert elapsed <= 1.0
