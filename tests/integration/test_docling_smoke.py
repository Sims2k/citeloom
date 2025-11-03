"""Integration tests for Docling document conversion and chunking."""

from pathlib import Path
import pytest
from src.domain.policy.chunking_policy import ChunkingPolicy
from src.infrastructure.adapters.docling_converter import DoclingConverterAdapter
from src.infrastructure.adapters.docling_chunker import DoclingHybridChunkerAdapter


@pytest.fixture
def sample_pdf_path():
    """Get path to sample PDF file if available."""
    pdf_path = Path("assets/raw/Keen - 2025 - Clean Architecture with Python Implement scalable and maintainable applications using proven archit.pdf")
    if pdf_path.exists():
        return str(pdf_path.absolute())
    return None


@pytest.fixture
def docling_converter():
    """Get Docling converter if available."""
    try:
        return DoclingConverterAdapter()
    except (ImportError, RuntimeError):
        pytest.skip("Docling not available")


def test_docling_conversion_page_map(docling_converter, sample_pdf_path):
    """Test that DoclingConverterAdapter produces conversion result with page map."""
    if not sample_pdf_path:
        pytest.skip("Sample PDF not available")
    
    result = docling_converter.convert(sample_pdf_path)
    
    # Verify conversion result structure
    assert "doc_id" in result, "Conversion result should contain doc_id"
    assert "structure" in result, "Conversion result should contain structure"
    
    structure = result.get("structure", {})
    assert "page_map" in structure, "Structure should contain page_map"
    
    page_map = structure.get("page_map", {})
    assert isinstance(page_map, dict), "page_map should be a dictionary"
    
    # Verify page_map maps page numbers to text offsets (or has placeholder structure)
    if page_map:
        for page_num, offset in page_map.items():
            assert isinstance(page_num, int), f"Page number should be int, got {type(page_num)}"
            assert isinstance(offset, int), f"Offset should be int, got {type(offset)}"


def test_docling_conversion_heading_tree(docling_converter, sample_pdf_path):
    """Test that DoclingConverterAdapter produces conversion result with heading tree."""
    if not sample_pdf_path:
        pytest.skip("Sample PDF not available")
    
    result = docling_converter.convert(sample_pdf_path)
    
    structure = result.get("structure", {})
    assert "heading_tree" in structure, "Structure should contain heading_tree"
    
    heading_tree = structure.get("heading_tree", {})
    assert isinstance(heading_tree, dict), "heading_tree should be a dictionary"


def test_docling_chunking_with_policy(docling_converter, sample_pdf_path):
    """Test that DoclingHybridChunkerAdapter chunks documents according to policy."""
    if not sample_pdf_path:
        pytest.skip("Sample PDF not available")
    
    chunker = DoclingHybridChunkerAdapter()
    
    # Convert a document
    conversion_result = docling_converter.convert(sample_pdf_path)
    
    # Create chunking policy
    policy = ChunkingPolicy(
        max_tokens=450,
        overlap_tokens=60,
        heading_context=2,
        tokenizer_id="minilm",
    )
    
    # Chunk the document
    chunks = chunker.chunk(conversion_result, policy)
    
    # Verify chunks were created
    assert len(chunks) > 0, "Should produce at least one chunk"
    
    # Verify chunk structure
    from src.domain.models.chunk import Chunk
    first_chunk = chunks[0]
    assert isinstance(first_chunk, Chunk), "Chunks should be Chunk objects"
    
    assert first_chunk.id, "Chunk should have deterministic ID"
    assert first_chunk.doc_id, "Chunk should have doc_id"
    assert first_chunk.text, "Chunk should have text"
    assert first_chunk.page_span, "Chunk should have page_span"
    assert isinstance(first_chunk.chunk_idx, int), "Chunk should have chunk_idx"


def test_docling_chunking_deterministic_ids(docling_converter, sample_pdf_path):
    """Test that chunking produces deterministic IDs for same inputs."""
    if not sample_pdf_path:
        pytest.skip("Sample PDF not available")
    
    chunker = DoclingHybridChunkerAdapter()
    
    conversion_result = docling_converter.convert(sample_pdf_path)
    policy = ChunkingPolicy(tokenizer_id="minilm")
    
    # Chunk twice with same inputs
    chunks1 = chunker.chunk(conversion_result, policy)
    chunks2 = chunker.chunk(conversion_result, policy)
    
    assert len(chunks1) == len(chunks2), "Same conversion should produce same number of chunks"
    
    # Verify IDs are deterministic
    for c1, c2 in zip(chunks1, chunks2):
        assert c1.id == c2.id, f"Chunk IDs should be deterministic: {c1.id} != {c2.id}"
        assert c1.doc_id == c2.doc_id
        assert c1.page_span == c2.page_span
        assert c1.chunk_idx == c2.chunk_idx


def test_docling_chunking_page_spans(docling_converter, sample_pdf_path):
    """Test that chunks have valid page spans."""
    if not sample_pdf_path:
        pytest.skip("Sample PDF not available")
    
    chunker = DoclingHybridChunkerAdapter()
    
    conversion_result = docling_converter.convert(sample_pdf_path)
    policy = ChunkingPolicy(tokenizer_id="minilm")
    
    chunks = chunker.chunk(conversion_result, policy)
    
    for chunk in chunks:
        assert len(chunk.page_span) == 2, "Page span should be tuple of (start, end)"
        start, end = chunk.page_span
        assert start <= end, f"Page span start ({start}) should be <= end ({end})"
        assert start > 0, "Page span start should be positive"
