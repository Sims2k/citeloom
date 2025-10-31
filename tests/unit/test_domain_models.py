"""Unit tests for domain models: Chunk, ConversionResult, CitationMeta."""

from src.domain.models.chunk import Chunk, generate_chunk_id
from src.domain.models.conversion_result import ConversionResult
from src.domain.models.citation_meta import CitationMeta


def test_chunk_deterministic_id_generation_same_inputs():
    """Test that generate_chunk_id produces the same ID for identical inputs."""
    doc_id = "doc123"
    page_span = (1, 3)
    section_path = ["Introduction", "Overview"]
    embedding_model_id = "fastembed/all-MiniLM-L6-v2"
    chunk_idx = 0
    
    id1 = generate_chunk_id(doc_id, page_span, section_path, embedding_model_id, chunk_idx)
    id2 = generate_chunk_id(doc_id, page_span, section_path, embedding_model_id, chunk_idx)
    
    assert id1 == id2, "Same inputs should produce identical chunk IDs"
    assert len(id1) == 16, "Chunk ID should be 16 characters (SHA256 hex digest truncated)"


def test_chunk_deterministic_id_generation_different_inputs():
    """Test that generate_chunk_id produces different IDs for different inputs."""
    # Test with section_path (section_path takes precedence over page_span)
    base_args_with_section = {
        "doc_id": "doc123",
        "page_span": (1, 3),
        "section_path": ["Introduction"],
        "embedding_model_id": "fastembed/all-MiniLM-L6-v2",
        "chunk_idx": 0,
    }
    
    base_id_section = generate_chunk_id(**base_args_with_section)
    
    # Change doc_id
    id_doc = generate_chunk_id(**{**base_args_with_section, "doc_id": "doc456"})
    assert id_doc != base_id_section, "Different doc_id should produce different chunk ID"
    
    # Change section_path (this affects ID when section_path is present)
    id_section = generate_chunk_id(**{**base_args_with_section, "section_path": ["Conclusion"]})
    assert id_section != base_id_section, "Different section_path should produce different chunk ID"
    
    # Change embedding_model_id
    id_model = generate_chunk_id(**{**base_args_with_section, "embedding_model_id": "openai/text-embedding-ada-002"})
    assert id_model != base_id_section, "Different embedding_model_id should produce different chunk ID"
    
    # Change chunk_idx
    id_idx = generate_chunk_id(**{**base_args_with_section, "chunk_idx": 1})
    assert id_idx != base_id_section, "Different chunk_idx should produce different chunk ID"
    
    # Test with page_span (when section_path is empty)
    base_args_with_page = {
        "doc_id": "doc123",
        "page_span": (1, 3),
        "section_path": [],  # Empty section_path
        "embedding_model_id": "fastembed/all-MiniLM-L6-v2",
        "chunk_idx": 0,
    }
    
    base_id_page = generate_chunk_id(**base_args_with_page)
    
    # Change page_span (affects ID when section_path is empty)
    id_page = generate_chunk_id(**{**base_args_with_page, "page_span": (2, 4)})
    assert id_page != base_id_page, "Different page_span should produce different chunk ID when section_path is empty"


def test_chunk_id_uses_section_path_when_available():
    """Test that section_path is used when available, otherwise page_span."""
    doc_id = "doc123"
    embedding_model_id = "fastembed/all-MiniLM-L6-v2"
    chunk_idx = 0
    
    # With section_path
    id_with_section = generate_chunk_id(
        doc_id=doc_id,
        page_span=(1, 3),
        section_path=["Chapter 1", "Section 1.1"],
        embedding_model_id=embedding_model_id,
        chunk_idx=chunk_idx,
    )
    
    # Without section_path (empty list)
    id_without_section = generate_chunk_id(
        doc_id=doc_id,
        page_span=(1, 3),
        section_path=[],
        embedding_model_id=embedding_model_id,
        chunk_idx=chunk_idx,
    )
    
    assert id_with_section != id_without_section, "Section path vs page span should produce different IDs"


def test_chunk_id_format():
    """Test that chunk IDs are hex strings of consistent length."""
    id1 = generate_chunk_id("doc1", (1, 1), [], "model1", 0)
    id2 = generate_chunk_id("doc2", (2, 2), ["section"], "model2", 1)
    
    assert all(c in "0123456789abcdef" for c in id1), "Chunk ID should be hexadecimal"
    assert all(c in "0123456789abcdef" for c in id2), "Chunk ID should be hexadecimal"
    assert len(id1) == len(id2) == 16, "All chunk IDs should be 16 characters"


def test_chunk_model_with_deterministic_id():
    """Test that Chunk model can be created with deterministic ID."""
    chunk_id = generate_chunk_id(
        doc_id="test-doc",
        page_span=(5, 7),
        section_path=["Chapter 2", "Section 2.1"],
        embedding_model_id="fastembed/all-MiniLM-L6-v2",
        chunk_idx=10,
    )
    
    chunk = Chunk(
        id=chunk_id,
        doc_id="test-doc",
        text="Test chunk text",
        page_span=(5, 7),
        section_heading="Section 2.1",
        section_path=["Chapter 2", "Section 2.1"],
        chunk_idx=10,
    )
    
    assert chunk.id == chunk_id
    assert chunk.doc_id == "test-doc"
    assert chunk.page_span == (5, 7)
    assert chunk.chunk_idx == 10


def test_chunk_validation():
    """Test that Chunk model validates input data."""
    chunk_id = generate_chunk_id("doc1", (1, 1), [], "model1", 0)
    
    # Valid chunk
    chunk = Chunk(
        id=chunk_id,
        doc_id="doc1",
        text="Valid text",
        page_span=(1, 5),
        chunk_idx=0,
    )
    assert chunk.page_span[0] <= chunk.page_span[1]
    
    # Invalid page span (should raise ValueError)
    try:
        invalid_chunk = Chunk(
            id=chunk_id,
            doc_id="doc1",
            text="Invalid",
            page_span=(5, 1),  # start > end
            chunk_idx=0,
        )
        assert False, "Should have raised ValueError for invalid page span"
    except ValueError:
        pass  # Expected
    
    # Invalid chunk_idx (should raise ValueError)
    try:
        invalid_chunk = Chunk(
            id=chunk_id,
            doc_id="doc1",
            text="Invalid",
            page_span=(1, 1),
            chunk_idx=-1,  # negative
        )
        assert False, "Should have raised ValueError for negative chunk_idx"
    except ValueError:
        pass  # Expected


def test_conversion_result_structure():
    """Test ConversionResult model structure validation."""
    result = ConversionResult(
        doc_id="doc123",
        structure={
            "heading_tree": {"root": []},
            "page_map": {1: 0, 2: 100},
        },
        plain_text="Converted text content",
    )
    
    assert result.doc_id == "doc123"
    assert "heading_tree" in result.structure
    assert "page_map" in result.structure
    assert result.plain_text == "Converted text content"


def test_citation_meta_validation():
    """Test CitationMeta model validation."""
    # Valid with DOI
    meta1 = CitationMeta(
        citekey="test2024",
        title="Test Title",
        authors=["Author One", "Author Two"],
        year=2024,
        doi="10.1000/test",
    )
    assert meta1.doi == "10.1000/test"
    assert meta1.url is None
    
    # Valid with URL (no DOI)
    meta2 = CitationMeta(
        citekey="test2024b",
        title="Test Title 2",
        authors=["Author Three"],
        year=2024,
        url="https://example.com/test",
    )
    assert meta2.url == "https://example.com/test"
    assert meta2.doi is None

