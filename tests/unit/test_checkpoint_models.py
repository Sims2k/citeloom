"""Unit tests for checkpoint domain models."""

from datetime import datetime

import pytest

from src.domain.models.checkpoint import (
    CheckpointStatistics,
    DocumentCheckpoint,
    IngestionCheckpoint,
    VALID_STATUSES,
)


def test_checkpoint_statistics_initialization():
    """Test CheckpointStatistics initialization."""
    stats = CheckpointStatistics(
        total_documents=10,
        completed=5,
        failed=2,
        pending=3,
    )
    
    assert stats.total_documents == 10
    assert stats.completed == 5
    assert stats.failed == 2
    assert stats.pending == 3


def test_checkpoint_statistics_completion_percentage():
    """Test CheckpointStatistics completion_percentage calculation."""
    stats = CheckpointStatistics(
        total_documents=10,
        completed=5,
        failed=2,
        pending=3,
    )
    
    assert stats.completion_percentage() == 50.0  # 5/10 * 100


def test_checkpoint_statistics_completion_percentage_zero_total():
    """Test CheckpointStatistics completion_percentage with zero total documents."""
    stats = CheckpointStatistics(
        total_documents=0,
        completed=0,
        failed=0,
        pending=0,
    )
    
    # Should handle zero total gracefully
    assert stats.completion_percentage() == 0.0


def test_document_checkpoint_initialization():
    """Test DocumentCheckpoint initialization."""
    doc = DocumentCheckpoint(
        path="/path/to/doc.pdf",
        status="pending",
        zotero_item_key="ABC123",
        zotero_attachment_key="XYZ789",
    )
    
    assert doc.path == "/path/to/doc.pdf"
    assert doc.status == "pending"
    assert doc.stage is None
    assert doc.chunks_count == 0
    assert doc.doc_id is None
    assert doc.zotero_item_key == "ABC123"
    assert doc.zotero_attachment_key == "XYZ789"
    assert doc.error is None


def test_document_checkpoint_status_validation():
    """Test DocumentCheckpoint status validation."""
    # Valid statuses should work
    for status in VALID_STATUSES:
        doc = DocumentCheckpoint(
            path="/path/to/doc.pdf",
            status=status,
        )
        assert doc.status == status
    
    # Invalid status should raise ValueError
    with pytest.raises(ValueError, match="Invalid status"):
        DocumentCheckpoint(
            path="/path/to/doc.pdf",
            status="invalid_status",
        )


def test_document_checkpoint_mark_stage():
    """Test DocumentCheckpoint mark_stage() method."""
    doc = DocumentCheckpoint(
        path="/path/to/doc.pdf",
        status="pending",
    )
    
    doc.mark_stage("converting")
    assert doc.status == "processing"
    assert doc.stage == "converting"
    
    doc.mark_stage("chunking")
    assert doc.stage == "chunking"
    
    doc.mark_stage("embedding")
    assert doc.stage == "embedding"
    
    doc.mark_stage("storing")
    assert doc.stage == "storing"


def test_document_checkpoint_mark_completed():
    """Test DocumentCheckpoint mark_completed() method."""
    doc = DocumentCheckpoint(
        path="/path/to/doc.pdf",
        status="processing",
        stage="storing",
    )
    
    doc.mark_completed(chunks_count=42, doc_id="doc_123")
    
    assert doc.status == "completed"
    assert doc.chunks_count == 42
    assert doc.doc_id == "doc_123"
    assert doc.stage is None  # Stage cleared on completion


def test_document_checkpoint_mark_failed():
    """Test DocumentCheckpoint mark_failed() method."""
    doc = DocumentCheckpoint(
        path="/path/to/doc.pdf",
        status="processing",
        stage="converting",
    )
    
    doc.mark_failed(error="Conversion timeout")
    
    assert doc.status == "failed"
    assert doc.error == "Conversion timeout"
    assert doc.stage is None  # Stage cleared on failure


def test_document_checkpoint_serialization():
    """Test DocumentCheckpoint to_dict() and from_dict() methods."""
    doc = DocumentCheckpoint(
        path="/path/to/doc.pdf",
        status="completed",
        stage=None,
        chunks_count=10,
        doc_id="doc_123",
        zotero_item_key="ABC123",
        zotero_attachment_key="XYZ789",
        error=None,
        updated_at=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    # Serialize
    doc_dict = doc.to_dict()
    
    assert doc_dict["path"] == "/path/to/doc.pdf"
    assert doc_dict["status"] == "completed"
    assert doc_dict["chunks_count"] == 10
    assert doc_dict["doc_id"] == "doc_123"
    
    # Deserialize
    doc_restored = DocumentCheckpoint.from_dict(doc_dict)
    
    assert doc_restored.path == doc.path
    assert doc_restored.status == doc.status
    assert doc_restored.chunks_count == doc.chunks_count
    assert doc_restored.doc_id == doc.doc_id


def test_ingestion_checkpoint_initialization():
    """Test IngestionCheckpoint initialization."""
    checkpoint = IngestionCheckpoint(
        correlation_id="corr_123",
        project_id="project/test",
        collection_key="ABC12345",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    assert checkpoint.correlation_id == "corr_123"
    assert checkpoint.project_id == "project/test"
    assert checkpoint.collection_key == "ABC12345"
    assert len(checkpoint.documents) == 0
    assert checkpoint.statistics.total_documents == 0


def test_ingestion_checkpoint_add_document():
    """Test IngestionCheckpoint add_document_checkpoint() method."""
    checkpoint = IngestionCheckpoint(
        correlation_id="corr_123",
        project_id="project/test",
        collection_key="ABC12345",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    doc1 = DocumentCheckpoint(path="/path/to/doc1.pdf", status="completed")
    doc1.mark_completed(chunks_count=10, doc_id="doc_1")
    
    checkpoint.add_document_checkpoint(doc1)
    
    assert len(checkpoint.documents) == 1
    assert checkpoint.statistics.total_documents == 1
    assert checkpoint.statistics.completed == 1


def test_ingestion_checkpoint_update_statistics():
    """Test IngestionCheckpoint update_statistics() method."""
    checkpoint = IngestionCheckpoint(
        correlation_id="corr_123",
        project_id="project/test",
        collection_key="ABC12345",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    # Add completed document
    doc1 = DocumentCheckpoint(path="/path/to/doc1.pdf", status="completed")
    doc1.mark_completed(chunks_count=10, doc_id="doc_1")
    checkpoint.add_document_checkpoint(doc1)
    
    # Add failed document
    doc2 = DocumentCheckpoint(path="/path/to/doc2.pdf", status="failed")
    doc2.mark_failed(error="Conversion failed")
    checkpoint.add_document_checkpoint(doc2)
    
    # Add pending document
    doc3 = DocumentCheckpoint(path="/path/to/doc3.pdf", status="pending")
    checkpoint.add_document_checkpoint(doc3)
    
    # Update statistics
    checkpoint.update_statistics()
    
    assert checkpoint.statistics.total_documents == 3
    assert checkpoint.statistics.completed == 1
    assert checkpoint.statistics.failed == 1
    assert checkpoint.statistics.pending == 1


def test_ingestion_checkpoint_get_completed_documents():
    """Test IngestionCheckpoint get_completed_documents() method."""
    checkpoint = IngestionCheckpoint(
        correlation_id="corr_123",
        project_id="project/test",
        collection_key="ABC12345",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    doc1 = DocumentCheckpoint(path="/path/to/doc1.pdf", status="completed")
    doc1.mark_completed(chunks_count=10, doc_id="doc_1")
    checkpoint.add_document_checkpoint(doc1)
    
    doc2 = DocumentCheckpoint(path="/path/to/doc2.pdf", status="failed")
    doc2.mark_failed(error="Error")
    checkpoint.add_document_checkpoint(doc2)
    
    doc3 = DocumentCheckpoint(path="/path/to/doc3.pdf", status="completed")
    doc3.mark_completed(chunks_count=5, doc_id="doc_3")
    checkpoint.add_document_checkpoint(doc3)
    
    completed = checkpoint.get_completed_documents()
    
    assert len(completed) == 2
    assert all(doc.status == "completed" for doc in completed)


def test_ingestion_checkpoint_get_incomplete_documents():
    """Test IngestionCheckpoint get_incomplete_documents() method."""
    checkpoint = IngestionCheckpoint(
        correlation_id="corr_123",
        project_id="project/test",
        collection_key="ABC12345",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    doc1 = DocumentCheckpoint(path="/path/to/doc1.pdf", status="completed")
    doc1.mark_completed(chunks_count=10, doc_id="doc_1")
    checkpoint.add_document_checkpoint(doc1)
    
    doc2 = DocumentCheckpoint(path="/path/to/doc2.pdf", status="pending")
    checkpoint.add_document_checkpoint(doc2)
    
    doc3 = DocumentCheckpoint(path="/path/to/doc3.pdf", status="processing")
    doc3.mark_stage("converting")
    checkpoint.add_document_checkpoint(doc3)
    
    incomplete = checkpoint.get_incomplete_documents()
    
    assert len(incomplete) == 2
    assert all(doc.status != "completed" for doc in incomplete)


def test_ingestion_checkpoint_serialization():
    """Test IngestionCheckpoint to_dict() and from_dict() methods."""
    checkpoint = IngestionCheckpoint(
        correlation_id="corr_123",
        project_id="project/test",
        collection_key="ABC12345",
        start_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    doc = DocumentCheckpoint(path="/path/to/doc.pdf", status="completed")
    doc.mark_completed(chunks_count=10, doc_id="doc_1")
    checkpoint.add_document_checkpoint(doc)
    
    # Serialize
    checkpoint_dict = checkpoint.to_dict()
    
    assert checkpoint_dict["correlation_id"] == "corr_123"
    assert checkpoint_dict["project_id"] == "project/test"
    assert checkpoint_dict["collection_key"] == "ABC12345"
    assert len(checkpoint_dict["documents"]) == 1
    
    # Deserialize
    checkpoint_restored = IngestionCheckpoint.from_dict(checkpoint_dict)
    
    assert checkpoint_restored.correlation_id == checkpoint.correlation_id
    assert checkpoint_restored.project_id == checkpoint.project_id
    assert checkpoint_restored.collection_key == checkpoint.collection_key
    assert len(checkpoint_restored.documents) == len(checkpoint.documents)

