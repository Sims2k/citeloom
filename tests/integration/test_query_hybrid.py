from application.dto.query import QueryRequest
from application.use_cases.query_chunks import query_chunks
from infrastructure.adapters.fastembed_embeddings import FastEmbedAdapter
from infrastructure.adapters.qdrant_index import QdrantIndexAdapter


def test_query_hybrid_modes_execute():
    embed = FastEmbedAdapter()
    index = QdrantIndexAdapter()
    items = [
        {"text": "entities and value objects", "page_span": [1, 1]},
        {"text": "repositories and ports", "page_span": [2, 2]},
    ]
    index.upsert(items, project_id="citeloom/test", model_id="m")

    req_dense = QueryRequest(project_id="citeloom/test", query_text="entities", top_k=1, hybrid=False)
    res_dense = query_chunks(req_dense, embed, index)
    assert res_dense.items and len(res_dense.items) == 1

    req_hybrid = QueryRequest(project_id="citeloom/test", query_text="entities", top_k=1, hybrid=True)
    res_hybrid = query_chunks(req_hybrid, embed, index)
    assert res_hybrid.items and len(res_hybrid.items) == 1
