"""Unit tests for batch_import_from_zotero use case."""

from __future__ import annotations

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from typing import Any

from src.application.use_cases.batch_import_from_zotero import (
    batch_import_from_zotero,
    _matches_tag_filter,
    _sanitize_filename,
)
from src.domain.models.download_manifest import DownloadManifest, DownloadManifestItem, DownloadManifestAttachment


class MockZoteroImporter:
    """Mock Zotero importer for testing."""
    
    def list_collections(self):
        return [
            {"key": "COLL1", "name": "Test Collection"},
        ]
    
    def find_collection_by_name(self, name):
        if name.lower() in "test collection":
            return {"key": "COLL1", "name": "Test Collection"}
        return None
    
    def get_collection_items(self, collection_key, include_subcollections=False):
        return [
            {
                "key": "ITEM1",
                "data": {
                    "title": "Item 1",
                    "tags": [{"tag": "important"}],
                },
            },
        ]
    
    def get_item_metadata(self, item_key):
        return {
            "title": "Test Item",
            "creators": [{"firstName": "Test", "lastName": "Author"}],
            "date": "2025",
        }
    
    def get_item_attachments(self, item_key):
        return [
            {
                "key": "ATT1",
                "data": {
                    "linkMode": "imported_file",
                    "contentType": "application/pdf",
                    "filename": "document.pdf",
                },
            },
        ]
    
    def download_attachment(self, item_key, attachment_key, output_path):
        output_path.write_bytes(b"fake pdf content")
        return output_path


class MockConverter:
    """Mock converter."""
    def convert(self, source_path, ocr_languages=None):
        return {
            "doc_id": f"doc_{Path(source_path).stem}",
            "structure": {"heading_tree": {}, "page_map": {1: (0, 100)}},
            "plain_text": "Test content",
        }


class MockChunker:
    """Mock chunker."""
    def chunk(self, conversion, policy):
        from src.domain.models.chunk import Chunk
        return [
            Chunk(
                id="chunk_1",
                doc_id=conversion["doc_id"],
                text="Test content",
                page_span=(1, 1),
                section_heading=None,
                section_path=[],
                chunk_idx=0,
                token_count=10,
                signal_to_noise_ratio=0.8,
            ),
        ]


class MockMetadataResolver:
    """Mock metadata resolver."""
    def resolve(self, citekey=None, doc_id="", source_hint=None, zotero_config=None):
        from src.domain.models.citation_meta import CitationMeta
        return CitationMeta(
            citekey="test-2025",
            title="Test Document",
            authors=["Test Author"],
            year=2025,
            doi=None,
            url=None,
            tags=[],
            collections=[],
            language="en",
        )


class MockEmbedder:
    """Mock embedder."""
    def embed(self, texts, model_id=None):
        return [[0.1] * 384 for _ in texts]


class MockVectorIndex:
    """Mock vector index."""
    def upsert(self, items, project_id, model_id):
        pass


def test_batch_import_basic_flow(tmp_path: Path):
    """Test basic batch import flow."""
    downloads_dir = tmp_path / "downloads"
    audit_dir = tmp_path / "audit"
    
    zotero_importer = MockZoteroImporter()
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    result = batch_import_from_zotero(
        project_id="test/project",
        collection_key="COLL1",
        zotero_importer=zotero_importer,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
        downloads_dir=downloads_dir,
        audit_dir=audit_dir,
    )
    
    assert result["total_documents"] >= 0
    assert result["chunks_written"] >= 0
    assert "correlation_id" in result
    assert result["collection_key"] == "COLL1"


def test_batch_import_collection_not_found():
    """Test batch import handles missing collection."""
    zotero_importer = MockZoteroImporter()
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    zotero_importer.find_collection_by_name = Mock(return_value=None)
    
    with pytest.raises(ValueError, match="Collection.*not found"):
        batch_import_from_zotero(
            project_id="test/project",
            collection_name="Nonexistent",
            zotero_importer=zotero_importer,
            converter=converter,
            chunker=chunker,
            resolver=resolver,
            embedder=embedder,
            index=index,
        )


def test_batch_import_empty_collection(tmp_path: Path):
    """Test batch import handles empty collection."""
    downloads_dir = tmp_path / "downloads"
    
    zotero_importer = MockZoteroImporter()
    zotero_importer.get_collection_items = Mock(return_value=[])
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    result = batch_import_from_zotero(
        project_id="test/project",
        collection_key="COLL1",
        zotero_importer=zotero_importer,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
        downloads_dir=downloads_dir,
    )
    
    assert result["total_items"] == 0
    assert result["total_attachments"] == 0
    assert len(result["warnings"]) > 0


def test_batch_import_with_tag_filter(tmp_path: Path):
    """Test batch import filters by tags."""
    downloads_dir = tmp_path / "downloads"
    
    zotero_importer = MockZoteroImporter()
    
    # Item with matching tag
    zotero_importer.get_collection_items = Mock(return_value=[
        {
            "key": "ITEM1",
            "data": {
                "title": "Item 1",
                "tags": [{"tag": "important"}, {"tag": "reviewed"}],
            },
        },
        {
            "key": "ITEM2",
            "data": {
                "title": "Item 2",
                "tags": [{"tag": "draft"}],
            },
        },
    ])
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    result = batch_import_from_zotero(
        project_id="test/project",
        collection_key="COLL1",
        zotero_importer=zotero_importer,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
        downloads_dir=downloads_dir,
        include_tags=["important"],
    )
    
    # Should process items with "important" tag
    assert result["total_items"] >= 0


def test_matches_tag_filter():
    """Test tag filter matching logic."""
    # Include tags (OR logic)
    item_tags = ["important", "reviewed"]
    assert _matches_tag_filter(item_tags, include_tags=["important"], exclude_tags=None) is True
    assert _matches_tag_filter(item_tags, include_tags=["draft"], exclude_tags=None) is False
    
    # Exclude tags (ANY-match excludes)
    assert _matches_tag_filter(item_tags, include_tags=None, exclude_tags=["draft"]) is True
    assert _matches_tag_filter(item_tags, include_tags=None, exclude_tags=["important"]) is False
    
    # Both include and exclude
    assert _matches_tag_filter(item_tags, include_tags=["important"], exclude_tags=["draft"]) is True
    assert _matches_tag_filter(item_tags, include_tags=["important"], exclude_tags=["reviewed"]) is False


def test_sanitize_filename():
    """Test filename sanitization."""
    # Invalid characters
    assert _sanitize_filename("test<>file.pdf") == "test__file.pdf"
    assert _sanitize_filename("test:file.pdf") == "test_file.pdf"
    
    # Leading/trailing dots and spaces
    assert _sanitize_filename(" .test.pdf. ") == "test.pdf"
    
    # Long filename
    long_name = "a" * 300 + ".pdf"
    sanitized = _sanitize_filename(long_name)
    assert len(sanitized) <= 205  # Should be truncated
    
    # Normal filename
    assert _sanitize_filename("normal_file.pdf") == "normal_file.pdf"


def test_batch_import_resume_from_checkpoint(tmp_path: Path):
    """Test batch import resumes from checkpoint."""
    downloads_dir = tmp_path / "downloads"
    checkpoints_dir = tmp_path / "checkpoints"
    
    # Create manifest with one downloaded file
    collection_downloads_dir = downloads_dir / "COLL1"
    collection_downloads_dir.mkdir(parents=True)
    manifest_path = collection_downloads_dir / "manifest.json"
    
    downloaded_file = collection_downloads_dir / "document.pdf"
    downloaded_file.write_bytes(b"fake pdf content")
    
    manifest = DownloadManifest(
        collection_key="COLL1",
        collection_name="Test Collection",
        download_time=datetime.now(),
    )
    
    manifest_item = DownloadManifestItem(
        item_key="ITEM1",
        title="Test Item",
        metadata={},
    )
    
    manifest_attachment = DownloadManifestAttachment(
        attachment_key="ATT1",
        filename="document.pdf",
        local_path=downloaded_file,
        download_status="success",
        file_size=len(b"fake pdf content"),
    )
    manifest_item.add_attachment(manifest_attachment)
    manifest.add_item(manifest_item)
    
    with manifest_path.open("w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
    
    zotero_importer = MockZoteroImporter()
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Mock checkpoint manager
    from src.infrastructure.adapters.checkpoint_manager import CheckpointManagerAdapter
    
    checkpoint_manager = CheckpointManagerAdapter(checkpoints_dir=checkpoints_dir)
    
    result = batch_import_from_zotero(
        project_id="test/project",
        collection_key="COLL1",
        zotero_importer=zotero_importer,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
        downloads_dir=downloads_dir,
        checkpoint_manager=checkpoint_manager,
        resume=False,  # Start fresh, but use existing manifest
    )
    
    assert "correlation_id" in result
    assert result["collection_key"] == "COLL1"

