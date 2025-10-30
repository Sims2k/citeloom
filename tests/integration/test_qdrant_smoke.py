from infrastructure.adapters.qdrant_index import QdrantIndexAdapter


def test_qdrant_smoke_inmemory():
    idx = QdrantIndexAdapter()
    items = [
        {"text": "alpha", "page_span": [1, 1]},
        {"text": "alphabet", "page_span": [2, 2]},
    ]
    idx.upsert(items, project_id="citeloom/test", model_id="m")
    res = idx.search([0.0]*8, project_id="citeloom/test", top_k=1)
    assert res and res[0]["text"] == "alphabet"
