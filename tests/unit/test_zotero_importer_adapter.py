"""Unit tests for ZoteroImporterAdapter."""

from __future__ import annotations

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from typing import Any

from src.infrastructure.adapters.zotero_importer import ZoteroImporterAdapter
from src.domain.errors import (
    ZoteroAPIError,
    ZoteroConnectionError,
    ZoteroRateLimitError,
)


def test_zotero_importer_init_with_config():
    """Test adapter initialization with config dict."""
    config = {
        "library_id": "12345",
        "library_type": "user",
        "api_key": "test_api_key",
        "local": False,  # Explicitly disable local mode
    }
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.return_value = MagicMock()
        with patch("src.infrastructure.adapters.zotero_importer.get_env", return_value=None):
            with patch("src.infrastructure.adapters.zotero_importer.get_env_bool", return_value=False):
                adapter = ZoteroImporterAdapter(zotero_config=config)
                
                assert adapter.zot is not None
                assert not adapter.local
                # Should call with API key (not local)
                assert mock_zotero.call_args[0][0] == "12345"
                assert mock_zotero.call_args[0][1] == "user"
                assert mock_zotero.call_args[0][2] == "test_api_key"


def test_zotero_importer_init_local_mode():
    """Test adapter initialization with local mode."""
    config = {
        "library_id": "1",
        "library_type": "user",
        "local": True,
    }
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.return_value = MagicMock()
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        assert adapter.zot is not None
        assert adapter.local
        mock_zotero.assert_called_once_with("1", "user", api_key=None, local=True)


def test_zotero_importer_init_missing_library_id():
    """Test adapter initialization fails without library_id."""
    with patch("src.infrastructure.adapters.zotero_importer.get_env", return_value=None):
        with patch("src.infrastructure.adapters.zotero_importer.get_env_bool", return_value=False):
            with pytest.raises(ZoteroConnectionError):
                ZoteroImporterAdapter(zotero_config={})


def test_zotero_importer_init_missing_api_key_for_remote():
    """Test adapter initialization fails without API key for remote access."""
    config = {
        "library_id": "12345",
        "library_type": "user",
        "local": False,
    }
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.side_effect = [Exception("Local failed")]  # First attempt fails
        with patch("src.infrastructure.adapters.zotero_importer.get_env", return_value=None):
            with patch("src.infrastructure.adapters.zotero_importer.get_env_bool", return_value=False):
                with pytest.raises(ZoteroConnectionError):
                    ZoteroImporterAdapter(zotero_config=config)


def test_rate_limit_local_mode():
    """Test rate limiting is skipped in local mode."""
    config = {
        "library_id": "1",
        "library_type": "user",
        "local": True,
    }
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.return_value = MagicMock()
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        # Rate limiting should return immediately in local mode
        start_time = time.time()
        adapter._rate_limit()
        elapsed = time.time() - start_time
        
        assert elapsed < 0.1  # Should be very fast (no sleep)


def test_rate_limit_remote_mode():
    """Test rate limiting applies in remote mode."""
    config = {
        "library_id": "12345",
        "library_type": "user",
        "api_key": "test_api_key",
        "local": False,
    }
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.return_value = MagicMock()
        with patch("src.infrastructure.adapters.zotero_importer.get_env_bool", return_value=False):
            adapter = ZoteroImporterAdapter(zotero_config=config)
            
            # Set last_request_time to current time to trigger rate limit
            adapter._last_request_time = time.time()
            
            # Mock time.sleep to verify it's called
            with patch("time.sleep") as mock_sleep:
                adapter._rate_limit()
                mock_sleep.assert_called_once()
                # Verify sleep duration is approximately MIN_REQUEST_INTERVAL
                assert mock_sleep.call_args[0][0] <= adapter.MIN_REQUEST_INTERVAL + 0.01


def test_retry_with_backoff_success():
    """Test retry logic succeeds on first attempt."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.return_value = MagicMock()
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        func = Mock(return_value="success")
        result = adapter._retry_with_backoff(func)
        
        assert result == "success"
        func.assert_called_once()


def test_retry_with_backoff_failure_then_success():
    """Test retry logic retries on failure and succeeds."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.return_value = MagicMock()
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        func = Mock(side_effect=[Exception("Error 1"), "success"])
        
        with patch("time.sleep"):  # Mock sleep to speed up test
            result = adapter._retry_with_backoff(func, max_retries=3)
        
        assert result == "success"
        assert func.call_count == 2


def test_retry_with_backoff_max_retries():
    """Test retry logic raises error after max retries."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_zotero.return_value = MagicMock()
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        func = Mock(side_effect=Exception("Always fails"))
        
        with patch("time.sleep"):  # Mock sleep to speed up test
            with pytest.raises(ZoteroAPIError):
                adapter._retry_with_backoff(func, max_retries=3)
        
        assert func.call_count == 3


def test_list_collections_success():
    """Test successful collection listing."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_client.collections.return_value = [
            {"data": {"key": "ABC123", "name": "Collection 1", "parentCollection": None}},
            {"data": {"key": "DEF456", "name": "Collection 2", "parentCollection": None}},
        ]
        mock_zotero.return_value = mock_client
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        with patch.object(adapter, "_rate_limit"), patch.object(adapter, "_retry_with_backoff") as mock_retry:
            mock_retry.side_effect = lambda f: f()
            collections = adapter.list_collections()
        
        assert len(collections) == 2
        assert collections[0]["key"] == "ABC123"
        assert collections[0]["name"] == "Collection 1"


def test_list_collections_rate_limit_error():
    """Test collection listing handles rate limit errors."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_client.collections.side_effect = Exception("Rate limit exceeded")
        mock_zotero.return_value = mock_client
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        with patch.object(adapter, "_rate_limit"), patch.object(adapter, "_retry_with_backoff") as mock_retry:
            def raise_rate_limit(f):
                try:
                    return f()
                except Exception as e:
                    if "rate" in str(e).lower() or "429" in str(e):
                        raise ZoteroRateLimitError("Rate limit exceeded", retry_after=60) from e
                    raise
            
            mock_retry.side_effect = raise_rate_limit
            
            with pytest.raises(ZoteroRateLimitError):
                adapter.list_collections()


def test_get_collection_items_success():
    """Test successful item retrieval from collection."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_client.collection_items.return_value = [
            {"key": "ITEM1", "data": {"title": "Item 1"}},
            {"key": "ITEM2", "data": {"title": "Item 2"}},
        ]
        mock_zotero.return_value = mock_client
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        with patch.object(adapter, "_rate_limit"), patch.object(adapter, "_retry_with_backoff") as mock_retry:
            mock_retry.side_effect = lambda f: f()
            items = list(adapter.get_collection_items("COLLECTION_KEY"))
        
        assert len(items) == 2


def test_get_item_attachments_pdf_only():
    """Test attachment retrieval filters PDFs."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_client.children.return_value = [
            {
                "key": "ATT1",
                "data": {
                    "linkMode": "imported_file",
                    "contentType": "application/pdf",
                    "filename": "document.pdf",
                },
            },
            {
                "key": "ATT2",
                "data": {
                    "linkMode": "imported_file",
                    "contentType": "text/plain",
                    "filename": "document.txt",
                },
            },
        ]
        mock_zotero.return_value = mock_client
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        with patch.object(adapter, "_rate_limit"), patch.object(adapter, "_retry_with_backoff") as mock_retry:
            mock_retry.side_effect = lambda f: f()
            attachments = adapter.get_item_attachments("ITEM_KEY")
        
        assert len(attachments) == 1
        assert attachments[0]["key"] == "ATT1"


def test_download_attachment_remote(tmp_path: Path):
    """Test attachment download via remote API."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key", "local": False}
    output_path = tmp_path / "downloaded.pdf"
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_client.file.return_value = b"fake pdf content"
        mock_zotero.return_value = mock_client
        
        with patch("src.infrastructure.adapters.zotero_importer.get_env_bool", return_value=False):
            adapter = ZoteroImporterAdapter(zotero_config=config)
            
            with patch.object(adapter, "_rate_limit"):
                result_path = adapter.download_attachment("ITEM_KEY", "ATT_KEY", output_path)
            
            assert result_path == output_path
            assert output_path.exists()
            assert output_path.read_bytes() == b"fake pdf content"


def test_download_attachment_local(tmp_path: Path):
    """Test attachment download via local storage."""
    config = {"library_id": "1", "library_type": "user", "local": True}
    output_path = tmp_path / "downloaded.pdf"
    
    # Create mock local storage structure
    home = tmp_path / "home"
    zotero_storage = home / "Zotero" / "storage"
    item_dir = zotero_storage / "ITEM_KEY"
    item_dir.mkdir(parents=True)
    local_pdf = item_dir / "document.pdf"
    local_pdf.write_bytes(b"local pdf content")
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_client.item.return_value = {"data": {"filename": "document.pdf"}}
        mock_zotero.return_value = mock_client
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        with patch("pathlib.Path.home", return_value=home):
            with patch.object(adapter, "_rate_limit"):
                result_path = adapter.download_attachment("ITEM_KEY", "ATT_KEY", output_path)
            
            assert result_path == output_path
            assert output_path.exists()
            assert output_path.read_bytes() == b"local pdf content"


def test_find_collection_by_name():
    """Test finding collection by name."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_zotero.return_value = mock_client
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        adapter.list_collections = Mock(return_value=[
            {"key": "ABC123", "name": "Machine Learning Papers"},
            {"key": "DEF456", "name": "Computer Vision"},
        ])
        
        result = adapter.find_collection_by_name("Machine Learning")
        
        assert result is not None
        assert result["key"] == "ABC123"
        assert result["name"] == "Machine Learning Papers"


def test_find_collection_by_name_not_found():
    """Test finding non-existent collection returns None."""
    config = {"library_id": "12345", "library_type": "user", "api_key": "test_api_key"}
    
    with patch("src.infrastructure.adapters.zotero_importer.zotero.Zotero") as mock_zotero:
        mock_client = MagicMock()
        mock_zotero.return_value = mock_client
        
        adapter = ZoteroImporterAdapter(zotero_config=config)
        
        adapter.list_collections = Mock(return_value=[
            {"key": "ABC123", "name": "Machine Learning Papers"},
        ])
        
        result = adapter.find_collection_by_name("Nonexistent Collection")
        
        assert result is None

