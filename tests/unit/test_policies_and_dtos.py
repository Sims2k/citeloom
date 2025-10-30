from src.domain.policy.chunking_policy import ChunkingPolicy
from src.domain.policy.retrieval_policy import RetrievalPolicy
from src.application.dto.ingest import IngestRequest
from src.application.dto.query import QueryRequest


def test_policies_default_values():
    c = ChunkingPolicy()
    r = RetrievalPolicy()
    assert c.max_tokens > 0 and r.top_k > 0


def test_dtos_construct():
    ingest = IngestRequest(
        project_id="citeloom/clean-arch",
        source_path="assets/raw/sample.pdf",
        references_path="references/clean-arch.json",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    query = QueryRequest(project_id="citeloom/clean-arch", query_text="test")
    assert ingest.project_id and query.query_text
