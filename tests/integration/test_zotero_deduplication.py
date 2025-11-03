"""Integration tests for incremental deduplication (T118)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.models.content_fingerprint import ContentFingerprint
from src.domain.models.download_manifest import DownloadManifestAttachment
from src.domain.services.content_fingerprint import ContentFingerprintService


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a sample file for testing."""
    test_file = tmp_path / "test.pdf"
    content = b"Test document content for fingerprinting " * 100
    test_file.write_bytes(content)
    return test_file


@pytest.fixture
def modified_file(tmp_path: Path) -> Path:
    """Create a modified version of the file."""
    test_file = tmp_path / "test_modified.pdf"
    content = b"Modified test document content " * 100
    test_file.write_bytes(content)
    return test_file


class TestIncrementalDeduplication:
    """Test incremental deduplication logic."""

    def test_fingerprint_matches_unchanged_file(self, sample_file: Path):
        """Test that fingerprints match for unchanged files."""
        embedding_model = "fastembed/all-MiniLM-L6-v2"
        chunking_policy = "1.0"
        embedding_policy = "1.0"

        # Compute fingerprint twice
        fp1 = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        fp2 = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # Should match
        assert fp1.matches(fp2) is True
        assert ContentFingerprintService.is_unchanged(fp1, fp2) is True

    def test_fingerprint_differs_for_changed_file(self, sample_file: Path, modified_file: Path):
        """Test that fingerprints differ for changed files."""
        embedding_model = "fastembed/all-MiniLM-L6-v2"
        chunking_policy = "1.0"
        embedding_policy = "1.0"

        fp1 = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        fp2 = ContentFingerprintService.compute_fingerprint(
            file_path=modified_file,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # Should not match
        assert fp1.matches(fp2) is False
        assert ContentFingerprintService.is_unchanged(fp1, fp2) is False

    def test_fingerprint_invalidated_by_policy_change(self, sample_file: Path):
        """Test that fingerprints are invalidated when policy changes."""
        embedding_model = "fastembed/all-MiniLM-L6-v2"

        # Original fingerprint with policy 1.0
        fp_old = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model=embedding_model,
            chunking_policy_version="1.0",
            embedding_policy_version="1.0",
        )

        # New fingerprint with policy 2.0
        fp_new = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model=embedding_model,
            chunking_policy_version="2.0",  # Policy changed
            embedding_policy_version="1.0",
        )

        # Should not match (policy version differs)
        assert fp_old.chunking_policy_version != fp_new.chunking_policy_version
        # Hash should be different due to policy version in hash
        assert fp_old.content_hash != fp_new.content_hash

    def test_fingerprint_invalidated_by_embedding_model_change(self, sample_file: Path):
        """Test that fingerprints are invalidated when embedding model changes."""
        chunking_policy = "1.0"
        embedding_policy = "1.0"

        # Original fingerprint with model A
        fp_old = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model="fastembed/all-MiniLM-L6-v2",
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # New fingerprint with model B
        fp_new = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model="openai/text-embedding-ada-002",  # Different model
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # Should not match (embedding model differs)
        assert fp_old.embedding_model != fp_new.embedding_model
        # Hash should be different due to model in hash
        assert fp_old.content_hash != fp_new.content_hash

    def test_collision_protection_with_metadata(self, sample_file: Path):
        """Test that metadata matching prevents hash collisions."""
        embedding_model = "fastembed/all-MiniLM-L6-v2"
        chunking_policy = "1.0"
        embedding_policy = "1.0"

        fp1 = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # Create a fingerprint with same hash but different metadata (hypothetical collision)
        # In practice, we test that matches() checks metadata too

        fp_collision = ContentFingerprint(
            content_hash=fp1.content_hash,  # Same hash
            file_mtime="2020-01-01T00:00:00",  # Different mtime
            file_size=fp1.file_size,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # Should not match even with same hash (metadata mismatch)
        assert fp1.matches(fp_collision) is False

    def test_is_unchanged_with_none_stored(self, sample_file: Path):
        """Test that is_unchanged returns False when no stored fingerprint."""
        embedding_model = "fastembed/all-MiniLM-L6-v2"
        chunking_policy = "1.0"
        embedding_policy = "1.0"

        computed = ContentFingerprintService.compute_fingerprint(
            file_path=sample_file,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # None stored means first import, not unchanged
        assert ContentFingerprintService.is_unchanged(None, computed) is False

    def test_manifest_attachment_with_fingerprint(self, tmp_path: Path):
        """Test that DownloadManifestAttachment stores and retrieves fingerprints."""
        embedding_model = "fastembed/all-MiniLM-L6-v2"
        chunking_policy = "1.0"
        embedding_policy = "1.0"

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"test content")

        fingerprint = ContentFingerprintService.compute_fingerprint(
            file_path=test_file,
            embedding_model=embedding_model,
            chunking_policy_version=chunking_policy,
            embedding_policy_version=embedding_policy,
        )

        # Create manifest attachment with fingerprint
        attachment = DownloadManifestAttachment(
            attachment_key="ATTACH1",
            filename="test.pdf",
            local_path=test_file,
            download_status="success",
            file_size=test_file.stat().st_size,
            content_fingerprint=fingerprint,
        )

        assert attachment.content_fingerprint is not None
        assert attachment.content_fingerprint.content_hash == fingerprint.content_hash

        # Test serialization
        data = attachment.to_dict()
        assert "content_fingerprint" in data

        # Test deserialization
        attachment2 = DownloadManifestAttachment.from_dict(data)
        assert attachment2.content_fingerprint is not None
        assert attachment2.content_fingerprint.content_hash == fingerprint.content_hash
        assert attachment2.content_fingerprint.matches(fingerprint) is True
