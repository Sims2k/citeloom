from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping, Any

from ...domain.models.citation_meta import CitationMeta
from ...domain.errors import MetadataMissing

logger = logging.getLogger(__name__)


class ZoteroCslJsonResolver:
    """
    Adapter for resolving citation metadata from Zotero CSL-JSON exports.
    
    Implements DOI-first matching with normalized title fallback.
    """
    
    def resolve(
        self,
        citekey: str | None,
        references_path: str,
        doc_id: str,
        source_hint: str | None = None,
    ) -> CitationMeta | None:
        """
        Resolve citation metadata from CSL-JSON references file.
        
        Args:
            citekey: Citation key hint (if available)
            references_path: Path to CSL-JSON references file
            doc_id: Document identifier for matching
            source_hint: Additional source hint (title, DOI, etc.)
        
        Returns:
            CitationMeta if match found, None otherwise
        
        Note:
            Non-blocking: Returns None if no match, logs MetadataMissing warning
        """
        path = Path(references_path)
        if not path.exists():
            logger.warning(
                f"References file not found: {references_path}",
                extra={"doc_id": doc_id, "references_path": references_path},
            )
            return None
        
        try:
            # Try utf-8-sig first to handle BOM, fallback to utf-8
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
            except UnicodeDecodeError:
                data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(
                f"Failed to parse references file: {e}",
                extra={"doc_id": doc_id, "references_path": references_path},
            )
            return None
        
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            logger.warning(
                f"References file does not contain items list",
                extra={"doc_id": doc_id, "references_path": references_path},
            )
            return None
        
        # Match by citekey first (if provided)
        if citekey:
            for item in items:
                key = item.get("id") or item.get("citekey") or item.get("citationKey")
                if key == citekey:
                    logger.info(
                        f"Metadata matched by citekey for doc_id={doc_id}",
                        extra={"doc_id": doc_id, "citekey": citekey},
                    )
                    return self._extract_metadata(item, doc_id)
        
        # DOI-first matching: Extract and match DOI if available in source_hint
        doi_hint: str | None = None
        if source_hint:
            source_hint_lower = source_hint.lower()
            # Check for DOI in various formats
            if "doi:" in source_hint_lower:
                # Extract DOI from "doi:10.1234/example" format
                doi_hint = source_hint_lower.split("doi:")[-1].strip()
            elif source_hint_lower.startswith("https://doi.org/") or source_hint_lower.startswith("http://doi.org/"):
                # Extract from URL
                doi_hint = source_hint_lower.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
            elif source_hint.startswith("10."):
                # Direct DOI format "10.1234/example" (case-sensitive check for 10.)
                doi_hint = source_hint.strip()
        
        if doi_hint:
            # Normalize DOI for matching (remove URL prefixes, lowercase, strip)
            doi_hint_normalized = self._normalize_doi(doi_hint)
            for item in items:
                item_doi = item.get("DOI") or item.get("doi")
                if item_doi:
                    item_doi_normalized = self._normalize_doi(item_doi)
                    # Exact match or contains match (handles partial DOIs)
                    if doi_hint_normalized == item_doi_normalized or doi_hint_normalized in item_doi_normalized:
                        logger.info(
                            f"Metadata matched by DOI for doc_id={doc_id}",
                            extra={"doc_id": doc_id, "doi": item_doi},
                        )
                        return self._extract_metadata(item, doc_id)
        
        # Fallback: match by normalized title (fuzzy matching)
        if source_hint and not doi_hint:  # Only if source_hint is not a DOI
            normalized_hint = self._normalize_title(source_hint)
            best_match = None
            best_score = 0.0
            fuzzy_threshold = 0.8  # Configurable threshold (default per spec)
            
            for item in items:
                item_title = item.get("title", "")
                if item_title:
                    normalized_item = self._normalize_title(item_title)
                    # Jaccard similarity on words
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
                f"Check references file {references_path} for matching entry. "
                f"Try adding entry with DOI, citekey, or matching title."
            ),
        )
        logger.warning(
            str(error),
            extra={"doc_id": doc_id, "references_path": references_path, "source_hint": source_hint},
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
                normalized = normalized[len(prefix):]
        return normalized.strip()
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for matching (lowercase, remove punctuation, collapse spaces)."""
        import re
        normalized = title.lower()
        normalized = re.sub(r'[^\w\s]', '', normalized)  # Remove punctuation
        normalized = re.sub(r'\s+', ' ', normalized)  # Collapse whitespace
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
    
    def _extract_metadata(self, item: dict[str, Any], doc_id: str) -> CitationMeta:
        """
        Extract CitationMeta from CSL-JSON item.
        
        Args:
            item: CSL-JSON item dict
            doc_id: Document identifier
        
        Returns:
            CitationMeta object
        """
        # Extract authors
        authors: list[str] = []
        author_list = item.get("author", [])
        if isinstance(author_list, list):
            for author in author_list:
                if isinstance(author, dict):
                    # CSL-JSON format: {"family": "Last", "given": "First"}
                    parts = []
                    if "given" in author:
                        parts.append(author["given"])
                    if "family" in author:
                        parts.append(author["family"])
                    if parts:
                        authors.append(" ".join(parts))
                elif isinstance(author, str):
                    authors.append(author)
        
        # Extract year
        year = None
        issued = item.get("issued", {})
        if isinstance(issued, dict):
            date_parts = issued.get("date-parts", [])
            if date_parts and isinstance(date_parts[0], list) and date_parts[0]:
                year = date_parts[0][0]
        
        # Extract citekey (from id field, typically Better BibTeX key)
        citekey = item.get("id", "") or item.get("citationKey", "") or item.get("citekey", "")
        
        # Extract DOI and URL
        doi = item.get("DOI") or item.get("doi")
        url = item.get("URL") or item.get("url")
        
        # Extract tags and collections
        tags = item.get("tags", [])
        if isinstance(tags, list):
            tags = [tag if isinstance(tag, str) else tag.get("name", "") for tag in tags]
        
        collections = item.get("collections", [])
        if isinstance(collections, list):
            collections = [coll if isinstance(coll, str) else coll.get("name", "") for coll in collections]
        
        return CitationMeta(
            citekey=citekey or f"unknown_{doc_id}",
            title=item.get("title", "Unknown Title"),
            authors=authors if authors else ["Unknown Author"],
            year=year,
            doi=doi,
            url=url,
            tags=tags,
            collections=collections,
        )
