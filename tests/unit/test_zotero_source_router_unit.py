"""Unit tests for ZoteroSourceRouter strategy logic with doubles (T122)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from src.domain.errors import ZoteroRateLimitError
from src.application.services.zotero_source_router import ZoteroSourceRouter


class TestZoteroSourceRouterStrategyLogic:
    """Test source router strategy logic with mocked adapters."""

    def test_local_first_strategy_logic(self):
        """Test local-first strategy logic."""
        local_adapter = Mock()
        web_adapter = Mock()
        local_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="local-first",
        )

        result = router.list_collections()

        assert len(result) > 0
        local_adapter.list_collections.assert_called_once()
        web_adapter.list_collections.assert_not_called()

    def test_local_first_fallback_when_local_unavailable(self):
        """Test local-first falls back when local adapter unavailable."""
        web_adapter = Mock()
        web_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=None,
            web_adapter=web_adapter,
            strategy="local-first",
        )

        result = router.list_collections()

        assert len(result) > 0
        web_adapter.list_collections.assert_called_once()

    def test_web_first_strategy_logic(self):
        """Test web-first strategy logic."""
        local_adapter = Mock()
        web_adapter = Mock()
        web_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="web-first",
        )

        result = router.list_collections()

        assert len(result) > 0
        web_adapter.list_collections.assert_called_once()
        local_adapter.list_collections.assert_not_called()

    def test_web_first_fallback_on_rate_limit(self):
        """Test web-first falls back to local on rate limit."""
        local_adapter = Mock()
        web_adapter = Mock()
        web_adapter.list_collections.side_effect = ZoteroRateLimitError(
            "Rate limit exceeded",
            retry_after=60,
        )
        local_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="web-first",
        )

        result = router.list_collections()

        assert len(result) > 0
        web_adapter.list_collections.assert_called_once()
        local_adapter.list_collections.assert_called_once()  # Fallback

    def test_auto_strategy_prefers_local(self):
        """Test auto strategy prefers local when available."""
        local_adapter = Mock()
        web_adapter = Mock()
        local_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="auto",
        )

        result = router.list_collections()

        assert len(result) > 0
        local_adapter.list_collections.assert_called_once()
        web_adapter.list_collections.assert_not_called()

    def test_auto_strategy_fallback_to_web(self):
        """Test auto strategy falls back to web when local fails."""
        local_adapter = Mock()
        web_adapter = Mock()
        local_adapter.list_collections.side_effect = Exception("Local failed")
        web_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="auto",
        )

        result = router.list_collections()

        assert len(result) > 0
        local_adapter.list_collections.assert_called_once()
        web_adapter.list_collections.assert_called_once()  # Fallback

    def test_local_only_strategy_requires_local(self):
        """Test local-only strategy requires local adapter."""
        local_adapter = Mock()
        web_adapter = Mock()
        local_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="local-only",
        )

        result = router.list_collections()

        assert len(result) > 0
        local_adapter.list_collections.assert_called_once()
        web_adapter.list_collections.assert_not_called()

    def test_local_only_raises_when_unavailable(self):
        """Test local-only raises error when local unavailable."""
        web_adapter = Mock()

        router = ZoteroSourceRouter(
            local_adapter=None,
            web_adapter=web_adapter,
            strategy="local-only",
        )

        with pytest.raises(ValueError, match="Local adapter not available"):
            router.list_collections()

    def test_web_only_strategy_uses_web(self):
        """Test web-only strategy uses web adapter."""
        local_adapter = Mock()
        web_adapter = Mock()
        web_adapter.list_collections.return_value = [{"key": "COL1"}]

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="web-only",
        )

        result = router.list_collections()

        assert len(result) > 0
        web_adapter.list_collections.assert_called_once()
        local_adapter.list_collections.assert_not_called()

    def test_is_local_available_returns_true(self):
        """Test is_local_available returns True when adapter exists."""
        local_adapter = Mock()
        web_adapter = Mock()

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="auto",
        )

        assert router.is_local_available() is True

    def test_is_local_available_returns_false(self):
        """Test is_local_available returns False when adapter is None."""
        web_adapter = Mock()

        router = ZoteroSourceRouter(
            local_adapter=None,
            web_adapter=web_adapter,
            strategy="auto",
        )

        assert router.is_local_available() is False

    def test_download_attachment_returns_source_marker(self, tmp_path: Path):
        """Test that download_attachment returns source marker."""
        local_adapter = Mock()
        web_adapter = Mock()
        local_adapter.can_resolve_locally.return_value = True
        local_adapter.download_attachment.return_value = Path("/local/file.pdf")

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="local-first",
        )

        output_path = tmp_path / "output.pdf"
        file_path, source = router.download_attachment("ITEM1", "ATTACH1", output_path)

        assert source in ("local", "web")
        assert isinstance(file_path, Path)

    def test_download_attachment_per_file_fallback(self, tmp_path: Path):
        """Test that per-file fallback works correctly."""
        local_adapter = Mock()
        web_adapter = Mock()

        # First call: local available
        # Second call: local not available
        local_adapter.can_resolve_locally.side_effect = [True, False]
        local_adapter.download_attachment.return_value = Path("/local/file.pdf")
        web_adapter.download_attachment.return_value = Path("/web/file.pdf")

        router = ZoteroSourceRouter(
            local_adapter=local_adapter,
            web_adapter=web_adapter,
            strategy="local-first",
        )

        output_path = tmp_path / "output.pdf"

        # First attachment: local
        file_path1, source1 = router.download_attachment("ITEM1", "ATTACH1", output_path)
        assert source1 == "local"

        # Second attachment: web (fallback)
        file_path2, source2 = router.download_attachment("ITEM1", "ATTACH2", output_path)
        assert source2 == "web"

        # Verify both adapters were called appropriately
        assert local_adapter.download_attachment.call_count >= 1
        assert web_adapter.download_attachment.call_count >= 1
