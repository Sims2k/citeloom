"""Unit tests for ingest_document use case."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Any

from src.application.use_cases.ingest_document import ingest_document
from src.application.dto.ingest import IngestRequest, IngestResult
from src.domain.errors import ChunkingError
from src.domain.models.citation_meta import CitationMeta
from src.domain.policy.chunking_policy import ChunkingPolicy


class MockConverter:
    """Mock converter for testing."""
    
    def convert(self, source_path: str, ocr_languages: list[str] | None = None) -> dict[str, Any]:
        """Mock conversion."""
        return {
            "doc_id": f"doc_{Path(source_path).stem}",
            "structure": {
                "heading_tree": {},
                "page_map": {1: (0, 100)},
            },
            "plain_text": "Sample document text for testing purposes.",
        }


class MockChunker:
    """Mock chunker for testing."""
    
    def chunk(self, conversion: dict[str, Any], policy: ChunkingPolicy) -> list[dict[str, Any]]:
        """Mock chunking."""
        from src.domain.models.chunk import Chunk
        
        return [
            Chunk(
                id="chunk_1",
                doc_id=conversion["doc_id"],
                text="Sample document text for testing purposes.",
                page_span=(1, 1),
                section_heading=None,
                section_path=[],
                chunk_idx=0,
                token_count=10,
                signal_to_noise_ratio=0.8,
            ),
        ]


class MockMetadataResolver:
    """Mock metadata resolver for testing."""
    
    def resolve(
        self,
        citekey: str | None = None,
        doc_id: str = "",
        source_hint: str | None = None,
        zotero_config: dict[str, Any] | None = None,
    ) -> CitationMeta | None:
        """Mock metadata resolution."""
        return CitationMeta(
            citekey="test-2025",
            title="Test Document",
            authors=["Test Author"],
            year=2025,
            doi="10.1000/test",
            url=None,
            tags=[],
            collections=[],
            language="en",
        )


class MockEmbedder:
    """Mock embedder for testing."""
    
    def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]]:
        """Mock embedding generation."""
        return [[0.1] * 384 for _ in texts]


class MockVectorIndex:
    """Mock vector index for testing."""
    
    def upsert(self, items: list[dict[str, Any]], project_id: str, model_id: str) -> None:
        """Mock upsert."""
        pass


def test_ingest_document_success(tmp_path: Path):
    """Test successful document ingestion."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Execute
    result = ingest_document(
        request=request,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
    )
    
    # Assert
    assert isinstance(result, IngestResult)
    assert result.chunks_written == 1
    assert result.documents_processed == 1
    assert result.embed_model == "BAAI/bge-small-en-v1.5"
    assert result.duration_seconds >= 0  # Duration may be 0 if test runs very fast


def test_ingest_document_conversion_failure(tmp_path: Path):
    """Test ingestion handles conversion failures gracefully."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    converter.convert = Mock(side_effect=Exception("Conversion failed"))
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Execute & Assert
    with pytest.raises(Exception, match="Conversion failed"):
        ingest_document(
            request=request,
            converter=converter,
            chunker=chunker,
            resolver=resolver,
            embedder=embedder,
            index=index,
        )


def test_ingest_document_chunking_failure(tmp_path: Path):
    """Test ingestion handles chunking failures gracefully."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    chunker = MockChunker()
    chunker.chunk = Mock(side_effect=ChunkingError("Chunking failed", "Invalid structure"))
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Execute & Assert
    with pytest.raises(ChunkingError):
        ingest_document(
            request=request,
            converter=converter,
            chunker=chunker,
            resolver=resolver,
            embedder=embedder,
            index=index,
        )


def test_ingest_document_embedding_failure(tmp_path: Path):
    """Test ingestion handles embedding failures gracefully."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    embedder.embed = Mock(side_effect=Exception("Embedding failed"))
    index = MockVectorIndex()
    
    # Execute & Assert
    with pytest.raises(Exception, match="Embedding failed"):
        ingest_document(
            request=request,
            converter=converter,
            chunker=chunker,
            resolver=resolver,
            embedder=embedder,
            index=index,
        )


def test_ingest_document_metadata_resolution_warning(tmp_path: Path):
    """Test ingestion continues with warning when metadata resolution fails."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    resolver.resolve = Mock(side_effect=Exception("Metadata resolution failed"))
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Execute
    result = ingest_document(
        request=request,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
    )
    
    # Assert
    assert result.chunks_written == 1
    assert len(result.warnings) > 0
    assert any("metadata" in w.lower() for w in result.warnings)


def test_ingest_document_with_audit_log(tmp_path: Path):
    """Test ingestion creates audit log when audit_dir is provided."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    audit_dir = tmp_path / "audit"
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Execute
    result = ingest_document(
        request=request,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
        audit_dir=audit_dir,
    )
    
    # Assert
    assert audit_dir.exists()
    audit_files = list(audit_dir.glob("*.jsonl"))
    assert len(audit_files) == 1
    
    # Check audit log content
    import json
    with audit_files[0].open() as f:
        audit_entry = json.loads(f.readline())
        assert audit_entry["project_id"] == "test/project"
        assert audit_entry["chunks_written"] == 1
        assert audit_entry["documents_processed"] == 1


def test_ingest_document_with_progress_reporter(tmp_path: Path):
    """Test ingestion calls progress reporter methods."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    index = MockVectorIndex()
    
    # Mock progress reporter
    progress_reporter = Mock()
    doc_progress = Mock()
    progress_reporter.start_document = Mock(return_value=doc_progress)
    
    # Execute
    result = ingest_document(
        request=request,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
        progress_reporter=progress_reporter,
    )
    
    # Assert
    progress_reporter.start_document.assert_called_once()
    doc_progress.update_stage.assert_called()
    doc_progress.finish.assert_called_once()


def test_ingest_document_with_zotero_keys(tmp_path: Path):
    """Test ingestion stores Zotero item and attachment keys."""
    # Setup
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf content")
    
    request = IngestRequest(
        source_path=str(test_file),
        project_id="test/project",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    
    converter = MockConverter()
    chunker = MockChunker()
    resolver = MockMetadataResolver()
    embedder = MockEmbedder()
    
    # Mock index to capture upserted items
    upserted_items = []
    index = Mock()
    def mock_upsert(items, project_id, model_id):
        upserted_items.extend(items)
    index.upsert = mock_upsert
    
    # Execute
    result = ingest_document(
        request=request,
        converter=converter,
        chunker=chunker,
        resolver=resolver,
        embedder=embedder,
        index=index,
        item_key="ZOTERO_ITEM_KEY",
        attachment_key="ZOTERO_ATTACHMENT_KEY",
    )
    
    # Assert
    assert len(upserted_items) == 1
    assert upserted_items[0]["zotero_item_key"] == "ZOTERO_ITEM_KEY"
    assert upserted_items[0]["zotero_attachment_key"] == "ZOTERO_ATTACHMENT_KEY"

