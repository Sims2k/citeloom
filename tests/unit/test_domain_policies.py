from src.domain.policy.chunking_policy import ChunkingPolicy
from src.domain.policy.retrieval_policy import RetrievalPolicy


def test_chunking_policy_defaults_and_equality():
    a = ChunkingPolicy()
    b = ChunkingPolicy(max_tokens=450, overlap=60, heading_context=2, tokenizer=None)
    assert a == b
    assert a.max_tokens == 450
    assert a.overlap == 60
    assert a.heading_context == 2


def test_chunking_policy_custom_values():
    p = ChunkingPolicy(max_tokens=300, overlap=30, heading_context=1, tokenizer="tkn")
    assert p.max_tokens == 300
    assert p.overlap == 30
    assert p.heading_context == 1
    assert p.tokenizer == "tkn"


def test_retrieval_policy_defaults_and_flags():
    r = RetrievalPolicy()
    assert r.top_k == 6
    assert r.hybrid is True
    assert r.project_filter_required is True


def test_retrieval_policy_custom_values():
    r = RetrievalPolicy(top_k=10, hybrid=False, project_filter_required=True)
    assert r.top_k == 10
    assert r.hybrid is False
    assert r.project_filter_required is True
