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
                # Provide detailed guidance for Windows users
                system = platform.system()
                if system == "Windows":
                    hint = (
                        "Zotero profile directory not found. Please check:\n"
                        "1. Zotero is installed and has been run at least once\n"
                        "2. Profile location is one of:\n"
                        "   - %APPDATA%\\Zotero\\Profiles\\{profile_id}\\zotero.sqlite\n"
                        "   - %LOCALAPPDATA%\\Zotero\\Profiles\\{profile_id}\\zotero.sqlite\n"
                        "   - %USERPROFILE%\\Documents\\Zotero\\Profiles\\{profile_id}\\zotero.sqlite\n"
                        "3. To manually configure, set 'db_path' in citeloom.toml:\n"
                        "   [zotero]\n"
                        "   db_path = \"C:\\Users\\YourName\\AppData\\Roaming\\Zotero\\Profiles\\xxxxx.default\\zotero.sqlite\"\n"
                        "   storage_dir = \"C:\\Users\\YourName\\AppData\\Roaming\\Zotero\\Profiles\\xxxxx.default\\zotero\\storage\"\n"
                        "See docs/zotero-local-access.md for more details."
                    )
                else:
                    hint = (
                        "Zotero profile directory not found. Ensure Zotero is installed and has been run at least once. "
                        "Or provide db_path explicitly via configuration. "
                        "See docs/zotero-local-access.md for more details."
                    )
                raise ZoteroProfileNotFoundError(
                    "Zotero profile directory",
                    hint=hint,
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
            hint = (
                f"Database file not found at: {self._db_path}\n"
                "Ensure:\n"
                "1. Zotero is installed and has been run at least once\n"
                "2. The database path is correct\n"
                "3. Zotero is not currently performing intensive operations\n"
                "To manually configure, set 'db_path' in citeloom.toml. "
                "See docs/zotero-local-access.md for configuration examples."
            )
            raise ZoteroDatabaseNotFoundError(
                str(self._db_path),
                hint=hint,
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
        - Windows: Checks multiple common paths:
            1. %APPDATA%\\Zotero\\Profiles\\{profile_id}\\
            2. %LOCALAPPDATA%\\Zotero\\Profiles\\{profile_id}\\
            3. %USERPROFILE%\\Documents\\Zotero\\Profiles\\{profile_id}\\
        - macOS: ~/Library/Application Support/Zotero/Profiles/{profile_id}/
        - Linux: ~/.zotero/zotero/Profiles/{profile_id}/
        """
        system = platform.system()
        
        if system == "Windows":
            # Check multiple Windows paths in order of preference
            windows_paths = [
                ("APPDATA", os.environ.get("APPDATA", "")),
                ("LOCALAPPDATA", os.environ.get("LOCALAPPDATA", "")),
                ("USERPROFILE", os.path.join(os.environ.get("USERPROFILE", ""), "Documents")),
            ]
            
            for env_name, base_path in windows_paths:
                if not base_path:
                    continue
                
                base = Path(base_path) / "Zotero"
                profiles_ini = base / "Profiles" / "profiles.ini"
                
                if profiles_ini.exists():
                    # Parse profiles.ini to find default profile
                    profile_path = LocalZoteroDbAdapter._parse_profiles_ini(profiles_ini, base)
                    if profile_path is not None:
                        return profile_path
            
            # If no profile found in any Windows path, return None
            return None
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
    
    def _check_schema_has_data_column(self) -> bool:
        """
        Check if items table has a 'data' column (Zotero 5+ schema).
        
        Returns:
            True if items.data column exists, False otherwise
        """
        if self._conn is None:
            return False
        
        try:
            cursor = self._conn.execute("PRAGMA table_info(items)")
            columns = [row[1] for row in cursor.fetchall()]
            return "data" in columns
        except sqlite3.Error:
            return False
    
    def _check_schema_needs_migration(self) -> tuple[bool, str]:
        """
        Check if database needs migration from old schema to new schema.
        
        Returns:
            Tuple of (needs_migration, message)
            - needs_migration: True if database appears to need migration
            - message: Description of the migration status
        """
        if self._conn is None:
            return (False, "Database not connected")
        
        try:
            # Check for Zotero version in settings
            cursor = self._conn.execute("SELECT value FROM settings WHERE key = 'lastVersion'")
            row = cursor.fetchone()
            zotero_version = row["value"] if row else None
            
            # Check if items.data column exists
            has_data_column = self._check_schema_has_data_column()
            
            # Check if itemData table exists (old schema)
            cursor = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='itemData'"
            )
            has_item_data_table = cursor.fetchone() is not None
            
            # If Zotero 7+ is installed but database hasn't migrated
            if zotero_version and zotero_version.startswith("7.") and not has_data_column and has_item_data_table:
                return (
                    True,
                    f"Zotero {zotero_version} is installed, but database hasn't been migrated to new schema. "
                    "Please open Zotero desktop application once to trigger database migration. "
                    "The migration happens automatically when Zotero starts. "
                    "Note: Old schema support is enabled as fallback."
                )
            
            if not has_data_column and has_item_data_table:
                return (
                    True,
                    "Database uses old schema (itemData table). "
                    "Please upgrade Zotero to version 5.0+ and open it to trigger database migration. "
                    "Note: Old schema support is enabled as fallback."
                )
            
            return (False, "Schema is up to date")
        except sqlite3.Error:
            return (False, "Could not check migration status")
    
    def _check_has_item_data_table(self) -> bool:
        """
        Check if itemData table exists (old schema).
        
        Returns:
            True if itemData table exists, False otherwise
        """
        if self._conn is None:
            return False
        
        try:
            cursor = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='itemData'"
            )
            return cursor.fetchone() is not None
        except sqlite3.Error:
            return False
    
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
        
        # Check if schema has items.data column (Zotero 5+)
        has_data_column = self._check_schema_has_data_column()
        
        if not has_data_column:
            # Older Zotero schema - items.data column doesn't exist
            # Use old schema fallback (itemData table) if available
            if self._check_has_item_data_table():
                # Check if migration is needed
                needs_migration, migration_msg = self._check_schema_needs_migration()
                if needs_migration:
                    logger.info(
                        f"Using old schema fallback: {migration_msg.split('.')[0]}. "
                        "Reading items from itemData table."
                    )
                else:
                    logger.info(
                        "Using old schema fallback: Reading items from itemData table. "
                        "Consider upgrading Zotero for better performance."
                    )
                # Fall through to old schema implementation
                yield from self._get_collection_items_old_schema(collection_id, include_subcollections)
                return
            else:
                # No old schema either - cannot proceed
                needs_migration, migration_msg = self._check_schema_needs_migration()
                if needs_migration:
                    logger.warning(
                        f"Database migration needed: {migration_msg}",
                        extra={"migration_needed": True, "migration_message": migration_msg},
                    )
                else:
                    logger.warning(
                        "Zotero database schema appears to be from an older version (< 5.0). "
                        "The items.data column is not available. "
                        "Please upgrade Zotero or use web API access instead."
                    )
                return
        
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
                    items.itemID,
                    items.key,
                    items.data
                FROM items
                JOIN collectionItems ci ON items.itemID = ci.itemID
                JOIN subcollections sc ON ci.collectionID = sc.collectionID
                WHERE json_extract(items.data, '$.itemType') != 'attachment'
                  AND json_extract(items.data, '$.itemType') != 'annotation';
            """
        else:
            query = """
                SELECT DISTINCT
                    items.itemID,
                    items.key,
                    items.data
                FROM items
                JOIN collectionItems ci ON items.itemID = ci.itemID
                WHERE ci.collectionID = ?
                  AND json_extract(items.data, '$.itemType') != 'attachment'
                  AND json_extract(items.data, '$.itemType') != 'annotation';
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
    
    def _get_collection_items_old_schema(
        self,
        collection_id: int,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Get items from collection using old schema (itemData table).
        
        Based on zotero-mcp implementation: https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py
        
        Args:
            collection_id: Collection ID
            include_subcollections: If True, recursively include items from subcollections
        
        Yields:
            Zotero items with keys: 'key', 'data' (formatted to match Web API format)
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        # Query using old schema (itemData table)
        # Based on zotero-mcp implementation: https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py
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
                    i.itemTypeID,
                    it.typeName as item_type,
                    title_val.value as title,
                    date_val.value as date,
                    doi_val.value as doi
                FROM items i
                JOIN collectionItems ci ON i.itemID = ci.itemID
                JOIN subcollections sc ON ci.collectionID = sc.collectionID
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                -- Get title (fieldID = 1)
                LEFT JOIN itemData title_data ON i.itemID = title_data.itemID AND title_data.fieldID = 1
                LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
                -- Get date (fieldID = 14)
                LEFT JOIN itemData date_data ON i.itemID = date_data.itemID AND date_data.fieldID = 14
                LEFT JOIN itemDataValues date_val ON date_data.valueID = date_val.valueID
                -- Get DOI
                LEFT JOIN fields doi_f ON doi_f.fieldName = 'DOI'
                LEFT JOIN itemData doi_data ON i.itemID = doi_data.itemID AND doi_data.fieldID = doi_f.fieldID
                LEFT JOIN itemDataValues doi_val ON doi_data.valueID = doi_val.valueID
                WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
            """
        else:
            query = """
                SELECT DISTINCT
                    i.itemID,
                    i.key,
                    i.itemTypeID,
                    it.typeName as item_type,
                    title_val.value as title,
                    date_val.value as date,
                    doi_val.value as doi
                FROM items i
                JOIN collectionItems ci ON i.itemID = ci.itemID
                JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
                -- Get title (fieldID = 1)
                LEFT JOIN itemData title_data ON i.itemID = title_data.itemID AND title_data.fieldID = 1
                LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
                -- Get date (fieldID = 14)
                LEFT JOIN itemData date_data ON i.itemID = date_data.itemID AND date_data.fieldID = 14
                LEFT JOIN itemDataValues date_val ON date_data.valueID = date_val.valueID
                -- Get DOI
                LEFT JOIN fields doi_f ON doi_f.fieldName = 'DOI'
                LEFT JOIN itemData doi_data ON i.itemID = doi_data.itemID AND doi_data.fieldID = doi_f.fieldID
                LEFT JOIN itemDataValues doi_val ON doi_data.valueID = doi_val.valueID
                WHERE ci.collectionID = ?
                  AND it.typeName NOT IN ('attachment', 'note', 'annotation')
            """
        
        try:
            cursor = self._conn.execute(query, (collection_id,))
            for row in cursor:
                # Build item data dict matching Web API format
                item_data: dict[str, Any] = {
                    "key": row["key"],
                    "itemType": row["item_type"] or "unknown",
                    "title": row["title"] or "",
                    "date": row["date"] or "",
                }
                
                # Add DOI if available
                if row["doi"]:
                    item_data["DOI"] = row["doi"]
                    item_data["doi"] = row["doi"]
                
                # Get creators (authors)
                # Try to get creators - handle both name and firstName/lastName formats
                creators_query = """
                    SELECT 
                        c.firstName,
                        c.lastName
                    FROM itemCreators ic
                    JOIN creators c ON ic.creatorID = c.creatorID
                    WHERE ic.itemID = ?
                    ORDER BY ic.orderIndex
                """
                try:
                    creators_cursor = self._conn.execute(creators_query, (row["itemID"],))
                    creators = []
                    for creator_row in creators_cursor:
                        first = creator_row["firstName"] or ""
                        last = creator_row["lastName"] or ""
                        if first or last:
                            creators.append({
                                "firstName": first,
                                "lastName": last,
                            })
                    if creators:
                        item_data["creators"] = creators
                except sqlite3.Error as e:
                    # If creators query fails, skip creators (non-critical)
                    logger.debug(f"Could not retrieve creators for item {row['key']}: {e}")
                
                # Get tags
                tags_query = """
                    SELECT t.name as tag
                    FROM itemTags it
                    JOIN tags t ON it.tagID = t.tagID
                    WHERE it.itemID = ?
                """
                tags_cursor = self._conn.execute(tags_query, (row["itemID"],))
                tags = []
                for tag_row in tags_cursor:
                    tags.append({"tag": tag_row["tag"]})
                if tags:
                    item_data["tags"] = tags
                
                yield {
                    "key": row["key"],
                    "data": item_data,
                }
        except sqlite3.Error as e:
            logger.error(f"Failed to get collection items from old schema: {e}")
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
        
        # Check if schema has items.data column (Zotero 5+)
        has_data_column = self._check_schema_has_data_column()
        
        if has_data_column:
            # New schema - use items.data column
            query = """
                SELECT 
                    ia.itemID,
                    att.key as attachment_key,
                    att.data,
                    (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key
                FROM itemAttachments ia
                JOIN items i ON ia.parentItemID = i.itemID
                JOIN items att ON ia.itemID = att.itemID
                WHERE i.key = ?
                AND json_extract(att.data, '$.contentType') = 'application/pdf';
            """
        else:
            # Old schema - use itemAttachments table directly
            query = """
                SELECT 
                    ia.itemID,
                    att.key as attachment_key,
                    (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key,
                    ia.contentType,
                    ia.path
                FROM itemAttachments ia
                JOIN items i ON ia.parentItemID = i.itemID
                JOIN items att ON ia.itemID = att.itemID
                WHERE i.key = ?
                AND (ia.contentType = 'application/pdf' OR ia.contentType LIKE '%pdf%');
            """
        
        try:
            cursor = self._conn.execute(query, (item_key,))
            attachments = []
            for row in cursor:
                if has_data_column:
                    # New schema - parse JSON data field
                    data_str = row["data"] if "data" in row.keys() else None
                    attachment_key = row["attachment_key"] if "attachment_key" in row.keys() else None
                    
                    if isinstance(data_str, str):
                        try:
                            attachment_data = json.loads(data_str)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON for attachment {attachment_key}")
                            attachment_data = {}
                    else:
                        attachment_data = data_str if isinstance(data_str, dict) else {}
                    
                    attachments.append({
                        "key": attachment_key or "",
                        "filename": attachment_data.get("filename", "") if attachment_data else "",
                        "contentType": attachment_data.get("contentType", "application/pdf") if attachment_data else "application/pdf",
                        "linkMode": attachment_data.get("linkMode", 0) if attachment_data else 0,
                        "data": attachment_data,
                    })
                else:
                    # Old schema - use direct columns
                    path_val = row["path"] if "path" in row.keys() else ""
                    content_type = row["contentType"] if "contentType" in row.keys() else "application/pdf"
                    attachment_key = row["attachment_key"] if "attachment_key" in row.keys() else ""
                    
                    attachments.append({
                        "key": attachment_key,
                        "filename": Path(path_val).name if path_val else "",
                        "contentType": content_type,
                        "linkMode": 0,  # Default to imported
                        "data": {
                            "filename": Path(path_val).name if path_val else "",
                            "contentType": content_type,
                            "linkMode": 0,
                        },
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
        
        # Check schema version
        has_data_column = self._check_schema_has_data_column()
        
        if has_data_column:
            query = """
                SELECT 
                    ia.data,
                    json_extract(ia.data, '$.linkMode') as linkMode,
                    json_extract(ia.data, '$.path') as path,
                    (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key
                FROM itemAttachments ia
                WHERE ia.key = ?;
            """
        else:
            # Old schema - use direct columns
            # In old schema, itemAttachments doesn't have 'key' column, need to join with items table
            query = """
                SELECT 
                    ia.linkMode,
                    ia.path,
                    (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key
                FROM itemAttachments ia
                JOIN items i ON ia.itemID = i.itemID
                WHERE i.key = ?;
            """
        
        try:
            cursor = self._conn.execute(query, (attachment_key,))
            row = cursor.fetchone()
            
            if row is None:
                raise ZoteroPathResolutionError(
                    attachment_key,
                    hint="Attachment not found in database",
                )
            
            link_mode = row["linkMode"] if "linkMode" in row.keys() else 0
            db_path = row["path"] if "path" in row.keys() else None
            parent_item_key = row["parent_item_key"] if "parent_item_key" in row.keys() else None
            
            # Parse data to get filename
            if has_data_column:
                data_str = row["data"] if "data" in row.keys() else None
                if isinstance(data_str, str):
                    try:
                        attachment_data = json.loads(data_str)
                    except json.JSONDecodeError:
                        attachment_data = {}
                else:
                    attachment_data = data_str if isinstance(data_str, dict) else {}
                
                filename = attachment_data.get("filename", "")
            else:
                # Old schema - filename is in path
                # Remove "storage:" prefix if present (old schema artifact)
                if db_path:
                    path_str = str(db_path)
                    if path_str.startswith("storage:"):
                        path_str = path_str[8:]  # Remove "storage:" prefix
                    filename = Path(path_str).name
                else:
                    filename = ""
                attachment_data = {}
            
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
                    
                    # Suggest filename variations
                    suggestions = []
                    if filename:
                        # Try common variations
                        base_name = Path(filename).stem
                        ext = Path(filename).suffix
                        variations = [
                            f"{base_name}{ext}",
                            f"{base_name.lower()}{ext}",
                            f"{base_name.upper()}{ext}",
                            filename.replace(" ", "_"),
                            filename.replace("_", " "),
                        ]
                        
                        # Check if any variations exist
                        for variation in variations:
                            var_path = self._storage_dir / attachment_key / variation
                            if var_path.exists():
                                suggestions.append(f"  - Found: {var_path}")
                            # Also check parent_item_key location
                            if parent_item_key:
                                var_path = self._storage_dir / parent_item_key / variation
                                if var_path.exists():
                                    suggestions.append(f"  - Found: {var_path}")
                    
                    hint_msg = f"File not found at: {file_path}"
                    if suggestions:
                        hint_msg += f"\nSimilar filenames found:\n" + "\n".join(suggestions)
                    hint_msg += f"\nChecked locations:\n  - {file_path}"
                    if parent_item_key:
                        hint_msg += f"\n  - {self._storage_dir / parent_item_key / filename}"
                    hint_msg += f"\nIf file exists with different name, check Zotero storage directory manually."
                    
                    raise ZoteroPathResolutionError(
                        attachment_key,
                        link_mode=0,
                        hint=hint_msg,
                    )
                return file_path
            elif link_mode == 1:  # Linked file
                # Linked files use absolute path from database
                if db_path:
                    linked_path = Path(db_path)
                    if linked_path.exists():
                        return linked_path
                    # Suggest filename variations for linked files
                    hint_msg = f"Linked file not found at: {db_path}"
                    if db_path:
                        db_path_obj = Path(db_path)
                        if db_path_obj.parent.exists():
                            # Check if similar filenames exist in the same directory
                            parent_dir = db_path_obj.parent
                            filename = db_path_obj.name
                            if filename:
                                base_name = db_path_obj.stem
                                ext = db_path_obj.suffix
                                variations = [
                                    f"{base_name}{ext}",
                                    f"{base_name.lower()}{ext}",
                                    f"{base_name.upper()}{ext}",
                                    filename.replace(" ", "_"),
                                    filename.replace("_", " "),
                                ]
                                
                                suggestions = []
                                for variation in variations:
                                    var_path = parent_dir / variation
                                    if var_path.exists():
                                        suggestions.append(f"  - Found: {var_path}")
                                
                                if suggestions:
                                    hint_msg += f"\nSimilar filenames found:\n" + "\n".join(suggestions)
                                hint_msg += f"\nVerify the file path in Zotero or check if the file was moved."
                    
                    raise ZoteroPathResolutionError(
                        attachment_key,
                        link_mode=1,
                        hint=hint_msg,
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
        
        # Check if schema has items.data column
        has_data_column = self._check_schema_has_data_column()
        if not has_data_column:
            # Use old schema fallback if available
            if self._check_has_item_data_table():
                return self._get_item_metadata_old_schema(item_key)
            else:
                # No old schema either - cannot proceed
                needs_migration, migration_msg = self._check_schema_needs_migration()
                if needs_migration:
                    logger.warning(
                        f"Cannot retrieve item metadata: {migration_msg}",
                        extra={"migration_needed": True, "migration_message": migration_msg},
                    )
                else:
                    logger.warning(
                        "Zotero database schema appears to be from an older version (< 5.0). "
                        "Cannot retrieve item metadata from local database. "
                        "Please upgrade Zotero or use web API access instead."
                    )
                return {}
        
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
        
        # Check if schema has items.data column (Zotero 5+)
        has_data_column = self._check_schema_has_data_column()
        
        if not has_data_column:
            # Older Zotero schema - items.data column doesn't exist
            # Use old schema fallback if available
            if self._check_has_item_data_table():
                # Use old schema to get recent items
                return self._get_recent_items_old_schema(limit)
            else:
                # No old schema either - cannot proceed
                needs_migration, migration_msg = self._check_schema_needs_migration()
                if needs_migration:
                    logger.warning(
                        f"Cannot retrieve recent items: {migration_msg}",
                        extra={"migration_needed": True, "migration_message": migration_msg},
                    )
                else:
                    logger.warning(
                        "Zotero database schema appears to be from an older version (< 5.0). "
                        "The items.data column is not available. "
                        "Please upgrade Zotero or use web API access instead."
                    )
                return []  # Return empty list for older schema
        
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
    
    def _get_recent_items_old_schema(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent items using old schema (itemData table).
        
        Based on zotero-mcp implementation: https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py
        
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
                i.itemTypeID,
                it.typeName as item_type,
                i.dateAdded,
                title_val.value as title,
                date_val.value as date
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            -- Get title (fieldID = 1)
            LEFT JOIN itemData title_data ON i.itemID = title_data.itemID AND title_data.fieldID = 1
            LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
            -- Get date (fieldID = 14)
            LEFT JOIN itemData date_data ON i.itemID = date_data.itemID AND date_data.fieldID = 14
            LEFT JOIN itemDataValues date_val ON date_data.valueID = date_val.valueID
            WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
            ORDER BY i.dateAdded DESC
            LIMIT ?;
        """
        
        try:
            cursor = self._conn.execute(query, (limit,))
            items = []
            for row in cursor:
                item_data: dict[str, Any] = {
                    "key": row["key"],
                    "itemType": row["item_type"] or "unknown",
                    "title": row["title"] or "",
                    "date": row["date"] or "",
                    "dateAdded": row["dateAdded"] or "",
                }
                
                items.append({
                    "key": row["key"],
                    "data": item_data,
                })
            return items
        except sqlite3.Error as e:
            logger.error(f"Failed to get recent items from old schema: {e}")
            raise
    
    def _get_item_metadata_old_schema(self, item_key: str) -> dict[str, Any]:
        """
        Get item metadata using old schema (itemData table).
        
        Based on zotero-mcp implementation: https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py
        
        Args:
            item_key: Zotero item key
        
        Returns:
            Item metadata dict with keys: title, creators (authors), date (year), DOI, tags
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        query = """
            SELECT 
                i.itemID,
                i.key,
                i.itemTypeID,
                it.typeName as item_type,
                title_val.value as title,
                date_val.value as date,
                doi_val.value as doi
            FROM items i
            JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
            -- Get title (fieldID = 1)
            LEFT JOIN itemData title_data ON i.itemID = title_data.itemID AND title_data.fieldID = 1
            LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
            -- Get date (fieldID = 14)
            LEFT JOIN itemData date_data ON i.itemID = date_data.itemID AND date_data.fieldID = 14
            LEFT JOIN itemDataValues date_val ON date_data.valueID = date_val.valueID
            -- Get DOI
            LEFT JOIN fields doi_f ON doi_f.fieldName = 'DOI'
            LEFT JOIN itemData doi_data ON i.itemID = doi_data.itemID AND doi_data.fieldID = doi_f.fieldID
            LEFT JOIN itemDataValues doi_val ON doi_data.valueID = doi_val.valueID
            WHERE i.key = ?
              AND it.typeName NOT IN ('attachment', 'note', 'annotation');
        """
        
        try:
            cursor = self._conn.execute(query, (item_key,))
            row = cursor.fetchone()
            
            if row is None:
                return {}
            
            metadata: dict[str, Any] = {
                "title": row["title"] or "",
                "itemType": row["item_type"] or "unknown",
                "date": row["date"] or "",
            }
            
            # Add DOI if available
            if row["doi"]:
                metadata["DOI"] = row["doi"]
                metadata["doi"] = row["doi"]
            
            # Get creators
            creators_query = """
                SELECT 
                    c.firstName,
                    c.lastName
                FROM itemCreators ic
                JOIN creators c ON ic.creatorID = c.creatorID
                WHERE ic.itemID = ?
                ORDER BY ic.orderIndex
            """
            creators_cursor = self._conn.execute(creators_query, (row["itemID"],))
            creators = []
            for creator_row in creators_cursor:
                first = creator_row["firstName"] or ""
                last = creator_row["lastName"] or ""
                if first or last:
                    creators.append({
                        "firstName": first,
                        "lastName": last,
                    })
            if creators:
                metadata["creators"] = creators
            
            # Extract year from date
            if row["date"]:
                try:
                    year_str = str(row["date"]).split("-")[0]
                    year = int(year_str)
                    metadata["year"] = year
                except (ValueError, IndexError):
                    pass
            
            # Get tags
            tags_query = """
                SELECT t.name as tag
                FROM itemTags it
                JOIN tags t ON it.tagID = t.tagID
                WHERE it.itemID = ?
            """
            tags_cursor = self._conn.execute(tags_query, (row["itemID"],))
            tags = []
            for tag_row in tags_cursor:
                tags.append(tag_row["tag"])
            if tags:
                metadata["tags"] = tags
            
            return metadata
        except sqlite3.Error as e:
            logger.error(f"Failed to get item metadata from old schema: {e}")
            return {}
    
    def get_collection_info(
        self,
        collection_name_or_key: str,
        collection_cache: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Get collection information with optional command-scoped cache.
        
        Args:
            collection_name_or_key: Collection name or key identifier
            collection_cache: Optional command-scoped cache for collection metadata
                - Key: collection_key (str)
                - Value: collection metadata dict
        
        Returns:
            Collection information dict with keys: key, name, metadata
        """
        if self._conn is None:
            raise ZoteroDatabaseNotFoundError("Database not connected")
        
        # Check if it's a collection key (numeric string) or name
        try:
            collection_id = int(collection_name_or_key)
            # It's a key - check cache first
            collection_key = str(collection_id)
            if collection_cache and collection_key in collection_cache:
                cached = collection_cache[collection_key]
                return {
                    "key": cached.get("key", collection_key),
                    "name": cached.get("name", ""),
                    "metadata": cached,
                }
            
            # Fetch from database
            query = """
                SELECT 
                    c.collectionID,
                    c.collectionName,
                    c.parentCollectionID,
                    (SELECT COUNT(*) FROM collectionItems ci WHERE ci.collectionID = c.collectionID) as item_count
                FROM collections c
                WHERE c.collectionID = ?
                LIMIT 1;
            """
            cursor = self._conn.execute(query, (collection_id,))
            row = cursor.fetchone()
            
            if row is None:
                raise ValueError(f"Collection not found: {collection_name_or_key}")
            
            coll_data = {
                "key": str(row["collectionID"]),
                "name": row["collectionName"],
                "parentCollection": str(row["parentCollectionID"]) if row["parentCollectionID"] else None,
                "item_count": row["item_count"],
            }
            
            # Cache if cache provided
            if collection_cache is not None:
                collection_cache[collection_key] = coll_data
            
            return {
                "key": coll_data["key"],
                "name": coll_data["name"],
                "metadata": coll_data,
            }
        except ValueError:
            # Not a numeric key, treat as name
            found = self.find_collection_by_name(collection_name_or_key)
            if found:
                coll_key = found.get("key", "")
                if coll_key:
                    # Use get_collection_info recursively with key (will check cache)
                    return self.get_collection_info(coll_key, collection_cache=collection_cache)
            else:
                raise ValueError(f"Collection not found: {collection_name_or_key}")
    
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

