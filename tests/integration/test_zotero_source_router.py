"""Integration tests for source router strategies (T119)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.domain.errors import ZoteroRateLimitError
from src.application.services.zotero_source_router import ZoteroSourceRouter


@pytest.fixture
def mock_local_adapter():
    """Create a mock local adapter."""
    adapter = Mock()
    adapter.list_collections.return_value = [{"key": "COL1", "name": "Test Collection"}]
    adapter.get_collection_items.return_value = [{"key": "ITEM1", "title": "Test Item"}]
    adapter.can_resolve_locally.return_value = True
    adapter.download_attachment.return_value = Path("/local/path/file.pdf")
    return adapter


@pytest.fixture
def mock_web_adapter():
    """Create a mock web adapter."""
    adapter = Mock()
    adapter.list_collections.return_value = [{"key": "COL1", "name": "Test Collection"}]
    adapter.get_collection_items.return_value = [{"key": "ITEM1", "title": "Test Item"}]
    adapter.download_attachment.return_value = Path("/web/path/file.pdf")
    return adapter


class TestSourceRouterStrategies:
    """Test source router strategy implementations."""

    def test_local_first_prefers_local(self, mock_local_adapter, mock_web_adapter):
        """Test that local-first strategy prefers local adapter."""
        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="local-first",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_local_adapter.list_collections.assert_called_once()
        mock_web_adapter.list_collections.assert_not_called()

    def test_local_first_fallback_to_web(self, mock_web_adapter):
        """Test that local-first falls back to web when local unavailable."""
        # No local adapter
        router = ZoteroSourceRouter(
            local_adapter=None,
            web_adapter=mock_web_adapter,
            strategy="local-first",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_web_adapter.list_collections.assert_called_once()

    def test_web_first_prefers_web(self, mock_local_adapter, mock_web_adapter):
        """Test that web-first strategy prefers web adapter."""
        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="web-first",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_web_adapter.list_collections.assert_called_once()
        mock_local_adapter.list_collections.assert_not_called()

    def test_web_first_fallback_on_rate_limit(self, mock_local_adapter, mock_web_adapter):
        """Test that web-first falls back to local on rate limit."""
        mock_web_adapter.list_collections.side_effect = ZoteroRateLimitError(
            "Rate limit exceeded",
            retry_after=60,
        )

        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="web-first",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_web_adapter.list_collections.assert_called_once()
        mock_local_adapter.list_collections.assert_called_once()  # Fallback called

    def test_auto_strategy_prefers_local_when_available(self, mock_local_adapter, mock_web_adapter):
        """Test that auto strategy prefers local when available."""
        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="auto",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_local_adapter.list_collections.assert_called_once()
        mock_web_adapter.list_collections.assert_not_called()

    def test_auto_strategy_fallback_to_web(self, mock_web_adapter):
        """Test that auto strategy falls back to web when local unavailable."""
        router = ZoteroSourceRouter(
            local_adapter=None,
            web_adapter=mock_web_adapter,
            strategy="auto",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_web_adapter.list_collections.assert_called_once()

    def test_local_only_requires_local(self, mock_local_adapter, mock_web_adapter):
        """Test that local-only strategy requires local adapter."""
        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="local-only",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_local_adapter.list_collections.assert_called_once()
        mock_web_adapter.list_collections.assert_not_called()

    def test_local_only_raises_when_unavailable(self, mock_web_adapter):
        """Test that local-only raises error when local unavailable."""
        router = ZoteroSourceRouter(
            local_adapter=None,
            web_adapter=mock_web_adapter,
            strategy="local-only",
        )

        with pytest.raises(ValueError, match="Local adapter not available"):
            router.list_collections()

    def test_web_only_uses_web(self, mock_local_adapter, mock_web_adapter):
        """Test that web-only strategy uses web adapter."""
        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="web-only",
        )

        collections = router.list_collections()

        assert len(collections) > 0
        mock_web_adapter.list_collections.assert_called_once()
        mock_local_adapter.list_collections.assert_not_called()

    def test_download_attachment_local_first(
        self, mock_local_adapter, mock_web_adapter, tmp_path: Path
    ):
        """Test download_attachment with local-first strategy."""
        output_path = tmp_path / "output.pdf"

        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="local-first",
        )

        file_path, source = router.download_attachment("ITEM1", "ATTACH1", output_path)

        assert source == "local"
        assert file_path == Path("/local/path/file.pdf")
        mock_local_adapter.download_attachment.assert_called_once()
        mock_web_adapter.download_attachment.assert_not_called()

    def test_download_attachment_local_first_fallback(self, mock_web_adapter, tmp_path: Path):
        """Test download_attachment with local-first fallback when local fails."""
        output_path = tmp_path / "output.pdf"

        mock_local_adapter = Mock()
        mock_local_adapter.can_resolve_locally.return_value = False

        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="local-first",
        )

        file_path, source = router.download_attachment("ITEM1", "ATTACH1", output_path)

        assert source == "web"
        assert file_path == Path("/web/path/file.pdf")
        mock_web_adapter.download_attachment.assert_called_once()

    def test_download_attachment_per_file_fallback(
        self, mock_local_adapter, mock_web_adapter, tmp_path: Path
    ):
        """Test that per-file fallback allows mixed sources."""
        output_path = tmp_path / "output.pdf"

        # First attachment available locally
        mock_local_adapter.can_resolve_locally.return_value = True

        router = ZoteroSourceRouter(
            local_adapter=mock_local_adapter,
            web_adapter=mock_web_adapter,
            strategy="local-first",
        )

        file_path1, source1 = router.download_attachment("ITEM1", "ATTACH1", output_path)
        assert source1 == "local"

        # Second attachment not available locally
        mock_local_adapter.can_resolve_locally.return_value = False
        file_path2, source2 = router.download_attachment("ITEM1", "ATTACH2", output_path)
        assert source2 == "web"

        # Both sources used (per-file routing)
        assert source1 != source2
