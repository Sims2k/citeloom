"""Domain model for content fingerprinting and deduplication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


@dataclass(frozen=True)
class ContentFingerprint:
    """
    Content fingerprint for deduplication.
    
    Represents a document's unique identity based on:
    - Content hash (first 1MB + file size + policy versions)
    - File metadata (mtime + size) for collision protection
    - Policy versions (chunking + embedding) for invalidation
    
    Attributes:
        content_hash: SHA256 hash of (file_content_preview + file_size + embedding_model_id + chunking_policy_version + embedding_policy_version)
        file_mtime: File modification time (ISO format string)
        file_size: File size in bytes
        embedding_model: Embedding model identifier
        chunking_policy_version: Chunking policy version (e.g., "1.0")
        embedding_policy_version: Embedding policy version (e.g., "1.0")
    """

    content_hash: str
    file_mtime: str  # ISO format datetime string
    file_size: int
    embedding_model: str
    chunking_policy_version: str
    embedding_policy_version: str

    def __post_init__(self) -> None:
        """Validate content fingerprint."""
        if not self.content_hash or len(self.content_hash) < 8:
            raise ValueError("content_hash must be non-empty hex string (>= 8 chars)")
        try:
            datetime.fromisoformat(self.file_mtime)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"file_mtime must be valid ISO format datetime string: {e}")
        if self.file_size < 0:
            raise ValueError(f"file_size must be >= 0, got {self.file_size}")
        if not self.embedding_model:
            raise ValueError("embedding_model must be non-empty")
        if not self.chunking_policy_version:
            raise ValueError("chunking_policy_version must be non-empty")
        if not self.embedding_policy_version:
            raise ValueError("embedding_policy_version must be non-empty")

    def matches(
        self,
        other: ContentFingerprint,
        check_metadata: bool = True,
    ) -> bool:
        """
        Check if fingerprints match (document unchanged).
        
        Args:
            other: Fingerprint to compare against
            check_metadata: If True, also verify file metadata matches (collision protection)
        
        Returns:
            True if fingerprints match (document unchanged)
        """
        if self.content_hash != other.content_hash:
            return False

        if check_metadata:
            if self.file_mtime != other.file_mtime or self.file_size != other.file_size:
                return False  # Hash collision protection

        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "content_hash": self.content_hash,
            "file_mtime": self.file_mtime,
            "file_size": self.file_size,
            "embedding_model": self.embedding_model,
            "chunking_policy_version": self.chunking_policy_version,
            "embedding_policy_version": self.embedding_policy_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentFingerprint:
        """Deserialize from dict."""
        return cls(
            content_hash=data["content_hash"],
            file_mtime=data["file_mtime"],
            file_size=data["file_size"],
            embedding_model=data["embedding_model"],
            chunking_policy_version=data["chunking_policy_version"],
            embedding_policy_version=data["embedding_policy_version"],
        )


