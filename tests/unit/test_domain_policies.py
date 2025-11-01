from domain.policy.chunking_policy import ChunkingPolicy
from domain.policy.retrieval_policy import RetrievalPolicy


def test_chunking_policy_defaults_and_equality():
    a = ChunkingPolicy()
    b = ChunkingPolicy(max_tokens=450, overlap_tokens=60, heading_context=2, tokenizer_id=None)
    assert a == b
    assert a.max_tokens == 450
    assert a.overlap_tokens == 60
    assert a.heading_context == 2


def test_chunking_policy_custom_values():
    p = ChunkingPolicy(max_tokens=300, overlap_tokens=30, heading_context=1, tokenizer_id="tkn")
    assert p.max_tokens == 300
    assert p.overlap_tokens == 30
    assert p.heading_context == 1
    assert p.tokenizer_id == "tkn"


def test_retrieval_policy_defaults_and_flags():
    r = RetrievalPolicy()
    assert r.top_k == 6
    assert r.hybrid_enabled is True
    assert r.require_project_filter is True


def test_retrieval_policy_custom_values():
    r = RetrievalPolicy(top_k=10, hybrid_enabled=False, require_project_filter=True)
    assert r.top_k == 10
    assert r.hybrid_enabled is False
    assert r.require_project_filter is True
