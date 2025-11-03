"""Domain service for content fingerprint computation and comparison."""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from src.domain.models.content_fingerprint import ContentFingerprint


class ContentFingerprintService:
    """
    Domain service for computing and comparing content fingerprints.
    
    This service is pure (no I/O) and deterministic.
    """

    # Preview size: first 1MB of file content for hashing
    PREVIEW_SIZE_BYTES = 1024 * 1024  # 1 MB

    @staticmethod
    def compute_fingerprint(
        file_path: Path,
        embedding_model: str,
        chunking_policy_version: str,
        embedding_policy_version: str,
    ) -> ContentFingerprint:
        """
        Compute content fingerprint for a file.
        
        Fingerprint includes:
        - Content hash: SHA256 of (first 1MB preview + file_size + embedding_model + policy versions)
        - File metadata: mtime (ISO format) + file_size for collision protection
        
        Args:
            file_path: Path to file (must exist and be readable)
            embedding_model: Embedding model identifier
            chunking_policy_version: Chunking policy version (e.g., "1.0")
            embedding_policy_version: Embedding policy version (e.g., "1.0")
        
        Returns:
            ContentFingerprint with computed hash and metadata
        
        Raises:
            FileNotFoundError: If file does not exist
            OSError: If file cannot be read
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Get file metadata
        stat = file_path.stat()
        file_size = stat.st_size
        file_mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()

        # Read file preview (first 1MB)
        with file_path.open("rb") as f:
            preview = f.read(ContentFingerprintService.PREVIEW_SIZE_BYTES)

        # Compute content hash: preview + file_size + embedding_model + policy versions
        hash_obj = hashlib.sha256()
        hash_obj.update(preview)
        hash_obj.update(str(file_size).encode("utf-8"))
        hash_obj.update(embedding_model.encode("utf-8"))
        hash_obj.update(chunking_policy_version.encode("utf-8"))
        hash_obj.update(embedding_policy_version.encode("utf-8"))
        content_hash = hash_obj.hexdigest()

        return ContentFingerprint(
            content_hash=content_hash,
            file_mtime=file_mtime,
            file_size=file_size,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy_version,
            embedding_policy_version=embedding_policy_version,
        )

    @staticmethod
    def is_unchanged(
        stored: ContentFingerprint | None,
        computed: ContentFingerprint,
    ) -> bool:
        """
        Check if document is unchanged by comparing fingerprints.
        
        Uses full comparison (hash + metadata) for collision protection per FR-019.
        
        Args:
            stored: Previously stored fingerprint (None if first import)
            computed: Newly computed fingerprint
        
        Returns:
            True if document is unchanged (fingerprints match), False otherwise
        """
        if stored is None:
            return False  # First import, not unchanged

        return stored.matches(computed, check_metadata=True)

