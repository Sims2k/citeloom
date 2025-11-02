"""Port interface for importing documents from Zotero collections."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterator


class ZoteroImporterPort(ABC):
    """Port for importing documents from Zotero collections."""

    @abstractmethod
    def list_collections(self) -> list[dict[str, Any]]:
        """
        List all top-level collections in Zotero library.
        
        Returns:
            List of collections with keys: 'key', 'name', 'parentCollection'
        """
        pass

    @abstractmethod
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Get items in a collection (generator to avoid loading all into memory).
        
        Args:
            collection_key: Zotero collection key
            include_subcollections: If True, recursively include items from subcollections
        
        Yields:
            Zotero items with keys: 'key', 'data' (containing title, itemType, etc.)
        """
        pass

    @abstractmethod
    def get_item_attachments(
        self,
        item_key: str,
    ) -> list[dict[str, Any]]:
        """
        Get PDF attachments for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            List of attachments with keys: 'key', 'data' (containing filename, contentType, linkMode)
        """
        pass

    @abstractmethod
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> Path:
        """
        Download a file attachment from Zotero.
        
        Args:
            item_key: Zotero item key
            attachment_key: Zotero attachment key
            output_path: Local path where file should be saved
        
        Returns:
            Path to downloaded file
        
        Raises:
            ZoteroAPIError: If download fails after retries
        """
        pass

    @abstractmethod
    def get_item_metadata(
        self,
        item_key: str,
    ) -> dict[str, Any]:
        """
        Get full metadata for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            Item metadata dict with keys: title, creators (authors), date (year), DOI, tags, collections
        """
        pass

    @abstractmethod
    def list_tags(self) -> list[dict[str, Any]]:
        """
        List all tags used in Zotero library.
        
        Returns:
            List of tags with keys: 'tag', 'meta' (containing numItems count)
        """
        pass

    @abstractmethod
    def get_recent_items(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recently added items to Zotero library.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of items sorted by dateAdded (descending)
        """
        pass

    @abstractmethod
    def find_collection_by_name(
        self,
        collection_name: str,
    ) -> dict[str, Any] | None:
        """
        Find collection by name (case-insensitive partial match).
        
        Args:
            collection_name: Collection name to search for
        
        Returns:
            Collection dict with keys: 'key', 'name', or None if not found
        """
        pass

