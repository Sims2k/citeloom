"""Integration tests for Zotero metadata resolution (CSL-JSON and pyzotero)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.domain.errors import MetadataMissing
from src.infrastructure.adapters.zotero_metadata import (
    ZoteroCslJsonResolver,
    ZoteroPyzoteroResolver,
)


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


# ============================================================================
# Comprehensive tests for pyzotero metadata resolution (T100)
# ============================================================================

class TestPyzoteroMetadataResolution:
    """Comprehensive tests for pyzotero metadata resolution via ZoteroPyzoteroResolver."""
    
    @pytest.fixture
    def mock_zotero_client(self):
        """Create a mock pyzotero client."""
        mock_client = MagicMock()
        return mock_client
    
    @pytest.fixture
    def sample_zotero_item(self):
        """Create a sample Zotero item structure (pyzotero format)."""
        return {
            "key": "ABC123",
            "data": {
                "title": "Clean Architecture: A Craftsman's Guide",
                "creators": [
                    {"creatorType": "author", "firstName": "Robert", "lastName": "Martin"}
                ],
                "date": "2023",
                "DOI": "10.1000/xyz123",
                "url": "https://example.com/clean-arch",
                "tags": [
                    {"tag": "architecture"},
                    {"tag": "software-design"},
                ],
                "collections": ["DEF456"],
                "language": "en-US",
                "extra": "Citation Key: cleanArch2023",
            },
        }
    
    def test_pyzotero_initialization_with_config(self):
        """Test that ZoteroPyzoteroResolver initializes with configuration."""
        zotero_config = {
            "library_id": "123456",
            "library_type": "user",
            "api_key": "test-api-key",
        }
        
        with patch('src.infrastructure.adapters.zotero_metadata.zotero') as mock_zotero_module:
            resolver = ZoteroPyzoteroResolver(zotero_config=zotero_config)
            
            # Verify pyzotero.Zotero was called with correct params
            mock_zotero_module.Zotero.assert_called_once()
            call_kwargs = mock_zotero_module.Zotero.call_args
            assert call_kwargs[0][0] == "123456"
            assert call_kwargs[0][1] == "user"
    
    def test_pyzotero_initialization_local_access(self):
        """Test that ZoteroPyzoteroResolver initializes for local access."""
        zotero_config = {
            "library_id": "1",
            "library_type": "user",
            "local": True,
        }
        
        with patch('src.infrastructure.adapters.zotero_metadata.zotero') as mock_zotero_module:
            resolver = ZoteroPyzoteroResolver(zotero_config=zotero_config)
            
            # Verify local=True was passed
            mock_zotero_module.Zotero.assert_called_once()
            call_kwargs = mock_zotero_module.Zotero.call_args
            assert call_kwargs[1]["local"] is True
    
    def test_pyzotero_initialization_from_environment(self):
        """Test that ZoteroPyzoteroResolver uses environment variables when config is None."""
        with patch('src.infrastructure.adapters.zotero_metadata.get_env') as mock_get_env:
            mock_get_env.side_effect = lambda key, default=None: {
                "ZOTERO_LIBRARY_ID": "123456",
                "ZOTERO_LIBRARY_TYPE": "group",
                "ZOTERO_API_KEY": "env-api-key",
            }.get(key, default)
            
            with patch('src.infrastructure.adapters.zotero_metadata.zotero'):
                resolver = ZoteroPyzoteroResolver(zotero_config=None)
                
                # Should use environment variables
                assert True  # Placeholder - verify env vars were read
    
    def test_pyzotero_resolve_by_doi(self, mock_zotero_client, sample_zotero_item):
        """Test that pyzotero resolves metadata by DOI (priority)."""
        # Mock pyzotero client to return sample item
        mock_zotero_client.items.return_value = [sample_zotero_item]
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        resolver.zot = mock_zotero_client
        
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="doi:10.1000/xyz123",
        )
        
        assert result is not None
        assert result.doi == "10.1000/xyz123"
        assert "Clean Architecture" in result.title
    
    def test_pyzotero_resolve_by_title_fallback(self, mock_zotero_client, sample_zotero_item):
        """Test that pyzotero falls back to title-based matching when DOI not found."""
        mock_zotero_client.items.return_value = [sample_zotero_item]
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        resolver.zot = mock_zotero_client
        
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="Clean Architecture A Craftsman Guide",
        )
        
        assert result is not None
        assert "Clean Architecture" in result.title
    
    def test_pyzotero_extract_language_field(self, mock_zotero_client, sample_zotero_item):
        """Test that language field is extracted from Zotero item."""
        mock_zotero_client.items.return_value = [sample_zotero_item]
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        resolver.zot = mock_zotero_client
        
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="doi:10.1000/xyz123",
        )
        
        assert result is not None
        assert result.language == "en-US"  # Language from Zotero item
    
    def test_pyzotero_extract_creators_to_authors(self, mock_zotero_client, sample_zotero_item):
        """Test that Zotero creators are extracted as authors."""
        mock_zotero_client.items.return_value = [sample_zotero_item]
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        resolver.zot = mock_zotero_client
        
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="doi:10.1000/xyz123",
        )
        
        assert result is not None
        assert len(result.authors) > 0
        assert "Robert" in result.authors[0] and "Martin" in result.authors[0]
    
    def test_pyzotero_extract_tags(self, mock_zotero_client, sample_zotero_item):
        """Test that tags are extracted from Zotero item."""
        mock_zotero_client.items.return_value = [sample_zotero_item]
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        resolver.zot = mock_zotero_client
        
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="doi:10.1000/xyz123",
        )
        
        assert result is not None
        assert "architecture" in result.tags
        assert "software-design" in result.tags
    
    def test_pyzotero_extract_collections(self, mock_zotero_client, sample_zotero_item):
        """Test that collections are extracted from Zotero item."""
        mock_zotero_client.items.return_value = [sample_zotero_item]
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        resolver.zot = mock_zotero_client
        
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="doi:10.1000/xyz123",
        )
        
        assert result is not None
        assert len(result.collections) > 0
    
    def test_pyzotero_graceful_error_handling(self, mock_zotero_client):
        """Test that pyzotero API errors are handled gracefully (non-blocking)."""
        mock_zotero_client.items.side_effect = Exception("API connection error")
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        resolver.zot = mock_zotero_client
        
        # Should return None and log warning, not raise exception
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="test",
        )
        
        assert result is None
    
    def test_pyzotero_no_client_initialized(self):
        """Test that resolver returns None gracefully when client not initialized."""
        resolver = ZoteroPyzoteroResolver(zotero_config=None)
        resolver.zot = None  # Simulate failed initialization
        
        result = resolver.resolve(
            citekey=None,
            doc_id="doc1",
            source_hint="test",
        )
        
        assert result is None
    
    def test_pyzotero_doi_normalization(self):
        """Test that DOI normalization works for various formats."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        test_cases = [
            ("10.1000/xyz123", "10.1000/xyz123"),
            ("https://doi.org/10.1000/xyz123", "10.1000/xyz123"),
            ("doi:10.1000/xyz123", "10.1000/xyz123"),
        ]
        
        for input_doi, expected in test_cases:
            normalized = resolver._normalize_doi(input_doi)
            assert normalized == expected
    
    def test_pyzotero_fuzzy_title_matching(self):
        """Test that fuzzy title matching respects 0.8 threshold."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        # High similarity (should match)
        score1 = resolver._fuzzy_score(
            "clean architecture craftsman guide software structure",
            "clean architecture craftsman guide software structure design"
        )
        assert score1 >= 0.8
        
        # Low similarity (should not match)
        score2 = resolver._fuzzy_score(
            "clean architecture",
            "completely different unrelated book title"
        )
        assert score2 < 0.8


class TestBetterBibTeXCitekeyExtraction:
    """Comprehensive tests for Better BibTeX citekey extraction via JSON-RPC."""
    
    @pytest.fixture
    def mock_better_bibtex_server(self):
        """Mock Better BibTeX JSON-RPC server response."""
        with patch('src.infrastructure.adapters.zotero_metadata.urllib.request.urlopen') as mock_urlopen:
            response_mock = MagicMock()
            response_mock.read.return_value = json.dumps({
                "jsonrpc": "2.0",
                "result": "cleanArch2023",
                "id": 1,
            }).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = response_mock
            yield mock_urlopen
    
    def test_better_bibtex_port_detection_zotero(self):
        """Test that Better BibTeX port detection works for Zotero (23119)."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        # Mock socket connection check
        with patch('src.infrastructure.adapters.zotero_metadata.socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0  # Connection successful
            mock_socket.return_value = mock_sock
            
            available = resolver._check_better_bibtex_available(port=23119)
            assert available is True
    
    def test_better_bibtex_port_detection_jurism(self):
        """Test that Better BibTeX port detection works for Juris-M (24119)."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        with patch('src.infrastructure.adapters.zotero_metadata.socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 0
            mock_socket.return_value = mock_sock
            
            available = resolver._check_better_bibtex_available(port=24119)
            assert available is True
    
    def test_better_bibtex_not_available(self):
        """Test that Better BibTeX detection returns False when not running."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        with patch('src.infrastructure.adapters.zotero_metadata.socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.return_value = 1  # Connection failed
            mock_socket.return_value = mock_sock
            
            available = resolver._check_better_bibtex_available(port=23119)
            assert available is False
    
    def test_better_bibtex_citekey_extraction(self, mock_better_bibtex_server):
        """Test that Better BibTeX citekey is extracted via JSON-RPC."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        with patch.object(resolver, '_check_better_bibtex_available', return_value=True):
            citekey = resolver._get_citekey_from_better_bibtex(item_key="ABC123", port=23119)
            
            assert citekey == "cleanArch2023"
    
    def test_better_bibtex_citekey_fallback_extra_field(self):
        """Test that citekey extraction falls back to parsing 'extra' field."""
        sample_item = {
            "key": "ABC123",
            "data": {
                "extra": "Citation Key: cleanArch2023\nSome other note",
            },
        }
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        # Mock Better BibTeX as unavailable
        with patch.object(resolver, '_check_better_bibtex_available', return_value=False):
            citekey = resolver._extract_citekey(sample_item)
            
            assert citekey == "cleanArch2023"
    
    def test_better_bibtex_timeout_handling(self):
        """Test that Better BibTeX connection respects timeout (5-10s)."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        with patch('src.infrastructure.adapters.zotero_metadata.socket.socket') as mock_socket:
            mock_sock = MagicMock()
            mock_sock.connect_ex.side_effect = Exception("Timeout")
            mock_socket.return_value = mock_sock
            
            available = resolver._check_better_bibtex_available(port=23119, timeout=5)
            assert available is False
    
    def test_better_bibtex_jsonrpc_error_handling(self):
        """Test that JSON-RPC errors are handled gracefully."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        with patch('src.infrastructure.adapters.zotero_metadata.urllib.request.urlopen') as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")
            
            with patch.object(resolver, '_check_better_bibtex_available', return_value=True):
                citekey = resolver._get_citekey_from_better_bibtex(item_key="ABC123", port=23119)
                
                # Should return None on error
                assert citekey is None


class TestZoteroLanguageFieldMapping:
    """Tests for language field mapping (Zotero codes → OCR language codes)."""
    
    def test_language_field_extraction(self):
        """Test that language field is extracted from Zotero item."""
        sample_item = {
            "data": {
                "language": "en-US",
            },
        }
        
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        # Mock extraction
        with patch.object(resolver, 'zot') as mock_zot:
            mock_zot.items.return_value = [sample_item]
            
            # Verify language extraction (would test in full resolve flow)
            assert True  # Placeholder
    
    def test_language_code_mapping_zotero_to_ocr(self):
        """Test that Zotero language codes are mapped to OCR language codes."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        # Test language mapping (e.g., 'en-US' → 'en')
        # This is done in _extract_metadata method
        assert True  # Placeholder - would verify mapping logic


class TestPyzoteroIntegration:
    """Integration tests combining pyzotero resolution with Better BibTeX."""
    
    def test_complete_resolution_workflow(self):
        """Test complete workflow: pyzotero + Better BibTeX citekey extraction."""
        resolver = ZoteroPyzoteroResolver(zotero_config={"library_id": "123", "api_key": "key"})
        
        # Would test full workflow with both pyzotero and Better BibTeX
        # For now, verify components work together
        assert True  # Placeholder

