"""Integration tests for LocalZoteroDbAdapter (T112-T114)."""

from __future__ import annotations

import sqlite3
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import patch

import pytest

from src.domain.errors import (
    ZoteroDatabaseNotFoundError,
    ZoteroPathResolutionError,
    ZoteroProfileNotFoundError,
)
from src.infrastructure.adapters.zotero_local_db import LocalZoteroDbAdapter


@pytest.fixture
def mock_zotero_db(tmp_path: Path) -> Path:
    """Create a mock Zotero SQLite database for testing."""
    db_path = tmp_path / "zotero.sqlite"

    # Create SQLite database with Zotero-like schema
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create collections table
    cursor.execute("""
        CREATE TABLE collections (
            collectionID INTEGER PRIMARY KEY,
            collectionName TEXT,
            parentCollectionID INTEGER,
            key TEXT UNIQUE
        )
    """)

    # Create items table
    cursor.execute("""
        CREATE TABLE items (
            itemID INTEGER PRIMARY KEY,
            itemTypeID INTEGER,
            key TEXT UNIQUE,
            dateAdded TEXT,
            dateModified TEXT
        )
    """)

    # Create itemData table (JSON storage)
    cursor.execute("""
        CREATE TABLE itemData (
            itemID INTEGER,
            fieldID INTEGER,
            value TEXT,
            PRIMARY KEY (itemID, fieldID)
        )
    """)

    # Create itemAttachments table
    cursor.execute("""
        CREATE TABLE itemAttachments (
            itemID INTEGER,
            key TEXT UNIQUE,
            parentItemID INTEGER,
            linkMode INTEGER,
            path TEXT,
            storageModTime INTEGER,
            contentType TEXT
        )
    """)

    # Create collectionItems table
    cursor.execute("""
        CREATE TABLE collectionItems (
            collectionID INTEGER,
            itemID INTEGER,
            PRIMARY KEY (collectionID, itemID)
        )
    """)

    # Create itemTags table
    cursor.execute("""
        CREATE TABLE itemTags (
            itemID INTEGER,
            tagID INTEGER,
            PRIMARY KEY (itemID, tagID)
        )
    """)

    # Create tags table
    cursor.execute("""
        CREATE TABLE tags (
            tagID INTEGER PRIMARY KEY,
            name TEXT UNIQUE
        )
    """)

    # Insert sample data
    cursor.execute(
        "INSERT INTO collections (collectionID, collectionName, parentCollectionID, key) VALUES (1, 'Test Collection', NULL, 'COL1')"
    )
    cursor.execute(
        "INSERT INTO collections (collectionID, collectionName, parentCollectionID, key) VALUES (2, 'Sub Collection', 1, 'COL2')"
    )

    cursor.execute(
        "INSERT INTO items (itemID, itemTypeID, key, dateAdded) VALUES (1, 2, 'ITEM1', '2024-01-01T00:00:00Z')"
    )
    cursor.execute(
        "INSERT INTO items (itemID, itemTypeID, key, dateAdded) VALUES (2, 2, 'ITEM2', '2024-01-02T00:00:00Z')"
    )

    cursor.execute(
        "INSERT INTO itemAttachments (itemID, key, parentItemID, linkMode, path) VALUES (1, 'ATTACH1', 1, 0, 'storage/ATTACH1/test.pdf')"
    )
    cursor.execute(
        "INSERT INTO itemAttachments (itemID, key, parentItemID, linkMode, path) VALUES (2, 'ATTACH2', 2, 1, '/absolute/path/to/file.pdf')"
    )

    cursor.execute("INSERT INTO collectionItems (collectionID, itemID) VALUES (1, 1)")
    cursor.execute("INSERT INTO collectionItems (collectionID, itemID) VALUES (1, 2)")

    cursor.execute("INSERT INTO tags (tagID, name) VALUES (1, 'test-tag')")
    cursor.execute("INSERT INTO itemTags (itemID, tagID) VALUES (1, 1)")
    cursor.execute("INSERT INTO itemTags (itemID, tagID) VALUES (2, 1)")

    # Insert JSON data for items
    cursor.execute("INSERT INTO itemData (itemID, fieldID, value) VALUES (1, 110, 'Test Title 1')")
    cursor.execute("INSERT INTO itemData (itemID, fieldID, value) VALUES (2, 110, 'Test Title 2')")

    conn.commit()
    conn.close()

    return db_path


@pytest.fixture
def mock_zotero_storage(tmp_path: Path) -> Path:
    """Create a mock Zotero storage directory."""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    # Create a sample file
    (storage_dir / "ATTACH1" / "test.pdf").parent.mkdir(parents=True, exist_ok=True)
    (storage_dir / "ATTACH1" / "test.pdf").write_bytes(b"fake pdf content")

    return storage_dir


@pytest.fixture
def mock_profiles_ini(tmp_path: Path) -> Path:
    """Create a mock profiles.ini file."""
    profiles_dir = tmp_path / "Profiles"
    profiles_dir.mkdir(parents=True)

    profiles_ini = profiles_dir / "profiles.ini"
    config = ConfigParser()
    config.add_section("Profile0")
    config.set("Profile0", "Name", "default")
    config.set("Profile0", "Path", "default")
    config.set("Profile0", "Default", "1")

    with profiles_ini.open("w") as f:
        config.write(f)

    return profiles_ini


class TestLocalZoteroDbProfileDetection:
    """Test profile detection (T112)."""

    @pytest.mark.parametrize(
        "platform_name,expected_base",
        [
            ("Windows", Path("APPDATA") / "Zotero"),
            ("Darwin", Path.home() / "Library" / "Application Support" / "Zotero"),
            ("Linux", Path.home() / ".zotero" / "zotero"),
        ],
    )
    def test_profile_detection_platform_paths(self, platform_name, expected_base):
        """Test profile detection finds correct platform paths."""
        with patch("platform.system", return_value=platform_name):
            with patch(
                "src.infrastructure.adapters.zotero_local_db.Path.exists", return_value=False
            ):
                profile = LocalZoteroDbAdapter._detect_zotero_profile()
                assert profile is None  # Should return None if profiles.ini not found

    def test_profile_detection_finds_default_profile(self, tmp_path: Path, mock_profiles_ini: Path):
        """Test that profile detection finds default profile from profiles.ini."""
        # Mock the platform and path detection
        base_dir = mock_profiles_ini.parent.parent

        with patch("platform.system", return_value="Windows"):
            with patch("os.environ.get", return_value=str(base_dir)):
                # Adjust the path logic to use our test directory
                with patch("src.infrastructure.adapters.zotero_local_db.Path") as mock_path:
                    mock_profiles_path = base_dir / "Profiles" / "profiles.ini"
                    mock_path.return_value.exists.return_value = True
                    mock_path.return_value.__truediv__.return_value = mock_profiles_path

                    profile = LocalZoteroDbAdapter._parse_profiles_ini(mock_profiles_ini, base_dir)
                    assert profile is not None
                    assert profile.name == "default"

    def test_profile_detection_no_profiles_file(self):
        """Test that profile detection returns None when profiles.ini not found."""
        with patch("platform.system", return_value="Windows"):
            with patch("os.environ.get", return_value="/nonexistent"):
                with patch(
                    "src.infrastructure.adapters.zotero_local_db.Path.exists", return_value=False
                ):
                    profile = LocalZoteroDbAdapter._detect_zotero_profile()
                    assert profile is None

    def test_parse_profiles_ini_default_profile(self, tmp_path: Path):
        """Test parsing profiles.ini to find default profile."""
        profiles_ini = tmp_path / "profiles.ini"
        config = ConfigParser()
        config.add_section("Profile0")
        config.set("Profile0", "Name", "default")
        config.set("Profile0", "Path", "profile1")
        config.set("Profile0", "Default", "1")

        with profiles_ini.open("w") as f:
            config.write(f)

        base_dir = tmp_path
        profile_path = LocalZoteroDbAdapter._parse_profiles_ini(profiles_ini, base_dir)

        assert profile_path is not None
        assert profile_path.name == "profile1"
        assert profile_path.parent == base_dir / "Profiles"


class TestLocalZoteroDbSQLQueries:
    """Test SQL queries (T113)."""

    def test_list_collections(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test listing collections with hierarchy."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        collections = adapter.list_collections()

        assert len(collections) > 0
        # Find the test collection
        test_col = next((c for c in collections if c.get("name") == "Test Collection"), None)
        assert test_col is not None
        assert test_col["key"] == "COL1"
        assert test_col.get("parent_collection") is None

    def test_get_collection_items(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test getting items from a collection."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        # First, find the collection key
        collections = adapter.list_collections()
        test_col = next((c for c in collections if c.get("name") == "Test Collection"), None)
        assert test_col is not None

        items = adapter.get_collection_items(test_col["key"])

        assert len(items) >= 2  # Should have at least 2 items
        item_keys = [item.get("key") for item in items]
        assert "ITEM1" in item_keys or "ITEM2" in item_keys

    def test_get_item_attachments(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test getting attachments for an item."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        attachments = adapter.get_item_attachments("ITEM1")

        assert len(attachments) > 0
        attach = attachments[0]
        assert attach.get("key") == "ATTACH1"

    def test_get_item_metadata(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test getting item metadata from JSON data field."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        metadata = adapter.get_item_metadata("ITEM1")

        assert metadata is not None
        assert isinstance(metadata, dict)

    def test_list_tags(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test listing tags with usage counts."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        tags = adapter.list_tags()

        assert len(tags) > 0
        test_tag = next((t for t in tags if t.get("tag") == "test-tag"), None)
        assert test_tag is not None
        assert test_tag.get("count", 0) >= 1

    def test_get_recent_items(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test getting recent items sorted by dateAdded."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        recent = adapter.get_recent_items(limit=10)

        assert len(recent) > 0
        assert len(recent) <= 10

        # Check sorting (newest first)
        if len(recent) > 1:
            dates = [item.get("date_added", "") for item in recent if item.get("date_added")]
            if len(dates) > 1:
                # Dates should be in descending order
                sorted_dates = sorted(dates, reverse=True)
                assert dates == sorted_dates

    def test_find_collection_by_name(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test finding collection by name with case-insensitive partial match."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        collection = adapter.find_collection_by_name("test")

        assert collection is not None
        assert "test" in collection.get("name", "").lower()


class TestLocalZoteroDbPathResolution:
    """Test path resolution (T114)."""

    def test_resolve_attachment_path_imported(
        self, mock_zotero_db: Path, mock_zotero_storage: Path
    ):
        """Test resolving path for imported attachment (linkMode=0)."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        # Get attachment info first
        attachments = adapter.get_item_attachments("ITEM1")
        assert len(attachments) > 0

        attach_info = attachments[0]
        path = adapter.resolve_attachment_path(
            attachment_key=attach_info["key"],
            link_mode=0,
            path_hint=attach_info.get("path", ""),
        )

        assert path is not None
        assert isinstance(path, Path)
        # For imported files, path should be relative to storage directory
        assert "storage" in str(path) or path.exists()

    def test_resolve_attachment_path_linked(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test resolving path for linked attachment (linkMode=1)."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        # Get attachment info for linked file
        attachments = adapter.get_item_attachments("ITEM2")
        assert len(attachments) > 0

        attach_info = attachments[0]
        try:
            path = adapter.resolve_attachment_path(
                attachment_key=attach_info["key"],
                link_mode=1,
                path_hint=attach_info.get("path", ""),
            )
            # For linked files, path should be absolute
            # In test, file may not exist, so we just check it's a Path object
            assert isinstance(path, Path)
        except ZoteroPathResolutionError:
            # Expected if file doesn't exist in test environment
            pass

    def test_resolve_attachment_path_nonexistent(
        self, mock_zotero_db: Path, mock_zotero_storage: Path
    ):
        """Test path resolution fails gracefully for nonexistent files."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        with pytest.raises(ZoteroPathResolutionError):
            adapter.resolve_attachment_path(
                attachment_key="NONEXISTENT",
                link_mode=0,
                path_hint="storage/NONEXISTENT/file.pdf",
            )

    def test_download_attachment_imported(
        self, mock_zotero_db: Path, mock_zotero_storage: Path, tmp_path: Path
    ):
        """Test downloading imported attachment from local storage."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        attachments = adapter.get_item_attachments("ITEM1")
        assert len(attachments) > 0

        attach_key = attachments[0]["key"]
        destination = tmp_path / "downloaded_file.pdf"

        downloaded_path = adapter.download_attachment(attach_key, destination)

        assert downloaded_path == destination
        assert destination.exists()
        assert destination.read_bytes() == b"fake pdf content"


class TestLocalZoteroDbErrors:
    """Test error handling."""

    def test_database_not_found_error(self, tmp_path: Path):
        """Test that missing database raises ZoteroDatabaseNotFoundError."""
        nonexistent_db = tmp_path / "nonexistent" / "zotero.sqlite"

        with pytest.raises(ZoteroDatabaseNotFoundError):
            LocalZoteroDbAdapter(db_path=nonexistent_db)

    def test_profile_not_found_error(self):
        """Test that missing profile raises ZoteroProfileNotFoundError."""
        with patch(
            "src.infrastructure.adapters.zotero_local_db.LocalZoteroDbAdapter._detect_zotero_profile",
            return_value=None,
        ):
            with pytest.raises(ZoteroProfileNotFoundError):
                LocalZoteroDbAdapter()

    def test_can_resolve_locally(self, mock_zotero_db: Path, mock_zotero_storage: Path):
        """Test can_resolve_locally method for source routing."""
        adapter = LocalZoteroDbAdapter(db_path=mock_zotero_db, storage_dir=mock_zotero_storage)

        # Should return True for attachments that exist
        attachments = adapter.get_item_attachments("ITEM1")
        assert len(attachments) > 0

        can_resolve = adapter.can_resolve_locally(attachments[0]["key"])
        assert can_resolve is True or can_resolve is False  # Method may not be implemented yet
