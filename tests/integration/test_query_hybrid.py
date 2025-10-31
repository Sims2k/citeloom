"""Integration tests for hybrid query functionality."""

from application.dto.query import QueryRequest
from application.use_cases.query_chunks import query_chunks
from infrastructure.adapters.fastembed_embeddings import FastEmbedAdapter
from infrastructure.adapters.qdrant_index import QdrantIndexAdapter


def test_query_hybrid_modes_execute():
    """Test that both dense-only and hybrid search modes execute successfully."""
    embed = FastEmbedAdapter()
    index = QdrantIndexAdapter(create_fulltext_index=True)
    
    # Create test chunks with embeddings
    texts = [
        "entities and value objects are core domain concepts",
        "repositories and ports enable dependency inversion",
    ]
    
    # Generate embeddings
    embeddings = embed.embed(texts, model_id=None)
    
    # Prepare items with proper structure
    items = [
        {
            "id": f"chunk-{i}",
            "doc_id": "test-doc-1",
            "text": text,
            "embedding": emb,
            "page_span": [i + 1, i + 1],
            "section_heading": f"Section {i + 1}",
            "section_path": ["Chapter 1", f"Section {i + 1}"],
            "chunk_idx": i,
        }
        for i, (text, emb) in enumerate(zip(texts, embeddings))
    ]
    
    # Upsert chunks
    model_id = embed.model_id
    index.upsert(items, project_id="citeloom/test", model_id=model_id)
    
    # Test dense-only search
    req_dense = QueryRequest(
        project_id="citeloom/test",
        query_text="entities",
        top_k=1,
        hybrid=False,
    )
    res_dense = query_chunks(req_dense, embed, index)
    assert res_dense.items is not None
    assert len(res_dense.items) == 1
    assert res_dense.items[0].text is not None
    assert res_dense.items[0].score >= 0.0
    
    # Test hybrid search
    req_hybrid = QueryRequest(
        project_id="citeloom/test",
        query_text="entities",
        top_k=1,
        hybrid=True,
    )
    res_hybrid = query_chunks(req_hybrid, embed, index)
    assert res_hybrid.items is not None
    assert len(res_hybrid.items) == 1
    assert res_hybrid.items[0].text is not None
    assert res_hybrid.items[0].score >= 0.0
    
    # Verify results contain expected content
    assert "entities" in res_dense.items[0].text.lower() or "value objects" in res_dense.items[0].text.lower()
    assert "entities" in res_hybrid.items[0].text.lower() or "value objects" in res_hybrid.items[0].text.lower()
