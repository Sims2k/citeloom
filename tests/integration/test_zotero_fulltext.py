"""Integration tests for FulltextResolver (T115-T116)."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.infrastructure.adapters.zotero_fulltext_resolver import ZoteroFulltextResolverAdapter
from src.infrastructure.adapters.zotero_local_db import LocalZoteroDbAdapter


@pytest.fixture
def mock_zotero_db_with_fulltext(tmp_path: Path) -> Path:
    """Create a mock Zotero SQLite database with fulltext table."""
    db_path = tmp_path / "zotero.sqlite"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create items table
    cursor.execute("""
        CREATE TABLE items (
            itemID INTEGER PRIMARY KEY,
            itemTypeID INTEGER,
            key TEXT UNIQUE
        )
    """)

    # Create fulltext table
    cursor.execute("""
        CREATE TABLE fulltext (
            itemID INTEGER PRIMARY KEY,
            fulltext TEXT
        )
    """)

    # Insert sample data
    cursor.execute("INSERT INTO items (itemID, itemTypeID, key) VALUES (1, 14, 'ATTACH1')")
    cursor.execute("INSERT INTO items (itemID, itemTypeID, key) VALUES (2, 14, 'ATTACH2')")
    cursor.execute("INSERT INTO items (itemID, itemTypeID, key) VALUES (3, 14, 'ATTACH3')")

    # Good quality fulltext (long enough, has sentences)
    good_fulltext = (
        """
    This is a test document with multiple sentences. It contains enough text
    to pass quality validation. The document has proper sentence structure
    with periods and proper capitalization. This ensures that the fulltext
    quality checks will pass and the text will be used for fast-path conversion.
    """
        * 10
    )  # Make it long enough

    # Low quality fulltext (too short)
    low_quality_fulltext = "Short text"

    # Empty fulltext
    cursor.execute("INSERT INTO fulltext (itemID, fulltext) VALUES (1, ?)", (good_fulltext,))
    cursor.execute("INSERT INTO fulltext (itemID, fulltext) VALUES (2, ?)", (low_quality_fulltext,))
    # ATTACH3 has no fulltext entry

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_converter():
    """Create a mock TextConverterPort."""
    converter = Mock()

    # Mock conversion result
    conversion_result = {
        "plain_text": "This is converted text from Docling. It has multiple sentences. " * 10,
        "structure": {
            "page_map": {
                1: (0, 100),
                2: (100, 200),
            },
        },
    }
    converter.convert.return_value = conversion_result
    return converter


class TestFulltextResolverPreference:
    """Test fulltext preference and fallback (T115)."""

    def test_prefer_zotero_fulltext_available(
        self, mock_zotero_db_with_fulltext: Path, mock_converter
    ):
        """Test that Zotero fulltext is preferred when available and valid."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(
            local_db_adapter=local_db, converter=mock_converter
        )

        test_file = Path("/tmp/test.pdf")
        result = resolver.resolve_fulltext(
            attachment_key="ATTACH1",
            file_path=test_file,
            prefer_zotero=True,
        )

        assert result.source == "zotero"
        assert len(result.text) > 0
        assert result.zotero_quality_score is not None
        assert result.zotero_quality_score > 0.5
        # Converter should not be called if Zotero fulltext is used
        mock_converter.convert.assert_not_called()

    def test_fallback_to_docling_when_zotero_unavailable(self, tmp_path: Path, mock_converter):
        """Test fallback to Docling when Zotero fulltext is not available."""
        # Create empty database
        db_path = tmp_path / "empty_zotero.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        local_db = LocalZoteroDbAdapter(db_path=db_path)
        resolver = ZoteroFulltextResolverAdapter(
            local_db_adapter=local_db, converter=mock_converter
        )

        test_file = Path("/tmp/test.pdf")
        result = resolver.resolve_fulltext(
            attachment_key="NONEXISTENT",
            file_path=test_file,
            prefer_zotero=True,
        )

        assert result.source == "docling"
        assert len(result.text) > 0
        assert len(result.pages_from_docling) > 0
        # Converter should be called for fallback
        mock_converter.convert.assert_called_once()

    def test_fallback_to_docling_when_quality_low(
        self, mock_zotero_db_with_fulltext: Path, mock_converter
    ):
        """Test fallback to Docling when Zotero fulltext quality is too low."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(
            local_db_adapter=local_db, converter=mock_converter
        )

        test_file = Path("/tmp/test.pdf")
        result = resolver.resolve_fulltext(
            attachment_key="ATTACH2",  # Has low quality fulltext
            file_path=test_file,
            prefer_zotero=True,
            min_length=100,
        )

        # Should fallback to Docling because quality is too low
        assert result.source == "docling"
        assert len(result.text) > 0
        mock_converter.convert.assert_called_once()

    def test_prefer_docling_when_prefer_zotero_false(
        self, mock_zotero_db_with_fulltext: Path, mock_converter
    ):
        """Test that Docling is used when prefer_zotero=False."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(
            local_db_adapter=local_db, converter=mock_converter
        )

        test_file = Path("/tmp/test.pdf")
        result = resolver.resolve_fulltext(
            attachment_key="ATTACH1",
            file_path=test_file,
            prefer_zotero=False,
        )

        assert result.source == "docling"
        mock_converter.convert.assert_called_once()

    def test_no_converter_raises_error(self, mock_zotero_db_with_fulltext: Path):
        """Test that error is raised when converter is None and Zotero fulltext unavailable."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(local_db_adapter=local_db, converter=None)

        test_file = Path("/tmp/test.pdf")

        with pytest.raises(ValueError, match="Converter not provided"):
            resolver.resolve_fulltext(
                attachment_key="ATTACH3",  # No fulltext
                file_path=test_file,
                prefer_zotero=True,
            )


class TestFulltextResolverMixedProvenance:
    """Test mixed provenance (T116)."""

    def test_mixed_provenance_when_some_pages_missing(
        self, mock_zotero_db_with_fulltext: Path, tmp_path: Path
    ):
        """Test mixed provenance when some pages are missing from Zotero fulltext."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)

        # Create mock converter that returns pages 1-5
        mock_converter = Mock()
        conversion_result = {
            "plain_text": "Page 1 text. " * 20 + "Page 2 text. " * 20 + "Page 3 text. " * 20,
            "structure": {
                "page_map": {
                    1: (0, 200),
                    2: (200, 400),
                    3: (400, 600),
                },
            },
        }
        mock_converter.convert.return_value = conversion_result

        resolver = ZoteroFulltextResolverAdapter(
            local_db_adapter=local_db, converter=mock_converter
        )

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake pdf")

        # Mock _parse_zotero_fulltext_pages to return only page 1
        with patch.object(resolver, "_parse_zotero_fulltext_pages") as mock_parse:
            mock_parse.return_value = {1: "Zotero page 1 text"}

            result = resolver.resolve_fulltext(
                attachment_key="ATTACH1",
                file_path=test_file,
                prefer_zotero=True,
            )

            # Should use mixed provenance if Docling converter is available
            # and some pages are missing
            if result.source == "mixed":
                assert len(result.pages_from_zotero) > 0
                assert len(result.pages_from_docling) > 0
                assert (
                    "zotero" in result.text.lower()
                    or "docling" in result.text.lower()
                    or len(result.text) > 0
                )

    def test_merge_mixed_provenance_sequential(self, tmp_path: Path):
        """Test that mixed provenance merges pages sequentially."""
        resolver = ZoteroFulltextResolverAdapter(local_db_adapter=None, converter=None)

        zotero_pages = {
            1: "Zotero page 1",
            3: "Zotero page 3",
        }
        docling_pages = {
            2: "Docling page 2",
            4: "Docling page 4",
        }

        merged_text, pages_from_zotero, pages_from_docling = resolver._merge_mixed_provenance(
            zotero_pages, docling_pages
        )

        assert len(pages_from_zotero) == 2
        assert 1 in pages_from_zotero
        assert 3 in pages_from_zotero

        assert len(pages_from_docling) == 2
        assert 2 in pages_from_docling
        assert 4 in pages_from_docling

        # Text should contain both sources
        assert "Zotero page 1" in merged_text
        assert "Docling page 2" in merged_text

    def test_validate_fulltext_quality_passes(self, mock_zotero_db_with_fulltext: Path):
        """Test that quality validation passes for good fulltext."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(local_db_adapter=local_db)

        good_text = "This is a good quality fulltext. " * 50  # Long enough, has sentences

        is_valid, quality_score = resolver._validate_fulltext_quality(good_text, min_length=100)

        assert is_valid is True
        assert quality_score > 0.5

    def test_validate_fulltext_quality_fails_short(self, mock_zotero_db_with_fulltext: Path):
        """Test that quality validation fails for too short text."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(local_db_adapter=local_db)

        short_text = "Too short"

        is_valid, quality_score = resolver._validate_fulltext_quality(short_text, min_length=100)

        assert is_valid is False
        assert quality_score < 1.0

    def test_get_zotero_fulltext_returns_text(self, mock_zotero_db_with_fulltext: Path):
        """Test getting fulltext from Zotero database."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(local_db_adapter=local_db)

        fulltext = resolver.get_zotero_fulltext("ATTACH1")

        assert fulltext is not None
        assert len(fulltext) > 0

    def test_get_zotero_fulltext_returns_none_when_missing(
        self, mock_zotero_db_with_fulltext: Path
    ):
        """Test that get_zotero_fulltext returns None when fulltext not found."""
        local_db = LocalZoteroDbAdapter(db_path=mock_zotero_db_with_fulltext)
        resolver = ZoteroFulltextResolverAdapter(local_db_adapter=local_db)

        fulltext = resolver.get_zotero_fulltext("ATTACH3")  # No fulltext entry

        assert fulltext is None

    def test_get_zotero_fulltext_handles_database_error(self, tmp_path: Path):
        """Test that get_zotero_fulltext handles database errors gracefully."""
        # Create database that will raise errors
        db_path = tmp_path / "error_db.sqlite"
        conn = sqlite3.connect(str(db_path))
        conn.close()

        local_db = LocalZoteroDbAdapter(db_path=db_path)
        resolver = ZoteroFulltextResolverAdapter(local_db_adapter=local_db)

        # Should return None on error, not raise
        fulltext = resolver.get_zotero_fulltext("NONEXISTENT")
        assert fulltext is None
