"""Adapter for importing documents from Zotero collections via pyzotero API."""

from __future__ import annotations

import logging
import random
import shutil
import time
from pathlib import Path
from typing import Any

from pyzotero import zotero

from ...application.ports.zotero_importer import ZoteroImporterPort
from ...domain.errors import ZoteroAPIError, ZoteroConnectionError, ZoteroRateLimitError
from ...infrastructure.config.environment import get_env, get_env_bool, load_environment_variables

logger = logging.getLogger(__name__)


class ZoteroImporterAdapter(ZoteroImporterPort):
    """
    Adapter for importing documents from Zotero collections.
    
    Implements ZoteroImporterPort using pyzotero library with rate limiting,
    retry logic with exponential backoff, and support for both local and remote API.
    """

    # Rate limiting: 0.5s minimum interval for web API, 2 requests per second max
    MIN_REQUEST_INTERVAL = 0.5  # seconds
    MAX_REQUESTS_PER_SECOND = 2

    def __init__(self, zotero_config: dict[str, Any] | None = None) -> None:
        """
        Initialize Zotero client with configuration.
        
        Args:
            zotero_config: Optional configuration dict with:
                - library_id: Zotero library ID
                - library_type: 'user' or 'group'
                - api_key: API key for remote access (required for remote)
                - local: True for local access (defaults to False, attempts local first if available)
        
        If None, uses environment variables:
            - ZOTERO_LIBRARY_ID
            - ZOTERO_LIBRARY_TYPE ('user' or 'group')
            - ZOTERO_API_KEY (for remote access)
            - ZOTERO_LOCAL (true/false for local access)
        """
        load_environment_variables()

        if zotero_config is None:
            zotero_config = {}

        # Get library_id from config or env
        library_id = zotero_config.get("library_id") or get_env("ZOTERO_LIBRARY_ID")

        # Get library_type from config or env (default 'user')
        library_type = zotero_config.get("library_type") or get_env("ZOTERO_LIBRARY_TYPE") or "user"

        # Check if local access is requested
        use_local = zotero_config.get("local", False) or get_env_bool("ZOTERO_LOCAL", False)

        if not library_id:
            raise ZoteroConnectionError(
                "Zotero library_id not configured. ZOTERO_LIBRARY_ID environment variable or library_id config required",
            )

        # Try local API first if available, fallback to remote
        self.local = False
        self.zot: zotero.Zotero | None = None

        if use_local:
            try:
                # Local access: Zotero must be running with local API enabled
                # library_id is typically '1' for user library in local mode
                self.zot = zotero.Zotero(library_id, library_type, api_key=None, local=True)
                self.local = True
                logger.info(
                    "Zotero client initialized for local access",
                    extra={"library_id": library_id, "library_type": library_type},
                )
            except Exception as e:
                logger.warning(
                    f"Local Zotero API unavailable, falling back to remote: {e}",
                    extra={"library_id": library_id, "library_type": library_type, "error": str(e)},
                )
                # Fall through to remote initialization

        if not self.local:
            # Remote access: requires API key
            api_key = zotero_config.get("api_key") or get_env("ZOTERO_API_KEY")
            if not api_key:
                raise ZoteroConnectionError(
                    "Zotero API key not configured for remote access. ZOTERO_API_KEY environment variable or api_key config required",
                )

            try:
                self.zot = zotero.Zotero(library_id, library_type, api_key)
                logger.info(
                    "Zotero client initialized for remote access",
                    extra={"library_id": library_id, "library_type": library_type},
                )
            except Exception as e:
                raise ZoteroConnectionError(
                    f"Failed to initialize Zotero client: {e}",
                ) from e

        # Rate limiting state
        self._last_request_time = 0.0
        
        # API call tracking for summary logging (T052a)
        self._api_call_count = 0
        self._api_call_start_time: float | None = None

    def _rate_limit(self) -> None:
        """Apply rate limiting for web API requests (0.5s minimum interval)."""
        # Track API call start time for summary logging (T052a)
        if self._api_call_start_time is None:
            self._api_call_start_time = time.time()
        
        # Increment API call counter (T052a)
        self._api_call_count += 1
        
        if self.local:
            return  # No rate limiting for local API

        current_time = time.time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.MIN_REQUEST_INTERVAL:
            sleep_time = self.MIN_REQUEST_INTERVAL - time_since_last
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _retry_with_backoff(
        self,
        func: Any,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
    ) -> Any:
        """
        Retry function with exponential backoff and jitter.
        
        Args:
            func: Function to retry (callable)
            max_retries: Maximum number of retries (default 3)
            base_delay: Base delay in seconds (default 1.0)
            max_delay: Maximum delay in seconds (default 30.0)
            jitter: Add random jitter to prevent thundering herd (default True)
        
        Returns:
            Function result
        
        Raises:
            ZoteroAPIError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_error = e

                if attempt < max_retries - 1:
                    # Exponential backoff: base_delay * 2^attempt
                    delay = min(base_delay * (2**attempt), max_delay)

                    # Add jitter (±25%)
                    if jitter:
                        jitter_amount = delay * 0.25 * (2 * random.random() - 1)
                        delay = max(0, delay + jitter_amount)

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries} failed, retrying in {delay:.2f}s: {e}",
                        extra={"attempt": attempt + 1, "max_retries": max_retries, "error": str(e)},
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {max_retries} attempts failed: {e}",
                        exc_info=True,
                        extra={"max_retries": max_retries},
                    )

        raise ZoteroAPIError(
            f"Operation failed after {max_retries} attempts: {last_error}",
            details={"max_retries": max_retries, "last_error": str(last_error)},
        ) from last_error

    def list_collections(self) -> list[dict[str, Any]]:
        """
        List all top-level collections in Zotero library.
        
        Returns:
            List of collections with keys: 'key', 'name', 'parentCollection'
        
        Raises:
            ZoteroConnectionError: If connection fails
            ZoteroAPIError: If API call fails
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        def _fetch_collections() -> list[dict[str, Any]]:
            self._rate_limit()
            try:
                collections = self.zot.collections()  # type: ignore[union-attr]
                return [
                    {
                        "key": coll.get("data", {}).get("key", ""),
                        "name": coll.get("data", {}).get("name", ""),
                        "parentCollection": coll.get("data", {}).get("parentCollection"),
                    }
                    for coll in collections
                ]
            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                raise ZoteroAPIError(f"Failed to list collections: {e}", details={"error": str(e)}) from e

        return self._retry_with_backoff(_fetch_collections)

    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Any:  # Iterator[dict[str, Any]]
        """
        Get items in a collection (generator to avoid loading all into memory).
        
        Args:
            collection_key: Zotero collection key
            include_subcollections: If True, recursively include items from subcollections
        
        Yields:
            Zotero items with keys: 'key', 'data' (containing title, itemType, etc.)
        
        Raises:
            ZoteroConnectionError: If connection fails
            ZoteroAPIError: If API call fails
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        def _fetch_items() -> Any:
            self._rate_limit()
            try:
                # Get items in collection
                items = self.zot.collection_items(collection_key)  # type: ignore[union-attr]

                # Yield items from this collection
                for item in items:
                    yield item

                # If including subcollections, recursively fetch items
                if include_subcollections:
                    try:
                        self._rate_limit()
                        subcollections = self.zot.collections_sub(collection_key)  # type: ignore[union-attr]
                        for subcoll in subcollections:
                            subcoll_key = subcoll.get("data", {}).get("key", "")
                            if subcoll_key:
                                # Recursively yield items from subcollections
                                for item in self.get_collection_items(subcoll_key, include_subcollections=True):
                                    yield item
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch subcollections for {collection_key}: {e}",
                            extra={"collection_key": collection_key, "error": str(e)},
                        )
                        # Continue without subcollections

            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                raise ZoteroAPIError(
                    f"Failed to get collection items: {e}",
                    details={"collection_key": collection_key, "error": str(e)},
                ) from e

        # Return generator that applies retry logic
        return self._retry_with_backoff(_fetch_items)

    def get_item_attachments(self, item_key: str) -> list[dict[str, Any]]:
        """
        Get PDF attachments for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            List of attachments with keys: 'key', 'data' (containing filename, contentType, linkMode)
        
        Raises:
            ZoteroConnectionError: If connection fails
            ZoteroAPIError: If API call fails
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        def _fetch_attachments() -> list[dict[str, Any]]:
            self._rate_limit()
            try:
                # Get children (attachments) of this item
                children = self.zot.children(item_key)  # type: ignore[union-attr]

                # Filter PDF attachments
                pdf_attachments = []
                for child in children:
                    child_data = child.get("data", {})
                    link_mode = child_data.get("linkMode", "")
                    content_type = child_data.get("contentType", "")

                    # Check if it's a PDF attachment
                    # linkMode: 'imported_file' (attached file) or 'linked_file' (linked file)
                    # contentType: 'application/pdf'
                    if link_mode in ("imported_file", "linked_file") and (
                        content_type == "application/pdf" or child_data.get("filename", "").endswith(".pdf")
                    ):
                        pdf_attachments.append(child)

                return pdf_attachments

            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                raise ZoteroAPIError(
                    f"Failed to get item attachments: {e}",
                    details={"item_key": item_key, "error": str(e)},
                ) from e

        return self._retry_with_backoff(_fetch_attachments)

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
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        def _download_file() -> Path:
            # Both local and remote API use zot.file() method
            # Local API goes through Better BibTeX JSON-RPC which handles file access
            self._rate_limit()
            try:
                # Download file content via API (works for both local and remote)
                # pyzotero file() method takes only the attachment key as positional argument
                file_data = self.zot.file(attachment_key)  # type: ignore[union-attr]

                # Write to output path
                with output_path.open("wb") as f:
                    if isinstance(file_data, bytes):
                        f.write(file_data)
                    elif hasattr(file_data, "read"):
                        f.write(file_data.read())
                    else:
                        raise ZoteroAPIError(
                            f"Unexpected file data type: {type(file_data)}",
                            details={"item_key": item_key, "attachment_key": attachment_key},
                        )

                api_type = "local" if self.local else "remote"
                logger.info(
                    f"Downloaded attachment from {api_type} API: {output_path}",
                    extra={"item_key": item_key, "attachment_key": attachment_key, "output_path": str(output_path), "api_type": api_type},
                )
                return output_path

            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                if "not found" in error_str or "404" in error_str or "does not exist" in error_str:
                    raise ZoteroAPIError(
                        f"Attachment not found: {e}",
                        details={"item_key": item_key, "attachment_key": attachment_key, "error": str(e)},
                    ) from e
                raise ZoteroAPIError(
                    f"Failed to download attachment: {e}",
                    details={"item_key": item_key, "attachment_key": attachment_key, "error": str(e)},
                ) from e

        return self._retry_with_backoff(_download_file, max_retries=3, base_delay=1.0, max_delay=30.0, jitter=True)

    def get_item_metadata(
        self,
        item_key: str,
        collection_cache: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Get full metadata for a Zotero item with optional collection cache to avoid redundant lookups.
        
        Args:
            item_key: Zotero item key
            collection_cache: Optional command-scoped cache for collection metadata
                - Key: collection_key (str)
                - Value: collection metadata dict from Zotero API
        
        Returns:
            Item metadata dict with keys: title, creators (authors), date (year), DOI, tags, collections
        
        Behavior:
            - Fetch item metadata from API
            - If item belongs to collections, check collection_cache before fetching collection info
            - Use cached collection metadata if available, otherwise fetch and cache
            - Return item metadata with collection names resolved
        
        Raises:
            ZoteroConnectionError: If connection fails
            ZoteroAPIError: If API call fails
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        def _fetch_metadata() -> dict[str, Any]:
            self._rate_limit()
            try:
                item = self.zot.item(item_key)  # type: ignore[union-attr]
                item_data = item.get("data", {})

                # Extract title
                title = item_data.get("title", "")

                # Extract creators (authors)
                creators: list[dict[str, Any]] = []
                creators_list = item_data.get("creators", [])
                if isinstance(creators_list, list):
                    creators = creators_list

                # Extract date (year)
                date_str = item_data.get("date", "")
                year: int | None = None
                if date_str:
                    try:
                        year_str = date_str.split("-")[0]
                        year = int(year_str)
                    except (ValueError, IndexError):
                        pass

                # Extract DOI
                doi = item_data.get("DOI") or item_data.get("doi")

                # Extract tags
                tags: list[str] = []
                tag_list = item_data.get("tags", [])
                if isinstance(tag_list, list):
                    for tag_obj in tag_list:
                        if isinstance(tag_obj, dict) and "tag" in tag_obj:
                            tags.append(tag_obj["tag"])
                        elif isinstance(tag_obj, str):
                            tags.append(tag_obj)

                # Extract collections - use cache if available
                collections: list[str] = []
                collection_keys = item_data.get("collections", [])
                if isinstance(collection_keys, list) and collection_keys:
                    try:
                        # Fetch collection names by key - check cache first
                        for coll_key in collection_keys:
                            try:
                                # Check cache first
                                if collection_cache and coll_key in collection_cache:
                                    coll_data = collection_cache[coll_key]
                                    coll_name = coll_data.get("name", "")
                                    if coll_name:
                                        collections.append(coll_name)
                                else:
                                    # Cache miss - fetch and cache
                                    self._rate_limit()
                                    coll = self.zot.collection(coll_key)  # type: ignore[union-attr]
                                    coll_data = coll.get("data", {})
                                    coll_name = coll_data.get("name", "")
                                    if coll_name:
                                        collections.append(coll_name)
                                    # Cache if cache provided
                                    if collection_cache is not None:
                                        collection_cache[coll_key] = coll_data
                            except Exception:
                                # Collection fetch failed, skip
                                pass
                    except Exception:
                        # Collection fetching not available or failed
                        pass

                # Extract additional metadata fields
                # Publication/journal information (for journal articles, book chapters, etc.)
                publication_title = (
                    item_data.get("publicationTitle") or
                    item_data.get("journalAbbreviation") or
                    item_data.get("publication") or
                    item_data.get("bookTitle") or
                    None
                )
                
                # Volume, issue, pages (for journal articles)
                volume = item_data.get("volume")
                issue = item_data.get("issue")
                pages = item_data.get("pages")
                
                # URL for web resources
                url = item_data.get("url") or item_data.get("URL")
                
                # Language
                language = item_data.get("language")
                
                # Item type
                item_type = item_data.get("itemType", "")
                
                return {
                    "title": title,
                    "creators": creators,
                    "date": date_str,
                    "year": year,
                    "DOI": doi,
                    "tags": tags,
                    "collections": collections,
                    "publicationTitle": publication_title,
                    "volume": volume,
                    "issue": issue,
                    "pages": pages,
                    "url": url,
                    "language": language,
                    "itemType": item_type,
                }

            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                raise ZoteroAPIError(
                    f"Failed to get item metadata: {e}",
                    details={"item_key": item_key, "error": str(e)},
                ) from e

        return self._retry_with_backoff(_fetch_metadata)

    def list_tags(self) -> list[dict[str, Any]]:
        """
        List all tags used in Zotero library.
        
        Returns:
            List of tags with keys: 'tag', 'meta' (containing numItems count)
        
        Raises:
            ZoteroConnectionError: If connection fails
            ZoteroAPIError: If API call fails
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        def _fetch_tags() -> list[dict[str, Any]]:
            self._rate_limit()
            try:
                tags = self.zot.tags()  # type: ignore[union-attr]
                result = []
                for tag in tags:
                    # Handle both dict and string formats from pyzotero
                    if isinstance(tag, dict):
                        result.append({
                            "tag": tag.get("tag", ""),
                            "meta": tag.get("meta", {}),
                        })
                    elif isinstance(tag, str):
                        # Tags can be returned as simple strings
                        result.append({
                            "tag": tag,
                            "meta": {},
                        })
                    else:
                        # Fallback: convert to string
                        result.append({
                            "tag": str(tag),
                            "meta": {},
                        })
                return result
            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                raise ZoteroAPIError(f"Failed to list tags: {e}", details={"error": str(e)}) from e

        return self._retry_with_backoff(_fetch_tags)

    def get_recent_items(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recently added items to Zotero library.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of items sorted by dateAdded (descending)
        
        Raises:
            ZoteroConnectionError: If connection fails
            ZoteroAPIError: If API call fails
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        def _fetch_recent_items() -> list[dict[str, Any]]:
            self._rate_limit()
            try:
                items = self.zot.items(sort="dateAdded", direction="desc", limit=limit)  # type: ignore[union-attr]
                return list(items)
            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                raise ZoteroAPIError(f"Failed to get recent items: {e}", details={"error": str(e)}) from e

        return self._retry_with_backoff(_fetch_recent_items)

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
                - Value: collection metadata dict from Zotero API
        
        Returns:
            Collection information dict with keys: key, name, metadata
        
        Behavior:
            - If collection_cache provided and collection_key found, return cached data
            - Otherwise, fetch from API, cache if collection_cache provided, return data
            - Cache key: collection_key from API response
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        # Check if it's a collection key (8 alphanumeric chars) or name
        if len(collection_name_or_key) == 8 and collection_name_or_key.isalnum():
            # It's a key - check cache first
            collection_key = collection_name_or_key
            if collection_cache and collection_key in collection_cache:
                cached = collection_cache[collection_key]
                return {
                    "key": cached.get("key", collection_key),
                    "name": cached.get("name", ""),
                    "metadata": cached,
                }
            
            # Fetch from API
            def _fetch_by_key() -> dict[str, Any]:
                self._rate_limit()
                try:
                    coll = self.zot.collection(collection_key)  # type: ignore[union-attr]
                    coll_data = coll.get("data", {})
                    coll_key = coll_data.get("key", collection_key)
                    coll_name = coll_data.get("name", "")
                    
                    result = {
                        "key": coll_key,
                        "name": coll_name,
                        "metadata": coll_data,
                    }
                    
                    # Cache if cache provided
                    if collection_cache is not None:
                        collection_cache[coll_key] = coll_data
                    
                    return result
                except Exception as e:
                    error_str = str(e).lower()
                    if "rate" in error_str or "limit" in error_str or "429" in error_str:
                        raise ZoteroRateLimitError("Zotero API rate limit exceeded", retry_after=60) from e
                    raise ZoteroAPIError(
                        f"Failed to get collection info: {e}",
                        details={"collection_key": collection_key, "error": str(e)},
                    ) from e
            
            return self._retry_with_backoff(_fetch_by_key)
        else:
            # It's a name - find by name first
            found = self.find_collection_by_name(collection_name_or_key)
            if found:
                coll_key = found.get("key", "")
                if coll_key:
                    # Use get_collection_info recursively with key (will check cache)
                    return self.get_collection_info(coll_key, collection_cache=collection_cache)
            else:
                raise ZoteroAPIError(
                    f"Collection not found: {collection_name_or_key}",
                    details={"collection_name_or_key": collection_name_or_key},
                )

    def get_api_call_summary(self) -> dict[str, Any] | None:
        """
        Get summary of API calls made since tracking started.
        
        Returns:
            Dict with 'count' and 'duration_seconds', or None if no calls made
        """
        if self._api_call_count == 0 or self._api_call_start_time is None:
            return None
        
        duration = time.time() - self._api_call_start_time
        return {
            "count": self._api_call_count,
            "duration_seconds": duration,
        }
    
    def reset_api_call_tracking(self) -> None:
        """Reset API call tracking counters."""
        self._api_call_count = 0
        self._api_call_start_time = None
    
    def log_api_call_summary(self) -> None:
        """
        Log summary of API calls made (T052a).
        
        Logs at INFO level with format: "Made N API calls in X seconds"
        """
        summary = self.get_api_call_summary()
        if summary:
            logger.info(
                f"Made {summary['count']} API call(s) in {summary['duration_seconds']:.1f} seconds",
                extra={
                    "api_call_count": summary["count"],
                    "duration_seconds": summary["duration_seconds"],
                },
            )
    
    def find_collection_by_name(self, collection_name: str) -> dict[str, Any] | None:
        """
        Find collection by name (case-insensitive partial match).
        
        Args:
            collection_name: Collection name to search for
        
        Returns:
            Collection dict with keys: 'key', 'name', or None if not found
        
        Raises:
            ZoteroConnectionError: If connection fails
            ZoteroAPIError: If API call fails
        """
        if self.zot is None:
            raise ZoteroConnectionError("Zotero client not initialized. Client initialization failed")

        try:
            collections = self.list_collections()
            collection_name_lower = collection_name.lower()

            # Case-insensitive partial match
            for coll in collections:
                coll_name = coll.get("name", "")
                if collection_name_lower in coll_name.lower():
                    return coll

            return None

        except ZoteroConnectionError:
            raise
        except ZoteroAPIError:
            raise
        except Exception as e:
            raise ZoteroAPIError(
                f"Failed to find collection by name: {e}",
                details={"collection_name": collection_name, "error": str(e)},
            ) from e

