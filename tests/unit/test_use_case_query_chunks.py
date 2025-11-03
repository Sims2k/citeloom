"""Unit tests for query_chunks use case."""

from __future__ import annotations

import pytest
from unittest.mock import Mock

from src.application.use_cases.query_chunks import query_chunks
from src.application.dto.query import QueryRequest, QueryResult
from src.domain.errors import ProjectNotFound, HybridNotSupported
from src.domain.policy.retrieval_policy import RetrievalPolicy


class MockEmbedder:
    """Mock embedder for testing."""
    
    def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]]:
        """Mock embedding generation."""
        return [[0.1] * 384]


class MockVectorIndex:
    """Mock vector index for testing."""
    
    def search(self, query_vector, project_id, top_k, filters=None):
        """Mock vector search."""
        return [
            {
                "id": "chunk_1",
                "score": 0.95,
                "payload": {
                    "fulltext": "Sample chunk text for testing.",
                    "doc": {
                        "page_span": [1, 1],
                        "section_heading": "Introduction",
                        "section_path": ["Introduction"],
                    },
                    "zotero": {
                        "citekey": "test-2025",
                        "doi": "10.1000/test",
                    },
                },
            },
        ]
    
    def hybrid_query(self, query_text, query_vector, project_id, top_k, filters=None):
        """Mock hybrid search."""
        return self.search(query_vector, project_id, top_k, filters)


def test_query_chunks_success():
    """Test successful chunk query."""
    # Setup
    request = QueryRequest(
        project_id="test/project",
        query_text="test query",
        top_k=5,
        hybrid=False,
    )
    
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Execute
    result = query_chunks(request, embedder, index)
    
    # Assert
    assert isinstance(result, QueryResult)
    assert len(result.items) == 1
    assert result.items[0].text == "Sample chunk text for testing."
    assert result.items[0].citekey == "test-2025"
    assert result.items[0].score == 0.95


def test_query_chunks_hybrid():
    """Test hybrid chunk query."""
    # Setup
    request = QueryRequest(
        project_id="test/project",
        query_text="test query",
        top_k=5,
        hybrid=True,
    )
    
    embedder = MockEmbedder()
    index = Mock()
    index.hybrid_query = Mock(return_value=[
        {
            "id": "chunk_1",
            "score": 0.95,
            "payload": {
                "fulltext": "Sample chunk text for testing.",
                "doc": {
                    "page_span": [1, 1],
                    "section_heading": "Introduction",
                    "section_path": ["Introduction"],
                },
                "zotero": {
                    "citekey": "test-2025",
                    "doi": "10.1000/test",
                },
            },
        },
    ])
    policy = RetrievalPolicy(hybrid_enabled=True)
    
    # Execute
    result = query_chunks(request, embedder, index, policy=policy)
    
    # Assert
    assert isinstance(result, QueryResult)
    assert len(result.items) == 1
    index.hybrid_query.assert_called_once()


def test_query_chunks_hybrid_not_supported():
    """Test hybrid query raises error when not supported."""
    # Setup
    request = QueryRequest(
        project_id="test/project",
        query_text="test query",
        top_k=5,
        hybrid=True,
    )
    
    embedder = MockEmbedder()
    index = MockVectorIndex()
    policy = RetrievalPolicy(hybrid_enabled=False)
    
    # Execute & Assert
    with pytest.raises(HybridNotSupported):
        query_chunks(request, embedder, index, policy=policy)


def test_query_chunks_project_not_found():
    """Test query raises error when project doesn't exist."""
    # Setup
    request = QueryRequest(
        project_id="nonexistent/project",
        query_text="test query",
        top_k=5,
    )
    
    embedder = MockEmbedder()
    index = MockVectorIndex()
    index.search = Mock(side_effect=Exception("Collection not found"))
    
    # Execute & Assert
    with pytest.raises(ProjectNotFound):
        query_chunks(request, embedder, index)


def test_query_chunks_empty_result():
    """Test query returns empty result when no chunks match."""
    # Setup
    request = QueryRequest(
        project_id="test/project",
        query_text="test query",
        top_k=5,
    )
    
    embedder = MockEmbedder()
    index = MockVectorIndex()
    index.search = Mock(return_value=[])
    
    # Execute
    result = query_chunks(request, embedder, index)
    
    # Assert
    assert isinstance(result, QueryResult)
    assert len(result.items) == 0


def test_query_chunks_text_trimming():
    """Test query trims text to max_chars_per_chunk."""
    # Setup
    request = QueryRequest(
        project_id="test/project",
        query_text="test query",
        top_k=5,
    )
    
    embedder = MockEmbedder()
    index = Mock()
    
    # Create long text chunk (exactly 1800 chars)
    long_text = "a" * 2000  # Very long text
    index.search = Mock(return_value=[
        {
            "id": "chunk_1",
            "score": 0.95,
            "payload": {
                "fulltext": long_text,
                "doc": {},
                "zotero": {},
            },
        },
    ])
    
    policy = RetrievalPolicy(max_chars_per_chunk=1800)
    
    # Execute
    result = query_chunks(request, embedder, index, policy=policy)
    
    # Assert - trimming adds "..." so may be slightly over, but should be close
    assert len(result.items) == 1
    assert len(result.items[0].text) <= 1803  # Allow for "..."
    assert result.items[0].text.endswith("...")


def test_query_chunks_min_score_filter():
    """Test query filters results by min_score."""
    # Setup
    request = QueryRequest(
        project_id="test/project",
        query_text="test query",
        top_k=5,
    )
    
    embedder = MockEmbedder()
    index = MockVectorIndex()
    index.search = Mock(return_value=[
        {
            "id": "chunk_1",
            "score": 0.95,
            "payload": {"fulltext": "text1", "doc": {}, "zotero": {}},
        },
        {
            "id": "chunk_2",
            "score": 0.3,  # Below threshold
            "payload": {"fulltext": "text2", "doc": {}, "zotero": {}},
        },
        {
            "id": "chunk_3",
            "score": 0.7,
            "payload": {"fulltext": "text3", "doc": {}, "zotero": {}},
        },
    ])
    
    policy = RetrievalPolicy(min_score=0.5)
    
    # Execute
    result = query_chunks(request, embedder, index, policy=policy)
    
    # Assert
    assert len(result.items) == 2  # Only chunks with score >= 0.5
    assert all(item.score >= 0.5 for item in result.items)


def test_query_chunks_with_filters():
    """Test query passes filters to index."""
    # Setup
    request = QueryRequest(
        project_id="test/project",
        query_text="test query",
        top_k=5,
        filters={"citekey": "test-2025"},
    )
    
    embedder = MockEmbedder()
    index = Mock()
    index.search = Mock(return_value=[
        {
            "id": "chunk_1",
            "score": 0.95,
            "payload": {
                "fulltext": "Sample chunk text.",
                "doc": {},
                "zotero": {},
            },
        },
    ])
    
    # Execute
    result = query_chunks(request, embedder, index)
    
    # Assert
    index.search.assert_called_once()
    call_args = index.search.call_args
    assert call_args[1]["filters"] == {"citekey": "test-2025"}

