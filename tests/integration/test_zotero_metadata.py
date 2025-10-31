"""Integration tests for Zotero CSL-JSON metadata matching."""

import json
import tempfile
from pathlib import Path

import pytest

from src.domain.errors import MetadataMissing
from src.infrastructure.adapters.zotero_metadata import ZoteroCslJsonResolver


@pytest.fixture
def sample_csl_json():
    """Create a sample CSL-JSON file with test items."""
    items = [
        {
            "id": "cleanArchitecture2023",
            "type": "book",
            "title": "Clean Architecture: A Craftsman's Guide to Software Structure and Design",
            "author": [
                {"given": "Robert", "family": "Martin"},
            ],
            "issued": {"date-parts": [[2023]]},
            "DOI": "10.1000/xyz123",
            "URL": "https://example.com/clean-arch",
            "tags": ["architecture", "software-design"],
            "collections": ["books"],
        },
        {
            "id": "dddBook2003",
            "type": "book",
            "title": "Domain-Driven Design: Tackling Complexity in the Heart of Software",
            "author": [
                {"given": "Eric", "family": "Evans"},
            ],
            "issued": {"date-parts": [[2003]]},
            "DOI": "10.1000/ddd123",
            "URL": "https://example.com/ddd",
            "tags": ["ddd", "architecture"],
            "collections": ["books"],
        },
        {
            "id": "unknownDoc",
            "type": "article",
            "title": "Unknown Document",
            "author": [{"given": "John", "family": "Doe"}],
            "issued": {"date-parts": [[2020]]},
            # No DOI, URL only
            "URL": "https://example.com/unknown",
        },
    ]
    
    return {"items": items}


@pytest.fixture
def references_file(sample_csl_json):
    """Create a temporary CSL-JSON references file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_csl_json, f, indent=2)
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


def test_zotero_metadata_match_by_doi(references_file, sample_csl_json):
    """Test that metadata is matched correctly by DOI."""
    resolver = ZoteroCslJsonResolver()
    
    # Match by DOI
    result = resolver.resolve(
        citekey=None,
        references_path=references_file,
        doc_id="doc1",
        source_hint="doi:10.1000/xyz123",
    )
    
    assert result is not None, "Should match by DOI"
    assert result.citekey == "cleanArchitecture2023"
    assert result.title == "Clean Architecture: A Craftsman's Guide to Software Structure and Design"
    assert result.doi == "10.1000/xyz123"
    assert len(result.authors) == 1
    assert result.authors[0] == "Robert Martin"
    assert result.year == 2023


def test_zotero_metadata_match_by_doi_normalized(references_file):
    """Test that DOI matching handles normalized formats."""
    resolver = ZoteroCslJsonResolver()
    
    # Test with URL-prefixed DOI
    result = resolver.resolve(
        citekey=None,
        references_path=references_file,
        doc_id="doc1",
        source_hint="https://doi.org/10.1000/xyz123",
    )
    
    assert result is not None, "Should match normalized DOI"
    assert result.doi == "10.1000/xyz123"


def test_zotero_metadata_match_by_title_fallback(references_file, sample_csl_json):
    """Test that metadata falls back to normalized title matching."""
    resolver = ZoteroCslJsonResolver()
    
    # Match by normalized title (using full title for high similarity score)
    # The normalized title matching should find this as it has most words in common
    result = resolver.resolve(
        citekey=None,
        references_path=references_file,
        doc_id="doc1",
        source_hint="Clean Architecture A Craftsman Guide to Software Structure and Design",
    )
    
    assert result is not None, "Should match by normalized title"
    assert result.citekey == "cleanArchitecture2023"
    assert "Clean Architecture" in result.title


def test_zotero_metadata_match_by_citekey(references_file):
    """Test that metadata can be matched by citekey."""
    resolver = ZoteroCslJsonResolver()
    
    result = resolver.resolve(
        citekey="dddBook2003",
        references_path=references_file,
        doc_id="doc1",
        source_hint=None,
    )
    
    assert result is not None, "Should match by citekey"
    assert result.citekey == "dddBook2003"
    assert "Domain-Driven Design" in result.title


def test_zotero_metadata_unknown_document(references_file):
    """Test that unknown documents return None and log MetadataMissing."""
    resolver = ZoteroCslJsonResolver()
    
    # Try to match non-existent document
    result = resolver.resolve(
        citekey=None,
        references_path=references_file,
        doc_id="nonexistent_doc",
        source_hint="completely unknown document title",
    )
    
    assert result is None, "Should return None for unknown document"


def test_zotero_metadata_missing_file():
    """Test that missing references file returns None gracefully."""
    resolver = ZoteroCslJsonResolver()
    
    result = resolver.resolve(
        citekey=None,
        references_path="/nonexistent/path/references.json",
        doc_id="doc1",
        source_hint=None,
    )
    
    assert result is None, "Should return None for missing file"


def test_zotero_metadata_extraction_authors(sample_csl_json):
    """Test that author extraction handles CSL-JSON format correctly."""
    resolver = ZoteroCslJsonResolver()
    
    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_csl_json, f)
        temp_path = f.name
    
    try:
        result = resolver.resolve(
            citekey="cleanArchitecture2023",
            references_path=temp_path,
            doc_id="doc1",
            source_hint=None,
        )
        
        assert result is not None
        assert len(result.authors) == 1
        assert result.authors[0] == "Robert Martin"  # "given family" format
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_zotero_metadata_extraction_tags_and_collections(references_file):
    """Test that tags and collections are extracted correctly."""
    resolver = ZoteroCslJsonResolver()
    
    result = resolver.resolve(
        citekey="cleanArchitecture2023",
        references_path=references_file,
        doc_id="doc1",
        source_hint=None,
    )
    
    assert result is not None
    assert "architecture" in result.tags
    assert "software-design" in result.tags
    assert "books" in result.collections


def test_zotero_metadata_fuzzy_title_threshold(references_file):
    """Test that fuzzy title matching respects threshold (0.8)."""
    resolver = ZoteroCslJsonResolver()
    
    # Very different title should not match
    result = resolver.resolve(
        citekey=None,
        references_path=references_file,
        doc_id="doc1",
        source_hint="completely different unrelated book title here",
    )
    
    assert result is None, "Should not match titles below threshold"


def test_zotero_metadata_no_doi_url_fallback(references_file):
    """Test that items with only URL (no DOI) still work."""
    resolver = ZoteroCslJsonResolver()
    
    result = resolver.resolve(
        citekey="unknownDoc",
        references_path=references_file,
        doc_id="doc1",
        source_hint=None,
    )
    
    assert result is not None
    assert result.doi is None
    assert result.url == "https://example.com/unknown"

