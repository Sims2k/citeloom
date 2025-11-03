"""Application service for routing Zotero operations to local database or Web API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from typing import Any, Iterator

from ..ports.zotero_importer import ZoteroImporterPort
from ...domain.errors import ZoteroRateLimitError

logger = logging.getLogger(__name__)

Strategy = Literal["local-first", "web-first", "auto", "local-only", "web-only"]


class ZoteroSourceRouter:
    """
    Routes Zotero operations to local database or Web API based on strategy.
    
    Not a port interface - application service that orchestrates adapters.
    Supports multiple strategy modes with intelligent fallback logic.
    """

    def __init__(
        self,
        local_adapter: ZoteroImporterPort | None,
        web_adapter: ZoteroImporterPort,
        strategy: Strategy = "auto",
    ) -> None:
        """
        Initialize router with adapters and strategy.
        
        Args:
            local_adapter: Local SQLite adapter (None if unavailable)
            web_adapter: Web API adapter (required)
            strategy: Routing strategy mode
        """
        self.local_adapter = local_adapter
        self.web_adapter = web_adapter
        self.strategy = strategy
        
        if web_adapter is None:
            raise ValueError("web_adapter is required")
        
        # Log initialization
        logger.info(
            f"ZoteroSourceRouter initialized with strategy: {strategy}",
            extra={
                "strategy": strategy,
                "local_available": local_adapter is not None,
            },
        )
    
    def is_local_available(self) -> bool:
        """
        Check if local database adapter is available.
        
        Returns:
            True if local adapter is available and can be used
        """
        if self.local_adapter is None:
            return False
        
        # Check if adapter has connection by trying to access it
        # For LocalZoteroDbAdapter, connection is opened in __init__
        # If it failed, adapter would be None or raise on access
        try:
            # Try to check if local adapter can be used
            # For now, just check if adapter exists
            return self.local_adapter is not None
        except Exception:
            return False
    
    def list_collections(self) -> list[dict[str, Any]]:
        """
        Route collection listing based on strategy.
        
        Strategy behaviors:
        - local-first: Try local, fallback to web if unavailable
        - web-first: Use web, fallback to local on rate limit
        - auto: Prefer local if available, else web
        - local-only: Only local, raise if unavailable
        - web-only: Only web
        
        Returns:
            List of collections
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError(
                    "Local adapter not available but strategy is 'local-only'. "
                    "Use 'local-first' or 'auto' for fallback, or configure local adapter."
                )
            return self.local_adapter.list_collections()
        
        if self.strategy == "web-only":
            return self.web_adapter.list_collections()
        
        if self.strategy == "local-first":
            if self.is_local_available():
                try:
                    return self.local_adapter.list_collections()
                except Exception as e:
                    logger.warning(
                        f"Local adapter failed, falling back to web: {e}",
                        extra={"error": str(e), "strategy": self.strategy},
                    )
            return self.web_adapter.list_collections()
        
        if self.strategy == "web-first":
            try:
                return self.web_adapter.list_collections()
            except ZoteroRateLimitError as e:
                logger.warning(
                    f"Web adapter rate limited, falling back to local: {e}",
                    extra={"error": str(e), "strategy": self.strategy},
                )
                if self.is_local_available():
                    return self.local_adapter.list_collections()
                raise
            except Exception as e:
                logger.warning(
                    f"Web adapter failed, falling back to local: {e}",
                    extra={"error": str(e), "strategy": self.strategy},
                )
                if self.is_local_available():
                    return self.local_adapter.list_collections()
                raise
        
        # auto strategy
        if self.is_local_available():
            try:
                collections = self.local_adapter.list_collections()
                logger.info(
                    "Using local adapter for collection listing (auto strategy)",
                    extra={"strategy": self.strategy, "count": len(collections)},
                )
                return collections
            except Exception as e:
                logger.warning(
                    f"Local adapter failed, falling back to web (auto strategy): {e}",
                    extra={"error": str(e), "strategy": self.strategy},
                )
        
        logger.info(
            "Using web adapter for collection listing (auto strategy)",
            extra={"strategy": self.strategy},
        )
        return self.web_adapter.list_collections()
    
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Route item fetching based on strategy.
        
        Args:
            collection_key: Zotero collection key
            include_subcollections: If True, recursively include items from subcollections
        
        Yields:
            Zotero items
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError(
                    "Local adapter not available but strategy is 'local-only'. "
                    "Use 'local-first' or 'auto' for fallback, or configure local adapter."
                )
            yield from self.local_adapter.get_collection_items(collection_key, include_subcollections)
            return
        
        if self.strategy == "web-only":
            yield from self.web_adapter.get_collection_items(collection_key, include_subcollections)
            return
        
        if self.strategy == "local-first":
            if self.is_local_available():
                try:
                    yield from self.local_adapter.get_collection_items(
                        collection_key, include_subcollections
                    )
                    return
                except Exception as e:
                    logger.warning(
                        f"Local adapter failed, falling back to web: {e}",
                        extra={"error": str(e), "strategy": self.strategy, "collection_key": collection_key},
                    )
            yield from self.web_adapter.get_collection_items(collection_key, include_subcollections)
            return
        
        if self.strategy == "web-first":
            try:
                yield from self.web_adapter.get_collection_items(collection_key, include_subcollections)
                return
            except ZoteroRateLimitError as e:
                logger.warning(
                    f"Web adapter rate limited, falling back to local: {e}",
                    extra={"error": str(e), "strategy": self.strategy, "collection_key": collection_key},
                )
                if self.is_local_available():
                    yield from self.local_adapter.get_collection_items(
                        collection_key, include_subcollections
                    )
                    return
                raise
            except Exception as e:
                logger.warning(
                    f"Web adapter failed, falling back to local: {e}",
                    extra={"error": str(e), "strategy": self.strategy, "collection_key": collection_key},
                )
                if self.is_local_available():
                    yield from self.local_adapter.get_collection_items(
                        collection_key, include_subcollections
                    )
                    return
                raise
        
        # auto strategy
        if self.is_local_available():
            try:
                items = list(self.local_adapter.get_collection_items(collection_key, include_subcollections))
                logger.info(
                    "Using local adapter for collection items (auto strategy)",
                    extra={"strategy": self.strategy, "collection_key": collection_key, "count": len(items)},
                )
                yield from items
                return
            except Exception as e:
                logger.warning(
                    f"Local adapter failed, falling back to web (auto strategy): {e}",
                    extra={"error": str(e), "strategy": self.strategy, "collection_key": collection_key},
                )
        
        logger.info(
            "Using web adapter for collection items (auto strategy)",
            extra={"strategy": self.strategy, "collection_key": collection_key},
        )
        yield from self.web_adapter.get_collection_items(collection_key, include_subcollections)
    
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> tuple[Path, str]:
        """
        Route download with fallback logic.
        
        Per-file fallback: Each file is checked individually, allowing mixed sources
        within the same collection (some files from local, some from web).
        
        Args:
            item_key: Zotero item key
            attachment_key: Zotero attachment key
            output_path: Local path where file should be saved
        
        Returns:
            Tuple of (file_path, source_marker) where source_marker is "local" or "web"
        
        Raises:
            ZoteroAPIError: If download fails after all fallbacks
            ZoteroPathResolutionError: If local file not found and no fallback
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError(
                    "Local adapter not available but strategy is 'local-only'. "
                    "Use 'local-first' or 'auto' for fallback, or configure local adapter."
                )
            try:
                file_path = self.local_adapter.download_attachment(item_key, attachment_key, output_path)
                return (file_path, "local")
            except Exception as e:
                raise ValueError(
                    f"Local-only strategy failed for attachment {attachment_key}: {e}. "
                    "No fallback available."
                ) from e
        
        if self.strategy == "web-only":
            file_path = self.web_adapter.download_attachment(item_key, attachment_key, output_path)
            return (file_path, "web")
        
        if self.strategy == "local-first":
            # Per-file fallback: Check each file individually
            if self.is_local_available():
                # Check if can_resolve_locally is available (LocalZoteroDbAdapter method)
                if hasattr(self.local_adapter, "can_resolve_locally"):
                    if self.local_adapter.can_resolve_locally(attachment_key):
                        try:
                            file_path = self.local_adapter.download_attachment(
                                item_key, attachment_key, output_path
                            )
                            logger.debug(
                                f"Downloaded attachment from local: {attachment_key}",
                                extra={"attachment_key": attachment_key, "source": "local"},
                            )
                            return (file_path, "local")
                        except Exception as e:
                            logger.warning(
                                f"Local download failed for {attachment_key}, falling back to web: {e}",
                                extra={"attachment_key": attachment_key, "error": str(e)},
                            )
                    else:
                        logger.debug(
                            f"Attachment {attachment_key} not available locally, using web",
                            extra={"attachment_key": attachment_key},
                        )
                else:
                    # Try local first if adapter available
                    try:
                        file_path = self.local_adapter.download_attachment(
                            item_key, attachment_key, output_path
                        )
                        return (file_path, "local")
                    except Exception as e:
                        logger.warning(
                            f"Local download failed, falling back to web: {e}",
                            extra={"attachment_key": attachment_key, "error": str(e)},
                        )
            
            # Fallback to web
            file_path = self.web_adapter.download_attachment(item_key, attachment_key, output_path)
            logger.debug(
                f"Downloaded attachment from web: {attachment_key}",
                extra={"attachment_key": attachment_key, "source": "web"},
            )
            return (file_path, "web")
        
        if self.strategy == "web-first":
            try:
                file_path = self.web_adapter.download_attachment(item_key, attachment_key, output_path)
                return (file_path, "web")
            except ZoteroRateLimitError as e:
                logger.warning(
                    f"Web adapter rate limited for {attachment_key}, falling back to local: {e}",
                    extra={"attachment_key": attachment_key, "error": str(e)},
                )
                if self.is_local_available():
                    if hasattr(self.local_adapter, "can_resolve_locally"):
                        if self.local_adapter.can_resolve_locally(attachment_key):
                            file_path = self.local_adapter.download_attachment(
                                item_key, attachment_key, output_path
                            )
                            return (file_path, "local")
                    else:
                        try:
                            file_path = self.local_adapter.download_attachment(
                                item_key, attachment_key, output_path
                            )
                            return (file_path, "local")
                        except Exception:
                            pass  # Fall through to raise
                raise
            except Exception as e:
                logger.warning(
                    f"Web adapter failed for {attachment_key}, falling back to local: {e}",
                    extra={"attachment_key": attachment_key, "error": str(e)},
                )
                if self.is_local_available():
                    if hasattr(self.local_adapter, "can_resolve_locally"):
                        if self.local_adapter.can_resolve_locally(attachment_key):
                            try:
                                file_path = self.local_adapter.download_attachment(
                                    item_key, attachment_key, output_path
                                )
                                return (file_path, "local")
                            except Exception:
                                pass  # Fall through to raise
                    else:
                        try:
                            file_path = self.local_adapter.download_attachment(
                                item_key, attachment_key, output_path
                            )
                            return (file_path, "local")
                        except Exception:
                            pass  # Fall through to raise
                raise
        
        # auto strategy: Intelligent source selection
        if self.is_local_available():
            # Check if file exists locally first
            if hasattr(self.local_adapter, "can_resolve_locally"):
                if self.local_adapter.can_resolve_locally(attachment_key):
                    try:
                        file_path = self.local_adapter.download_attachment(
                            item_key, attachment_key, output_path
                        )
                        logger.debug(
                            f"Auto strategy: Using local for {attachment_key}",
                            extra={"attachment_key": attachment_key, "source": "local"},
                        )
                        return (file_path, "local")
                    except Exception as e:
                        logger.warning(
                            f"Local download failed in auto strategy, falling back to web: {e}",
                            extra={"attachment_key": attachment_key, "error": str(e)},
                        )
            else:
                # Try local first if available
                try:
                    file_path = self.local_adapter.download_attachment(
                        item_key, attachment_key, output_path
                    )
                    logger.debug(
                        f"Auto strategy: Using local for {attachment_key}",
                        extra={"attachment_key": attachment_key, "source": "local"},
                    )
                    return (file_path, "local")
                except Exception as e:
                    logger.debug(
                        f"Local unavailable in auto strategy, using web: {e}",
                        extra={"attachment_key": attachment_key, "error": str(e)},
                    )
        
        # Fallback to web
        file_path = self.web_adapter.download_attachment(item_key, attachment_key, output_path)
        logger.debug(
            f"Auto strategy: Using web for {attachment_key}",
            extra={"attachment_key": attachment_key, "source": "web"},
        )
        return (file_path, "web")
    
    def get_item_attachments(self, item_key: str) -> list[dict[str, Any]]:
        """
        Route attachment listing based on strategy.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            List of attachments
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError("Local adapter not available but strategy is 'local-only'")
            return self.local_adapter.get_item_attachments(item_key)
        
        if self.strategy == "web-only":
            return self.web_adapter.get_item_attachments(item_key)
        
        if self.strategy == "local-first":
            if self.is_local_available():
                try:
                    return self.local_adapter.get_item_attachments(item_key)
                except Exception as e:
                    logger.warning(f"Local adapter failed, falling back to web: {e}")
            return self.web_adapter.get_item_attachments(item_key)
        
        if self.strategy == "web-first":
            try:
                return self.web_adapter.get_item_attachments(item_key)
            except (ZoteroRateLimitError, Exception) as e:
                logger.warning(f"Web adapter failed, falling back to local: {e}")
                if self.is_local_available():
                    return self.local_adapter.get_item_attachments(item_key)
                raise
        
        # auto strategy
        if self.is_local_available():
            try:
                return self.local_adapter.get_item_attachments(item_key)
            except Exception as e:
                logger.warning(f"Local adapter failed, falling back to web: {e}")
        
        return self.web_adapter.get_item_attachments(item_key)
    
    def get_item_metadata(self, item_key: str) -> dict[str, Any]:
        """
        Route metadata fetching based on strategy.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            Item metadata dict
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError("Local adapter not available but strategy is 'local-only'")
            return self.local_adapter.get_item_metadata(item_key)
        
        if self.strategy == "web-only":
            return self.web_adapter.get_item_metadata(item_key)
        
        if self.strategy == "local-first":
            if self.is_local_available():
                try:
                    return self.local_adapter.get_item_metadata(item_key)
                except Exception as e:
                    logger.warning(f"Local adapter failed, falling back to web: {e}")
            return self.web_adapter.get_item_metadata(item_key)
        
        if self.strategy == "web-first":
            try:
                return self.web_adapter.get_item_metadata(item_key)
            except (ZoteroRateLimitError, Exception) as e:
                logger.warning(f"Web adapter failed, falling back to local: {e}")
                if self.is_local_available():
                    return self.local_adapter.get_item_metadata(item_key)
                raise
        
        # auto strategy
        if self.is_local_available():
            try:
                return self.local_adapter.get_item_metadata(item_key)
            except Exception as e:
                logger.warning(f"Local adapter failed, falling back to web: {e}")
        
        return self.web_adapter.get_item_metadata(item_key)
    
    def list_tags(self) -> list[dict[str, Any]]:
        """
        Route tag listing based on strategy.
        
        Returns:
            List of tags
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError("Local adapter not available but strategy is 'local-only'")
            return self.local_adapter.list_tags()
        
        if self.strategy == "web-only":
            return self.web_adapter.list_tags()
        
        if self.strategy == "local-first":
            if self.is_local_available():
                try:
                    return self.local_adapter.list_tags()
                except Exception as e:
                    logger.warning(f"Local adapter failed, falling back to web: {e}")
            return self.web_adapter.list_tags()
        
        if self.strategy == "web-first":
            try:
                return self.web_adapter.list_tags()
            except (ZoteroRateLimitError, Exception) as e:
                logger.warning(f"Web adapter failed, falling back to local: {e}")
                if self.is_local_available():
                    return self.local_adapter.list_tags()
                raise
        
        # auto strategy
        if self.is_local_available():
            try:
                return self.local_adapter.list_tags()
            except Exception as e:
                logger.warning(f"Local adapter failed, falling back to web: {e}")
        
        return self.web_adapter.list_tags()
    
    def get_recent_items(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Route recent items fetching based on strategy.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of recent items
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError("Local adapter not available but strategy is 'local-only'")
            return self.local_adapter.get_recent_items(limit)
        
        if self.strategy == "web-only":
            return self.web_adapter.get_recent_items(limit)
        
        if self.strategy == "local-first":
            if self.is_local_available():
                try:
                    return self.local_adapter.get_recent_items(limit)
                except Exception as e:
                    logger.warning(f"Local adapter failed, falling back to web: {e}")
            return self.web_adapter.get_recent_items(limit)
        
        if self.strategy == "web-first":
            try:
                return self.web_adapter.get_recent_items(limit)
            except (ZoteroRateLimitError, Exception) as e:
                logger.warning(f"Web adapter failed, falling back to local: {e}")
                if self.is_local_available():
                    return self.local_adapter.get_recent_items(limit)
                raise
        
        # auto strategy
        if self.is_local_available():
            try:
                return self.local_adapter.get_recent_items(limit)
            except Exception as e:
                logger.warning(f"Local adapter failed, falling back to web: {e}")
        
        return self.web_adapter.get_recent_items(limit)
    
    def find_collection_by_name(self, collection_name: str) -> dict[str, Any] | None:
        """
        Route collection search based on strategy.
        
        Args:
            collection_name: Collection name to search for
        
        Returns:
            Collection dict or None if not found
        """
        if self.strategy == "local-only":
            if not self.is_local_available():
                raise ValueError("Local adapter not available but strategy is 'local-only'")
            return self.local_adapter.find_collection_by_name(collection_name)
        
        if self.strategy == "web-only":
            return self.web_adapter.find_collection_by_name(collection_name)
        
        if self.strategy == "local-first":
            if self.is_local_available():
                try:
                    result = self.local_adapter.find_collection_by_name(collection_name)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Local adapter failed, falling back to web: {e}")
            return self.web_adapter.find_collection_by_name(collection_name)
        
        if self.strategy == "web-first":
            try:
                result = self.web_adapter.find_collection_by_name(collection_name)
                if result:
                    return result
            except (ZoteroRateLimitError, Exception) as e:
                logger.warning(f"Web adapter failed, falling back to local: {e}")
                if self.is_local_available():
                    return self.local_adapter.find_collection_by_name(collection_name)
                raise
            return None
        
        # auto strategy
        if self.is_local_available():
            try:
                result = self.local_adapter.find_collection_by_name(collection_name)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Local adapter failed, falling back to web: {e}")
        
        return self.web_adapter.find_collection_by_name(collection_name)

