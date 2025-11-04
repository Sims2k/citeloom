from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any

from pyzotero import zotero

from ...domain.errors import MetadataMissing
from ...domain.models.citation_meta import CitationMeta
from ...infrastructure.config.environment import get_env, get_env_bool, load_environment_variables

logger = logging.getLogger(__name__)


class ZoteroPyzoteroResolver:
    """
    Adapter for resolving citation metadata from Zotero library via pyzotero API.
    
    Implements DOI-first matching with normalized title fallback, Better BibTeX
    citekey extraction via JSON-RPC, and language field extraction for OCR.
    """

    def __init__(self, zotero_config: dict[str, Any] | None = None) -> None:
        """
        Initialize Zotero client with configuration.
        
        Args:
            zotero_config: Optional configuration dict with:
                - library_id: Zotero library ID
                - library_type: 'user' or 'group'
                - api_key: API key for remote access (required for remote)
                - local: True for local access (defaults to False)
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
        # Priority: explicit config > environment variable > default (False)
        if "local" in zotero_config:
            # Explicit config value takes precedence
            use_local = bool(zotero_config.get("local", False))
        else:
            # Only check environment if not explicitly set in config
            use_local = get_env_bool("ZOTERO_LOCAL", False)
        
        if not library_id:
            # Client not initialized - will handle gracefully in resolve()
            self.zot = None
            logger.warning(
                "Zotero library_id not configured. Metadata resolution will be disabled.",
                extra={"zotero_config": zotero_config},
            )
            return
        
        try:
            if use_local:
                # Local access: Zotero must be running with local API enabled
                # library_id is typically '1' for user library in local mode
                self.zot = zotero.Zotero(library_id, library_type, api_key=None, local=True)
                logger.info(
                    "Zotero client initialized for local access",
                    extra={"library_id": library_id, "library_type": library_type},
                )
            else:
                # Remote access: requires API key
                api_key = zotero_config.get("api_key") or get_env("ZOTERO_API_KEY")
                if not api_key:
                    self.zot = None
                    logger.warning(
                        "Zotero API key not configured for remote access. Metadata resolution will be disabled.",
                        extra={"library_id": library_id, "library_type": library_type},
                    )
                    return
                
                self.zot = zotero.Zotero(library_id, library_type, api_key)
                logger.info(
                    "Zotero client initialized for remote access",
                    extra={"library_id": library_id, "library_type": library_type},
                )
        except Exception as e:
            self.zot = None
            logger.warning(
                f"Failed to initialize Zotero client: {e}",
                extra={"library_id": library_id, "library_type": library_type, "error": str(e)},
            )

    def resolve(
        self,
        citekey: str | None,
        doc_id: str,
        source_hint: str | None = None,
        zotero_config: dict[str, Any] | None = None,
    ) -> CitationMeta | None:
        """
        Resolve citation metadata from Zotero library via pyzotero API.
        
        Args:
            citekey: Citation key hint (if available, from Better BibTeX)
            doc_id: Document identifier for matching
            source_hint: Additional source hint (title, DOI, etc.)
            zotero_config: Optional Zotero configuration (overrides instance config)
        
        Returns:
            CitationMeta if match found, None otherwise
        
        Note:
            Non-blocking: Returns None if no match, logs MetadataMissing warning.
            Gracefully handles pyzotero API connection failures and Better BibTeX
            JSON-RPC unavailability.
        """
        if self.zot is None:
            # Client not initialized - cannot resolve metadata
            return None
        
        try:
            # Step 1: Extract DOI from source_hint if available
            doi_hint: str | None = None
            if source_hint:
                source_hint_lower = source_hint.lower()
                # Check for DOI in various formats
                if "doi:" in source_hint_lower:
                    doi_hint = source_hint_lower.split("doi:")[-1].strip()
                elif source_hint_lower.startswith("https://doi.org/") or source_hint_lower.startswith("http://doi.org/"):
                    doi_hint = source_hint_lower.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
                elif source_hint.startswith("10."):
                    doi_hint = source_hint.strip()
            
            # Step 2: Search by DOI first (exact match, normalized)
            if doi_hint:
                doi_normalized = self._normalize_doi(doi_hint)
                # pyzotero items() returns a generator/iterator - iterate through all items
                items = self.zot.items()
                
                for item in items:
                    item_data = item.get("data", {})
                    item_doi = item_data.get("DOI") or item_data.get("doi")
                    if item_doi:
                        item_doi_normalized = self._normalize_doi(item_doi)
                        if doi_normalized == item_doi_normalized:
                            logger.info(
                                f"Metadata matched by DOI for doc_id={doc_id}",
                                extra={"doc_id": doc_id, "doi": item_doi},
                            )
                            return self._extract_metadata(item, doc_id)
            
            # Step 3: Fallback to title-based matching (normalized, fuzzy threshold ≥ 0.8)
            if source_hint and not doi_hint:
                normalized_hint = self._normalize_title(source_hint)
                # pyzotero items() returns a generator/iterator - iterate through all items
                items = self.zot.items()
                best_match = None
                best_score = 0.0
                fuzzy_threshold = 0.8  # Default threshold per spec
                
                for item in items:
                    item_data = item.get("data", {})
                    item_title = item_data.get("title", "")
                    if item_title:
                        normalized_item = self._normalize_title(item_title)
                        score = self._fuzzy_score(normalized_hint, normalized_item)
                        if score > best_score and score >= fuzzy_threshold:
                            best_score = score
                            best_match = item
                
                if best_match:
                    logger.info(
                        f"Metadata matched by title (score={best_score:.2f}) for doc_id={doc_id}",
                        extra={"doc_id": doc_id, "score": best_score},
                    )
                    return self._extract_metadata(best_match, doc_id)
            
            # No match found - log MetadataMissing (non-blocking)
            error = MetadataMissing(
                doc_id=doc_id,
                hint=(
                    f"Check Zotero library for matching entry. "
                    f"Try adding entry with DOI, citekey, or matching title."
                ),
            )
            logger.warning(
                str(error),
                extra={"doc_id": doc_id, "source_hint": source_hint},
            )
            
            return None
            
        except Exception as e:
            # Gracefully handle pyzotero API connection failures
            logger.warning(
                f"Zotero API error during metadata resolution: {e}",
                extra={"doc_id": doc_id, "source_hint": source_hint, "error": str(e)},
                exc_info=True,
            )
            return None

    def _normalize_doi(self, doi: str) -> str:
        """
        Normalize DOI for matching.
        
        Removes URL prefixes, converts to lowercase, strips whitespace.
        """
        normalized = doi.lower().strip()
        # Remove common DOI URL prefixes
        for prefix in ["https://doi.org/", "http://doi.org/", "doi:", "dx.doi.org/"]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
        return normalized.strip()

    def _normalize_title(self, title: str) -> str:
        """Normalize title for matching (lowercase, remove punctuation, collapse spaces)."""
        import re

        normalized = title.lower()
        normalized = re.sub(r"[^\w\s]", "", normalized)  # Remove punctuation
        normalized = re.sub(r"\s+", " ", normalized)  # Collapse whitespace
        return normalized.strip()

    def _fuzzy_score(self, s1: str, s2: str) -> float:
        """Simple fuzzy matching score (Jaccard similarity on words)."""
        words1 = set(s1.split())
        words2 = set(s2.split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _check_better_bibtex_available(self, port: int = 23119, timeout: int = 5) -> bool:
        """
        Check if Better BibTeX JSON-RPC server is available on specified port.
        
        Args:
            port: Port number (23119 for Zotero, 24119 for Juris-M)
            timeout: Timeout in seconds (default 5s, per spec up to 10s)
        
        Returns:
            True if Better BibTeX is running and accessible
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def _get_citekey_from_better_bibtex(self, item_key: str, port: int = 23119) -> str | None:
        """
        Extract Better BibTeX citekey via JSON-RPC API.
        
        Args:
            item_key: Zotero item key (from item['key'])
            port: Port number (23119 for Zotero, 24119 for Juris-M)
        
        Returns:
            Citekey string if successful, None otherwise
        """
        if not self._check_better_bibtex_available(port, timeout=5):
            logger.debug(
                f"Better BibTeX not available on port {port}",
                extra={"item_key": item_key, "port": port},
            )
            return None
        
        try:
            # Better BibTeX JSON-RPC API: http://localhost:23119/jsonrpc
            url = f"http://localhost:{port}/jsonrpc"
            
            # JSON-RPC 2.0 request: item.citationkey method
            payload = {
                "jsonrpc": "2.0",
                "method": "item.citationkey",
                "params": [item_key],
                "id": 1,
            }
            
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                if "result" in result:
                    citekey = result["result"]
                    if citekey:
                        logger.debug(
                            f"Better BibTeX citekey extracted: {citekey}",
                            extra={"item_key": item_key, "citekey": citekey},
                        )
                        return citekey
            
            return None
            
        except (urllib.error.URLError, socket.timeout, json.JSONDecodeError, KeyError) as e:
            logger.debug(
                f"Better BibTeX JSON-RPC error: {e}",
                extra={"item_key": item_key, "port": port, "error": str(e)},
            )
            return None

    def _extract_citekey_from_extra(self, item_data: dict[str, Any]) -> str | None:
        """
        Extract Better BibTeX citekey from item['data']['extra'] field.
        
        Parses "Citation Key: citekey" pattern as fallback when JSON-RPC unavailable.
        
        Args:
            item_data: Zotero item data dict
        
        Returns:
            Citekey string if found, None otherwise
        """
        extra = item_data.get("extra", "")
        if not isinstance(extra, str):
            return None
        
        # Look for "Citation Key: citekey" pattern
        lines = extra.split("\n")
        for line in lines:
            if line.strip().startswith("Citation Key:"):
                citekey = line.split(":", 1)[1].strip()
                if citekey:
                    logger.debug(
                        f"Citekey extracted from extra field: {citekey}",
                        extra={"citekey": citekey},
                    )
                    return citekey
        
        return None

    def _map_language_to_ocr_code(self, zotero_lang: str | None) -> str | None:
        """
        Map Zotero language codes to OCR language codes.
        
        Examples: 'en-US' → 'en', 'de-DE' → 'de', 'fr-FR' → 'fr'
        
        Args:
            zotero_lang: Zotero language code (e.g., 'en-US', 'de-DE')
        
        Returns:
            OCR language code (first 2 letters, lowercase) or None
        """
        if not zotero_lang:
            return None
        
        # Extract first 2 characters (language code) and lowercase
        # Handles: 'en-US' → 'en', 'de-DE' → 'de', 'en' → 'en'
        lang_code = zotero_lang.split("-")[0].lower()
        
        # Validate against common OCR-supported languages
        # Common: 'en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'ru', 'zh', 'ja'
        supported = ["en", "de", "fr", "es", "it", "pt", "nl", "ru", "zh", "ja"]
        if lang_code in supported:
            return lang_code
        
        # Return lowercase first 2 chars even if not in supported list
        # (OCR engines may support additional languages)
        return lang_code if len(lang_code) >= 2 else None

    def _extract_metadata(self, item: dict[str, Any], doc_id: str) -> CitationMeta:
        """
        Extract CitationMeta from pyzotero item response.
        
        Args:
            item: pyzotero item dict (has 'data' and 'key' fields)
            doc_id: Document identifier
        
        Returns:
            CitationMeta object with language field
        """
        item_data = item.get("data", {})
        item_key = item.get("key", "")
        
        # Extract Better BibTeX citekey (T070, T071)
        citekey: str | None = None
        
        # Try Better BibTeX JSON-RPC first (port 23119 for Zotero)
        if item_key:
            citekey = self._get_citekey_from_better_bibtex(item_key, port=23119)
            
            # If failed, try Juris-M port (24119)
            if not citekey:
                citekey = self._get_citekey_from_better_bibtex(item_key, port=24119)
        
        # Fallback: parse item['data']['extra'] field
        if not citekey:
            citekey = self._extract_citekey_from_extra(item_data)
        
        # Extract title
        title = item_data.get("title", "Unknown Title")
        
        # Extract authors from creators array
        authors: list[str] = []
        creators = item_data.get("creators", [])
        if isinstance(creators, list):
            for creator in creators:
                if isinstance(creator, dict):
                    # Zotero format: {"firstName": "First", "lastName": "Last"} or {"name": "Full Name"}
                    if "name" in creator:
                        authors.append(creator["name"])
                    else:
                        parts = []
                        if "firstName" in creator:
                            parts.append(creator["firstName"])
                        if "lastName" in creator:
                            parts.append(creator["lastName"])
                        if parts:
                            authors.append(" ".join(parts))
        
        # Extract year from date
        year: int | None = None
        date_str = item_data.get("date", "")
        if date_str:
            # Extract year from date string (e.g., '2023-01-15' → 2023)
            try:
                year_str = date_str.split("-")[0]
                year = int(year_str)
            except (ValueError, IndexError):
                pass
        
        # Extract DOI and URL
        doi = item_data.get("DOI") or item_data.get("doi")
        url = item_data.get("url") or item_data.get("URL")
        
        # Extract tags
        tags: list[str] = []
        tag_list = item_data.get("tags", [])
        if isinstance(tag_list, list):
            for tag_obj in tag_list:
                if isinstance(tag_obj, dict) and "tag" in tag_obj:
                    tags.append(tag_obj["tag"])
                elif isinstance(tag_obj, str):
                    tags.append(tag_obj)
        
        # Extract collections (need to fetch via API or get from item)
        collections: list[str] = []
        collection_keys = item_data.get("collections", [])
        if isinstance(collection_keys, list) and collection_keys:
            try:
                # Fetch collections by key
                for coll_key in collection_keys:
                    try:
                        coll = self.zot.collection(coll_key)
                        coll_data = coll.get("data", {})
                        coll_name = coll_data.get("name", "")
                        if coll_name:
                            collections.append(coll_name)
                    except Exception:
                        # Collection fetch failed, skip
                        pass
            except Exception:
                # Collection fetching not available or failed
                pass
        
        # Extract language and map to OCR code (T074)
        zotero_lang = item_data.get("language", "")
        ocr_language = self._map_language_to_ocr_code(zotero_lang) if zotero_lang else None
        
        # Use citekey from Better BibTeX, or fallback to generated key, or doc_id-based key
        if not citekey:
            # Already tried _extract_citekey_from_extra above, so just use doc_id-based key as final fallback
            citekey = f"unknown_{doc_id}"
        
        return CitationMeta(
            citekey=citekey,
            title=title,
            authors=authors if authors else ["Unknown Author"],
            year=year,
            doi=doi,
            url=url,
            tags=tags,
            collections=collections,
            language=ocr_language,  # Mapped OCR language code
        )


# Alias for backwards compatibility (if any code still references the old name)
ZoteroCslJsonResolver = ZoteroPyzoteroResolver
