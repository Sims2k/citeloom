"""Unit tests for download manifest domain models."""

from datetime import datetime
from pathlib import Path

import pytest

from src.domain.models.download_manifest import (
    DownloadManifest,
    DownloadManifestAttachment,
    DownloadManifestItem,
)


def test_download_manifest_attachment_initialization():
    """Test DownloadManifestAttachment initialization."""
    # Use absolute path (Path.resolve() ensures it's absolute)
    import os
    abs_path = Path("/tmp/document.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/document.pdf")
    
    attachment = DownloadManifestAttachment(
        attachment_key="ATT123",
        filename="document.pdf",
        local_path=abs_path,
        download_status="success",
        file_size=1024,
    )
    
    assert attachment.attachment_key == "ATT123"
    assert attachment.filename == "document.pdf"
    assert attachment.local_path.is_absolute()  # Must be absolute for success status
    assert attachment.download_status == "success"
    assert attachment.file_size == 1024
    assert attachment.error is None


def test_download_manifest_attachment_failed_status():
    """Test DownloadManifestAttachment with failed download status."""
    attachment = DownloadManifestAttachment(
        attachment_key="ATT123",
        filename="document.pdf",
        local_path=Path("/tmp/document.pdf"),
        download_status="failed",
        error="Network timeout",
    )
    
    assert attachment.download_status == "failed"
    assert attachment.error == "Network timeout"


def test_download_manifest_item_initialization():
    """Test DownloadManifestItem initialization."""
    item = DownloadManifestItem(
        item_key="ITEM123",
        title="Test Document",
        metadata={"author": "John Doe"},
    )
    
    assert item.item_key == "ITEM123"
    assert item.title == "Test Document"
    assert item.metadata == {"author": "John Doe"}
    assert len(item.attachments) == 0


def test_download_manifest_item_add_attachment():
    """Test DownloadManifestItem add_attachment() method."""
    item = DownloadManifestItem(
        item_key="ITEM123",
        title="Test Document",
    )
    
    # Use absolute path
    import os
    abs_path = Path("/tmp/document.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/document.pdf")
    
    attachment = DownloadManifestAttachment(
        attachment_key="ATT123",
        filename="document.pdf",
        local_path=abs_path,
        download_status="success",
    )
    
    item.add_attachment(attachment)
    
    assert len(item.attachments) == 1
    assert item.attachments[0].attachment_key == "ATT123"


def test_download_manifest_item_get_pdf_attachments():
    """Test DownloadManifestItem get_pdf_attachments() method."""
    item = DownloadManifestItem(
        item_key="ITEM123",
        title="Test Document",
    )
    
    # Use absolute paths
    import os
    pdf_path = Path("/tmp/document.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/document.pdf")
    txt_path = Path("/tmp/notes.txt").resolve() if os.name != 'nt' else Path("C:/tmp/notes.txt")
    
    # Add PDF attachment
    pdf_att = DownloadManifestAttachment(
        attachment_key="ATT123",
        filename="document.pdf",
        local_path=pdf_path,
        download_status="success",
    )
    item.add_attachment(pdf_att)
    
    # Add non-PDF attachment (should be filtered out)
    txt_att = DownloadManifestAttachment(
        attachment_key="ATT456",
        filename="notes.txt",
        local_path=txt_path,
        download_status="success",
    )
    item.add_attachment(txt_att)
    
    pdf_attachments = item.get_pdf_attachments()
    
    assert len(pdf_attachments) == 1
    assert pdf_attachments[0].filename.endswith(".pdf")


def test_download_manifest_initialization():
    """Test DownloadManifest initialization."""
    manifest = DownloadManifest(
        collection_key="COLL123",
        collection_name="Test Collection",
        download_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    assert manifest.collection_key == "COLL123"
    assert manifest.collection_name == "Test Collection"
    assert len(manifest.items) == 0


def test_download_manifest_add_item():
    """Test DownloadManifest add_item() method."""
    manifest = DownloadManifest(
        collection_key="COLL123",
        collection_name="Test Collection",
        download_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    item = DownloadManifestItem(
        item_key="ITEM123",
        title="Test Document",
    )
    
    manifest.add_item(item)
    
    assert len(manifest.items) == 1
    assert manifest.items[0].item_key == "ITEM123"


def test_download_manifest_get_all_file_paths():
    """Test DownloadManifest get_all_file_paths() method."""
    manifest = DownloadManifest(
        collection_key="COLL123",
        collection_name="Test Collection",
        download_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    # Use absolute paths
    import os
    doc1_path = Path("/tmp/doc1.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/doc1.pdf")
    doc2_path = Path("/tmp/doc2.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/doc2.pdf")
    
    item1 = DownloadManifestItem(item_key="ITEM1", title="Doc 1")
    att1 = DownloadManifestAttachment(
        attachment_key="ATT1",
        filename="doc1.pdf",
        local_path=doc1_path,
        download_status="success",
    )
    item1.add_attachment(att1)
    manifest.add_item(item1)
    
    item2 = DownloadManifestItem(item_key="ITEM2", title="Doc 2")
    att2 = DownloadManifestAttachment(
        attachment_key="ATT2",
        filename="doc2.pdf",
        local_path=doc2_path,
        download_status="success",
    )
    item2.add_attachment(att2)
    manifest.add_item(item2)
    
    file_paths = manifest.get_all_file_paths()
    
    assert len(file_paths) == 2
    assert doc1_path in file_paths
    assert doc2_path in file_paths


def test_download_manifest_get_successful_downloads():
    """Test DownloadManifest get_successful_downloads() method."""
    manifest = DownloadManifest(
        collection_key="COLL123",
        collection_name="Test Collection",
        download_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    # Use absolute paths
    import os
    doc1_path = Path("/tmp/doc1.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/doc1.pdf")
    doc2_path = Path("/tmp/doc2.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/doc2.pdf")
    
    # Item with successful downloads
    item1 = DownloadManifestItem(item_key="ITEM1", title="Doc 1")
    att1 = DownloadManifestAttachment(
        attachment_key="ATT1",
        filename="doc1.pdf",
        local_path=doc1_path,
        download_status="success",
    )
    item1.add_attachment(att1)
    manifest.add_item(item1)
    
    # Item with failed downloads only (should be filtered out)
    item2 = DownloadManifestItem(item_key="ITEM2", title="Doc 2")
    att2 = DownloadManifestAttachment(
        attachment_key="ATT2",
        filename="doc2.pdf",
        local_path=doc2_path,
        download_status="failed",
        error="Network error",
    )
    item2.add_attachment(att2)
    manifest.add_item(item2)
    
    successful = manifest.get_successful_downloads()
    
    assert len(successful) == 1
    assert successful[0].item_key == "ITEM1"


def test_download_manifest_serialization():
    """Test DownloadManifest to_dict() and from_dict() methods."""
    manifest = DownloadManifest(
        collection_key="COLL123",
        collection_name="Test Collection",
        download_time=datetime(2024, 1, 1, 12, 0, 0),
    )
    
    # Use absolute path
    import os
    abs_path = Path("/tmp/document.pdf").resolve() if os.name != 'nt' else Path("C:/tmp/document.pdf")
    
    item = DownloadManifestItem(item_key="ITEM123", title="Test Document")
    attachment = DownloadManifestAttachment(
        attachment_key="ATT123",
        filename="document.pdf",
        local_path=abs_path,
        download_status="success",
        file_size=1024,
    )
    item.add_attachment(attachment)
    manifest.add_item(item)
    
    # Serialize
    manifest_dict = manifest.to_dict()
    
    assert manifest_dict["collection_key"] == "COLL123"
    assert manifest_dict["collection_name"] == "Test Collection"
    assert len(manifest_dict["items"]) == 1
    
    # Deserialize
    manifest_restored = DownloadManifest.from_dict(manifest_dict)
    
    assert manifest_restored.collection_key == manifest.collection_key
    assert manifest_restored.collection_name == manifest.collection_name
    assert len(manifest_restored.items) == len(manifest.items)
    assert manifest_restored.items[0].item_key == manifest.items[0].item_key

