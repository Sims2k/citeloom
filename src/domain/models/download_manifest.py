"""Domain models for Zotero download manifests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

    from src.domain.models.content_fingerprint import ContentFingerprint


@dataclass
class DownloadManifestAttachment:
    """
    Represents a downloaded file attachment in the manifest.
    
    Attributes:
        attachment_key: Zotero attachment key
        filename: Original filename
        local_path: Local file path where downloaded
        download_status: "success" | "failed" | "pending"
        file_size: File size in bytes (if download succeeded)
        error: Error message (if download failed)
        source: Source marker ("local" | "web") indicating which source provided the attachment
        content_fingerprint: Content fingerprint for deduplication (None if not computed yet)
    """

    attachment_key: str
    filename: str
    local_path: Path
    download_status: str = "pending"
    file_size: int | None = None
    error: str | None = None
    source: str | None = None  # "local" | "web"
    content_fingerprint: ContentFingerprint | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result: dict[str, Any] = {
            "attachment_key": self.attachment_key,
            "filename": self.filename,
            "local_path": str(self.local_path),
            "download_status": self.download_status,
        }
        if self.file_size is not None:
            result["file_size"] = self.file_size
        if self.error is not None:
            result["error"] = self.error
        if self.source is not None:
            result["source"] = self.source
        if self.content_fingerprint is not None:
            result["content_fingerprint"] = self.content_fingerprint.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadManifestAttachment:
        """Deserialize from dict."""
        from src.domain.models.content_fingerprint import ContentFingerprint

        fingerprint_data = data.get("content_fingerprint")
        fingerprint = ContentFingerprint.from_dict(fingerprint_data) if fingerprint_data else None

        return cls(
            attachment_key=data["attachment_key"],
            filename=data["filename"],
            local_path=Path(data["local_path"]),
            download_status=data.get("download_status", "pending"),
            file_size=data.get("file_size"),
            error=data.get("error"),
            source=data.get("source"),
            content_fingerprint=fingerprint,
        )

    def __post_init__(self) -> None:
        """Validate download manifest attachment."""
        if not self.attachment_key:
            raise ValueError("attachment_key must be non-empty")
        if self.download_status not in {"success", "failed", "pending"}:
            raise ValueError(f"download_status must be one of {{'success', 'failed', 'pending'}}, got {self.download_status}")
        if self.download_status == "success" and not self.local_path.is_absolute():
            raise ValueError(f"local_path must be absolute when download_status is 'success', got {self.local_path}")
        if self.download_status == "failed" and not self.error:
            raise ValueError("error must be non-empty when download_status is 'failed'")
        if self.file_size is not None and self.file_size < 0:
            raise ValueError("file_size must be >= 0 if provided")
        if self.source is not None and self.source not in {"local", "web"}:
            raise ValueError(f"source must be 'local' or 'web' if provided, got {self.source}")


@dataclass
class DownloadManifestItem:
    """
    Represents a Zotero item with its downloaded attachments in the manifest.
    
    Attributes:
        item_key: Zotero item key
        title: Item title
        attachments: List of downloaded attachments
        metadata: Zotero item metadata (citekey, authors, year, tags, collections)
    """

    item_key: str
    title: str
    attachments: list[DownloadManifestAttachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_attachment(self, attachment: DownloadManifestAttachment) -> None:
        """Add attachment to item."""
        self.attachments.append(attachment)

    def get_pdf_attachments(self) -> list[DownloadManifestAttachment]:
        """Filter PDF attachments only."""
        return [att for att in self.attachments if att.filename.lower().endswith(".pdf")]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "item_key": self.item_key,
            "title": self.title,
            "attachments": [att.to_dict() for att in self.attachments],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadManifestItem:
        """Deserialize from dict."""
        return cls(
            item_key=data["item_key"],
            title=data.get("title", ""),
            attachments=[DownloadManifestAttachment.from_dict(att_data) for att_data in data.get("attachments", [])],
            metadata=data.get("metadata", {}),
        )

    def __post_init__(self) -> None:
        """Validate download manifest item."""
        if not self.item_key:
            raise ValueError("item_key must be non-empty")


@dataclass
class DownloadManifest:
    """
    Documents downloaded files from a Zotero collection for two-phase import.
    
    Attributes:
        collection_key: Zotero collection key
        collection_name: Zotero collection name
        download_time: Download operation timestamp
        items: List of items with downloaded attachments
    """

    collection_key: str
    collection_name: str
    download_time: datetime = field(default_factory=datetime.now)
    items: list[DownloadManifestItem] = field(default_factory=list)

    def add_item(self, item: DownloadManifestItem) -> None:
        """Add item to manifest."""
        self.items.append(item)

    def get_item_by_key(self, item_key: str) -> DownloadManifestItem | None:
        """Find item by Zotero key."""
        for item in self.items:
            if item.item_key == item_key:
                return item
        return None

    def get_all_file_paths(self) -> list[Path]:
        """Get all downloaded file paths."""
        paths: list[Path] = []
        for item in self.items:
            for attachment in item.attachments:
                if attachment.download_status == "success":
                    paths.append(attachment.local_path)
        return paths

    def get_successful_downloads(self) -> list[DownloadManifestItem]:
        """Filter items with successful downloads."""
        successful_items: list[DownloadManifestItem] = []
        for item in self.items:
            # Include item if it has at least one successful attachment
            if any(att.download_status == "success" for att in item.attachments):
                successful_items.append(item)
        return successful_items

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "collection_key": self.collection_key,
            "collection_name": self.collection_name,
            "download_time": self.download_time.isoformat(),
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadManifest:
        """Deserialize from dict."""
        download_time = datetime.fromisoformat(data["download_time"]) if isinstance(data.get("download_time"), str) else datetime.now()
        return cls(
            collection_key=data["collection_key"],
            collection_name=data["collection_name"],
            download_time=download_time,
            items=[DownloadManifestItem.from_dict(item_data) for item_data in data.get("items", [])],
        )

    def __post_init__(self) -> None:
        """Validate download manifest."""
        if not self.collection_key:
            raise ValueError("collection_key must be non-empty")

