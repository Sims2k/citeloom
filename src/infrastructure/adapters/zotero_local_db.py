"""Adapter for importing documents from Zotero collections via local SQLite database."""

from __future__ import annotations

import json
import logging
import os
import platform
import sqlite3
from configparser import ConfigParser
from pathlib import Path
from typing import Any, Iterator

from ...application.ports.zotero_importer import ZoteroImporterPort
from ...domain.errors import (
    ZoteroDatabaseLockedError,
    ZoteroDatabaseNotFoundError,
    ZoteroPathResolutionError,
    ZoteroProfileNotFoundError,
)

logger = logging.getLogger(__name__)


class LocalZoteroDbAdapter(ZoteroImporterPort):
    """
    Adapter for importing documents from Zotero collections using local SQLite database.
    
    Provides offline access to Zotero library without network calls or rate limits.
    Opens database in immutable read-only mode to safely access while Zotero is running.
    """

    def __init__(self, db_path: Path | None = None, storage_dir: Path | None = None) -> None:
        """
        Initialize local Zotero database adapter.
        
        Args:
            db_path: Optional path to zotero.sqlite file. If None, auto-detects profile.
            storage_dir: Optional path to Zotero storage directory. If None, auto-detects from profile.
        
        Raises:
            ZoteroProfileNotFoundError: If profile cannot be detected
            ZoteroDatabaseNotFoundError: If database file not found
            ZoteroDatabaseLockedError: If database is locked
        """
        self._conn: sqlite3.Connection | None = None
        self._db_path: Path | None = None
        self._storage_dir: Path | None = None
        
        # Auto-detect profile if db_path not provided
        if db_path is None:
            profile_dir = self._detect_zotero_profile()
            if profile_dir is None:
                raise ZoteroProfileNotFoundError(
                    "Zotero profile directory",
                    hint="Ensure Zotero is installed and has been run at least once. "
                    "Or provide db_path explicitly via configuration.",
                )
            db_path = profile_dir / "zotero.sqlite"
            # Storage directory is typically alongside the profile
            if storage_dir is None:
                # Check for storage directory in profile or parent
                potential_storage = profile_dir.parent / "storage"
                if potential_storage.exists():
                    self._storage_dir = potential_storage
                else:
                    # Fallback: try to find storage directory from Zotero config
                    storage_base = profile_dir.parent.parent
                    self._storage_dir = storage_base / "storage"
        
        self._db_path = db_path
        if storage_dir is not None:
            self._storage_dir = storage_dir
        
        # Validate database exists
        if not self._db_path.exists():
            raise ZoteroDatabaseNotFoundError(
                str(self._db_path),
                hint="Ensure Zotero is installed and has been run at least once. "
                "Database file should be at: zotero.sqlite in profile directory.",
            )
        
        # Open database in immutable read-only mode
        self._open_db_readonly()
    
    @staticmethod
    def _detect_zotero_profile() -> Path | None:
        """
        Detect Zotero profile directory per platform.
        
        Returns:
            Path to profile directory, or None if not found
        
        Platform paths:
        - Windows: %APPDATA%\\Zotero\\Profiles\\{profile_id}\\
        - macOS: ~/Library/Application Support/Zotero/Profiles/{profile_id}/
        - Linux: ~/.zotero/zotero/Profiles/{profile_id}/
        """
        system = platform.system()
        
        if system == "Windows":
            appdata = os.environ.get("APPDATA", "")
            if not appdata:
                return None
            base = Path(appdata) / "Zotero"
            profiles_ini = base / "Profiles" / "profiles.ini"
        elif system == "Darwin":  # macOS
            base = Path.home() / "Library" / "Application Support" / "Zotero"
            profiles_ini = base / "Profiles" / "profiles.ini"
        else:  # Linux
            base = Path.home() / ".zotero" / "zotero"
            profiles_ini = base / "Profiles" / "profiles.ini"
        
        if not profiles_ini.exists():
            return None
        
        # Parse profiles.ini to find default profile
        profile_path = LocalZoteroDbAdapter._parse_profiles_ini(profiles_ini, base)
        return profile_path
    
    @staticmethod
    def _parse_profiles_ini(profiles_ini: Path, base_dir: Path) -> Path | None:
        """
        Parse profiles.ini to find default profile.
        
        Args:
            profiles_ini: Path to profiles.ini file
            base_dir: Base directory for profiles
        
        Returns:
            Path to default profile directory, or None if not found
        """
        config = ConfigParser()
        config.read(profiles_ini)
        
        # Look for profile with Default=1
        for section in config.sections():
            if section.startswith("Profile"):
                try:
                    is_default = config.getboolean(section, "Default", fallback=False)
                    if is_default:
                        profile_id = config.get(section, "Path", fallback=None)
                        if profile_id:
                            return base_dir / "Profiles" / profile_id
                except (ValueError, TypeError):
                    # Skip invalid sections
                    continue
        
        # Fallback: use first profile if no default marked
        for section in config.sections():
            if section.startswith("Profile"):
                try:
                    profile_id = config.get(section, "Path", fallback=None)
                    if profile_id:
                        return base_dir / "Profiles" / profile_id
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def _open_db_readonly(self) -> None:
        """
        Open SQLite database in immutable read-only mode.
        
        Uses URI mode with immutable=1&mode=ro flags to ensure:
        - No writes possible (safe with Zotero running)
        - Read-only snapshot access
        - No locking conflicts
        
        Raises:
            ZoteroDatabaseLockedError: If database is locked
            ZoteroDatabaseNotFoundError: If database file doesn't exist
        """
        if self._db_path is None:
            raise ZoteroDatabaseNotFoundError("Database path not set")
        
        try:
            # Convert to absolute path for URI mode
            abs_path = self._db_path.resolve()
            
            # Use URI mode with immutable=1 and mode=ro flags
            uri = f"file:{abs_path}?immutable=1&mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            
            # Enable JSON1 extension for json_extract() queries
            # Note: enable_load_extension may not work on all systems
            # JSON1 should be built-in in SQLite 3.38+, but we use json() function instead
            self._conn.row_factory = sqlite3.Row
            
            logger.info(
                "Opened Zotero database in read-only mode",
                extra={"db_path": str(abs_path)},
            )
        except sqlite3.OperationalError as e:
            error_msg = str(e).lower()
            if "locked" in error_msg or "database is locked" in error_msg:
                raise ZoteroDatabaseLockedError(
                    str(self._db_path),
                    hint="Database is locked by another process. "
                    "Ensure Zotero is not performing intensive operations. "
                    "Wait a moment and try again.",
                ) from e
            elif "no such file" in error_msg or "cannot open" in error_msg:
                raise ZoteroDatabaseNotFoundError(
                    str(self._db_path),
                    hint="Database file not found. Ensure Zotero is installed and has been run.",
                ) from e
            else:
                raise ZoteroDatabaseNotFoundError(
                    str(self._db_path),
                    hint=f"Failed to open database: {e}",
                ) from e
        except Exception as e:
            raise ZoteroDatabaseNotFoundError(
                str(self._db_path),
                hint=f"Unexpected error opening database: {e}",
            ) from e
    
    def list_collections(self) -> list[dict[str, Any]]:
        """
        List all collections in Zotero library with hierarchy and item counts.
        
        Returns:
            List of collections with keys:
            - 'key': Collection key (collectionID as string)
            - 'name': Collection name
            - 'parentCollection': Parent collection key (None for top-level)
            - 'item_count': Number of items in collection
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                c.collectionID,
                c.collectionName,
                c.parentCollectionID,
                (SELECT COUNT(*) FROM collectionItems ci WHERE ci.collectionID = c.collectionID) as item_count
            FROM collections c
            ORDER BY c.collectionName;
        """
        
        try:
            cursor = self._conn.execute(query)
            collections = []
            for row in cursor:
                collections.append({
                    "key": str(row["collectionID"]),
                    "name": row["collectionName"],
                    "parentCollection": str(row["parentCollectionID"]) if row["parentCollectionID"] else None,
                    "item_count": row["item_count"],
                })
            return collections
        except sqlite3.Error as e:
            logger.error(f"Failed to list collections: {e}")
            raise
    
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Get items in a collection (generator to avoid loading all into memory).
        
        Args:
            collection_key: Zotero collection key (collectionID as string)
            include_subcollections: If True, recursively include items from subcollections
        
        Yields:
            Zotero items with keys: 'key', 'title', 'itemType', 'creators', 'date', 'tags'
            (formatted to match Web API adapter structure where possible)
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        try:
            collection_id = int(collection_key)
        except ValueError:
            raise ValueError(f"Invalid collection key: {collection_key}")
        
        if include_subcollections:
            # Use recursive CTE to get all subcollections
            query = """
                WITH RECURSIVE subcollections(collectionID) AS (
                    SELECT ? AS collectionID
                    UNION ALL
                    SELECT c.collectionID 
                    FROM collections c
                    JOIN subcollections sc ON c.parentCollectionID = sc.collectionID
                )
                SELECT DISTINCT
                    i.itemID,
                    i.key,
                    i.data
                FROM items i
                JOIN collectionItems ci ON i.itemID = ci.itemID
                JOIN subcollections sc ON ci.collectionID = sc.collectionID
                WHERE json_extract(i.data, '$.itemType') != 'attachment'
                  AND json_extract(i.data, '$.itemType') != 'annotation';
            """
        else:
            query = """
                SELECT DISTINCT
                    i.itemID,
                    i.key,
                    i.data
                FROM items i
                JOIN collectionItems ci ON i.itemID = ci.itemID
                WHERE ci.collectionID = ?
                  AND json_extract(i.data, '$.itemType') != 'attachment'
                  AND json_extract(i.data, '$.itemType') != 'annotation';
            """
        
        try:
            cursor = self._conn.execute(query, (collection_id,))
            for row in cursor:
                # Parse JSON data field
                data_str = row["data"]
                if isinstance(data_str, str):
                    try:
                        item_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON for item {row['key']}")
                        item_data = {}
                else:
                    item_data = data_str if isinstance(data_str, dict) else {}
                
                yield {
                    "key": row["key"],
                    "data": item_data,  # Match Web API format
                }
        except sqlite3.Error as e:
            logger.error(f"Failed to get collection items: {e}")
            raise
    
    def get_item_attachments(self, item_key: str) -> list[dict[str, Any]]:
        """
        Get PDF attachments for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            List of attachments with keys:
            - 'key': Attachment key
            - 'filename': Filename
            - 'contentType': MIME type
            - 'linkMode': 0 (imported) or 1 (linked)
            - 'data': Dict with attachment metadata
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                ia.itemID,
                ia.key as attachment_key,
                ia.data,
                (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key
            FROM itemAttachments ia
            JOIN items i ON ia.parentItemID = i.itemID
            WHERE i.key = ?
            AND json_extract(ia.data, '$.contentType') = 'application/pdf';
        """
        
        try:
            cursor = self._conn.execute(query, (item_key,))
            attachments = []
            for row in cursor:
                # Parse JSON data field
                data_str = row["data"]
                if isinstance(data_str, str):
                    try:
                        attachment_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON for attachment {row['attachment_key']}")
                        attachment_data = {}
                else:
                    attachment_data = data_str if isinstance(data_str, dict) else {}
                
                attachments.append({
                    "key": row["attachment_key"],
                    "filename": attachment_data.get("filename", ""),
                    "contentType": attachment_data.get("contentType", "application/pdf"),
                    "linkMode": attachment_data.get("linkMode", 0),
                    "data": attachment_data,
                })
            return attachments
        except sqlite3.Error as e:
            logger.error(f"Failed to get item attachments: {e}")
            raise
    
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> Path:
        """
        Download (copy) a file attachment from local Zotero storage.
        
        Args:
            item_key: Zotero item key (not used for local files, but required by interface)
            attachment_key: Zotero attachment key
            output_path: Local path where file should be saved
        
        Returns:
            Path to copied file
        
        Raises:
            ZoteroPathResolutionError: If attachment path cannot be resolved
            FileNotFoundError: If source file doesn't exist
        """
        # Resolve attachment path first
        source_path = self.resolve_attachment_path(attachment_key)
        
        if not source_path.exists():
            raise ZoteroPathResolutionError(
                attachment_key,
                hint=f"Source file not found at: {source_path}",
            )
        
        try:
            import shutil
            shutil.copy2(source_path, output_path)
            logger.info(
                f"Copied attachment {attachment_key} to {output_path}",
                extra={"attachment_key": attachment_key, "output_path": str(output_path)},
            )
            return output_path
        except Exception as e:
            raise ZoteroPathResolutionError(
                attachment_key,
                hint=f"Failed to copy file: {e}",
            ) from e
    
    def resolve_attachment_path(self, attachment_key: str) -> Path:
        """
        Resolve attachment path from database.
        
        Distinguishes imported (linkMode=0) vs linked (linkMode=1) files.
        
        Args:
            attachment_key: Zotero attachment key
        
        Returns:
            Path to attachment file
        
        Raises:
            ZoteroPathResolutionError: If path cannot be resolved
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                ia.data,
                json_extract(ia.data, '$.linkMode') as linkMode,
                json_extract(ia.data, '$.path') as path,
                (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key
            FROM itemAttachments ia
            WHERE ia.key = ?;
        """
        
        try:
            cursor = self._conn.execute(query, (attachment_key,))
            row = cursor.fetchone()
            
            if row is None:
                raise ZoteroPathResolutionError(
                    attachment_key,
                    hint="Attachment not found in database",
                )
            
            link_mode = row["linkMode"]
            db_path = row["path"]
            parent_item_key = row["parent_item_key"]
            
            # Parse data to get filename
            data_str = row["data"]
            if isinstance(data_str, str):
                try:
                    attachment_data = json.loads(data_str)
                except json.JSONDecodeError:
                    attachment_data = {}
            else:
                attachment_data = data_str if isinstance(data_str, dict) else {}
            
            filename = attachment_data.get("filename", "")
            
            if link_mode == 0:  # Imported file
                # Imported files are in storage directory: storage/{attachment_key}/{filename}
                if self._storage_dir is None:
                    # Try to detect storage directory
                    if self._db_path:
                        profile_dir = self._db_path.parent
                        storage_base = profile_dir.parent.parent
                        storage_path = storage_base / "storage"
                        if storage_path.exists():
                            self._storage_dir = storage_path
                        else:
                            raise ZoteroPathResolutionError(
                                attachment_key,
                                link_mode=0,
                                hint="Storage directory not found and cannot be auto-detected",
                            )
                
                # Zotero storage pattern: storage/{attachment_key}/{filename}
                file_path = self._storage_dir / attachment_key / filename
                if not file_path.exists():
                    # Try alternative: storage/{parent_item_key}/{filename}
                    if parent_item_key:
                        alt_path = self._storage_dir / parent_item_key / filename
                        if alt_path.exists():
                            return alt_path
                    raise ZoteroPathResolutionError(
                        attachment_key,
                        link_mode=0,
                        hint=f"File not found at: {file_path}",
                    )
                return file_path
            elif link_mode == 1:  # Linked file
                # Linked files use absolute path from database
                if db_path:
                    linked_path = Path(db_path)
                    if linked_path.exists():
                        return linked_path
                    raise ZoteroPathResolutionError(
                        attachment_key,
                        link_mode=1,
                        hint=f"Linked file not found at: {db_path}",
                    )
                else:
                    raise ZoteroPathResolutionError(
                        attachment_key,
                        link_mode=1,
                        hint="Linked file path is empty in database",
                    )
            else:
                raise ZoteroPathResolutionError(
                    attachment_key,
                    link_mode=link_mode,
                    hint=f"Unknown link mode: {link_mode}",
                )
        except sqlite3.Error as e:
            raise ZoteroPathResolutionError(
                attachment_key,
                hint=f"Database error resolving path: {e}",
            ) from e
    
    def get_item_metadata(self, item_key: str) -> dict[str, Any]:
        """
        Get full metadata for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            Item metadata dict with keys: title, creators (authors), date (year), DOI, tags, collections
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                i.data,
                i.key
            FROM items i
            WHERE i.key = ?
            AND json_extract(i.data, '$.itemType') != 'attachment'
            AND json_extract(i.data, '$.itemType') != 'annotation';
        """
        
        try:
            cursor = self._conn.execute(query, (item_key,))
            row = cursor.fetchone()
            
            if row is None:
                return {}
            
            # Parse JSON data field
            data_str = row["data"]
            if isinstance(data_str, str):
                try:
                    item_data = json.loads(data_str)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON for item {item_key}")
                    return {}
            else:
                item_data = data_str if isinstance(data_str, dict) else {}
            
            # Extract metadata in format matching Web API
            # Extract additional metadata fields (same as Web API)
            publication_title = (
                item_data.get("publicationTitle") or
                item_data.get("journalAbbreviation") or
                item_data.get("publication") or
                item_data.get("bookTitle") or
                None
            )
            
            metadata = {
                "title": item_data.get("title", ""),
                "creators": item_data.get("creators", []),
                "date": item_data.get("date", ""),
                "year": self._extract_year(item_data.get("date", "")),
                "DOI": item_data.get("DOI", ""),
                "tags": [tag.get("tag", "") for tag in item_data.get("tags", [])],
                "collections": [],  # Would need additional query to get collections
                "publicationTitle": publication_title,
                "volume": item_data.get("volume"),
                "issue": item_data.get("issue"),
                "pages": item_data.get("pages"),
                "url": item_data.get("url") or item_data.get("URL"),
                "language": item_data.get("language"),
                "itemType": item_data.get("itemType", ""),
            }
            
            return metadata
        except sqlite3.Error as e:
            logger.error(f"Failed to get item metadata: {e}")
            raise
    
    @staticmethod
    def _extract_year(date_str: str) -> int | None:
        """Extract year from date string."""
        if not date_str:
            return None
        try:
            # Try to extract 4-digit year
            import re
            match = re.search(r'\d{4}', date_str)
            if match:
                return int(match.group())
        except (ValueError, AttributeError):
            pass
        return None
    
    def list_tags(self) -> list[dict[str, Any]]:
        """
        List all tags used in Zotero library with usage counts.
        
        Returns:
            List of tags with keys:
            - 'tag': Tag name
            - 'count': Number of items with this tag (for local DB)
            - 'meta': Dict with numItems count (matching Web API format)
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                t.name as tag,
                COUNT(DISTINCT it.itemID) as count
            FROM tags t
            JOIN itemTags it ON t.tagID = it.tagID
            GROUP BY t.name
            ORDER BY count DESC, t.name;
        """
        
        try:
            cursor = self._conn.execute(query)
            tags = []
            for row in cursor:
                tags.append({
                    "tag": row["tag"],
                    "count": row["count"],
                    "meta": {"numItems": row["count"]},  # Match Web API format
                })
            return tags
        except sqlite3.Error as e:
            logger.error(f"Failed to list tags: {e}")
            raise
    
    def get_recent_items(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recently added items to Zotero library.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of items sorted by dateAdded (descending)
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                i.itemID,
                i.key,
                i.data
            FROM items i
            WHERE json_extract(i.data, '$.itemType') != 'attachment'
              AND json_extract(i.data, '$.itemType') != 'annotation'
            ORDER BY json_extract(i.data, '$.dateAdded') DESC
            LIMIT ?;
        """
        
        try:
            cursor = self._conn.execute(query, (limit,))
            items = []
            for row in cursor:
                # Parse JSON data field
                data_str = row["data"]
                if isinstance(data_str, str):
                    try:
                        item_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON for item {row['key']}")
                        item_data = {}
                else:
                    item_data = data_str if isinstance(data_str, dict) else {}
                
                items.append({
                    "key": row["key"],
                    "data": item_data,
                })
            return items
        except sqlite3.Error as e:
            logger.error(f"Failed to get recent items: {e}")
            raise
    
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
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                c.collectionID,
                c.collectionName,
                c.parentCollectionID,
                (SELECT COUNT(*) FROM collectionItems ci WHERE ci.collectionID = c.collectionID) as item_count
            FROM collections c
            WHERE LOWER(c.collectionName) LIKE LOWER(?)
            LIMIT 1;
        """
        
        try:
            cursor = self._conn.execute(query, (f"%{collection_name}%",))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return {
                "key": str(row["collectionID"]),
                "name": row["collectionName"],
                "parentCollection": str(row["parentCollectionID"]) if row["parentCollectionID"] else None,
                "item_count": row["item_count"],
            }
        except sqlite3.Error as e:
            logger.error(f"Failed to find collection by name: {e}")
            raise
    
    def can_resolve_locally(self, attachment_key: str) -> bool:
        """
        Check if attachment can be resolved locally (for source routing).
        
        Args:
            attachment_key: Zotero attachment key
        
        Returns:
            True if attachment can be resolved locally, False otherwise
        """
        try:
            path = self.resolve_attachment_path(attachment_key)
            return path.exists()
        except (ZoteroPathResolutionError, ZoteroDatabaseNotFoundError):
            return False
    
    def __del__(self) -> None:
        """Close database connection on cleanup."""
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass  # Ignore errors during cleanup
    
    def close(self) -> None:
        """Explicitly close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

