"""Adapter for resolving full-text content from Zotero fulltext table."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...application.ports.converter import TextConverterPort
from ...application.ports.fulltext_resolver import FulltextResolverPort, FulltextResult
from ...domain.errors import (
    ZoteroDatabaseLockedError,
    ZoteroDatabaseNotFoundError,
    ZoteroFulltextNotFoundError,
    ZoteroFulltextQualityError,
)
from .zotero_local_db import LocalZoteroDbAdapter

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ZoteroFulltextResolverAdapter(FulltextResolverPort):
    """
    Adapter for resolving full-text content from Zotero fulltext table.
    
    Queries Zotero SQLite database for cached fulltext, validates quality,
    and falls back to Docling conversion if unavailable or low-quality.
    """

    def __init__(
        self,
        local_db_adapter: LocalZoteroDbAdapter | None = None,
        converter: TextConverterPort | None = None,
    ) -> None:
        """
        Initialize fulltext resolver.
        
        Args:
            local_db_adapter: Optional LocalZoteroDbAdapter for SQLite access.
                If None, will auto-detect and create one.
            converter: Optional TextConverterPort for Docling fallback.
                If None, Docling conversion will raise ImportError if unavailable.
        """
        self._local_db: LocalZoteroDbAdapter | None = local_db_adapter
        self._converter: TextConverterPort | None = converter

    def _get_db_connection(self) -> sqlite3.Connection:
        """Get SQLite database connection from local adapter."""
        if self._local_db is None:
            # Auto-create local adapter if not provided
            try:
                self._local_db = LocalZoteroDbAdapter()
            except Exception as e:
                logger.warning(
                    f"Failed to create LocalZoteroDbAdapter: {e}. "
                    "Fulltext resolution will fallback to Docling conversion.",
                )
                raise ZoteroDatabaseNotFoundError(
                    "Local database adapter unavailable",
                    hint="Ensure Zotero is installed and database is accessible.",
                ) from e

        # Access internal connection (note: LocalZoteroDbAdapter uses _conn)
        if hasattr(self._local_db, "_conn") and self._local_db._conn is not None:
            return self._local_db._conn
        else:
            raise ZoteroDatabaseNotFoundError(
                "Database connection not available",
                hint="Local database adapter connection not initialized.",
            )

    def get_zotero_fulltext(
        self,
        attachment_key: str,
    ) -> str | None:
        """
        Get fulltext from Zotero fulltext table (if available).
        
        Args:
            attachment_key: Zotero attachment key
        
        Returns:
            Fulltext string or None if not available
        """
        try:
            conn = self._get_db_connection()
        except (ZoteroDatabaseNotFoundError, ZoteroDatabaseLockedError):
            logger.debug(f"Database unavailable, cannot query fulltext for attachment {attachment_key}")
            return None

        # Query fulltext table
        # Note: Zotero stores fulltext indexed by itemID, which maps to attachment key
        # We need to find the itemID for this attachment_key
        try:
            # First, find itemID from items table where key = attachment_key
            item_query = """
                SELECT itemID FROM items WHERE key = ?
            """
            cursor = conn.execute(item_query, (attachment_key,))
            row = cursor.fetchone()
            
            if row is None:
                logger.debug(f"Attachment key {attachment_key} not found in items table")
                return None
            
            item_id = row["itemID"]
            
            # Query fulltext table for this itemID
            fulltext_query = """
                SELECT fulltext FROM fulltext WHERE itemID = ?
            """
            cursor = conn.execute(fulltext_query, (item_id,))
            row = cursor.fetchone()
            
            if row is None:
                logger.debug(f"Fulltext not found for itemID {item_id} (attachment {attachment_key})")
                return None
            
            fulltext = row["fulltext"]
            if fulltext is None or not fulltext.strip():
                logger.debug(f"Fulltext is empty for itemID {item_id} (attachment {attachment_key})")
                return None
            
            return fulltext
        except sqlite3.Error as e:
            logger.warning(
                f"Database error querying fulltext for {attachment_key}: {e}",
                exc_info=True,
            )
            return None
        except Exception as e:
            logger.warning(
                f"Unexpected error querying fulltext for {attachment_key}: {e}",
                exc_info=True,
            )
            return None

    def _validate_fulltext_quality(
        self,
        fulltext: str,
        min_length: int = 100,
    ) -> tuple[bool, float]:
        """
        Validate fulltext quality.
        
        Args:
            fulltext: Fulltext string to validate
            min_length: Minimum text length required
        
        Returns:
            Tuple of (is_valid, quality_score)
            - is_valid: True if fulltext meets quality requirements
            - quality_score: Quality score (0.0 to 1.0)
        """
        if not fulltext or not fulltext.strip():
            return False, 0.0
        
        text = fulltext.strip()
        
        # Length check
        if len(text) < min_length:
            logger.debug(f"Fulltext too short: {len(text)} < {min_length}")
            return False, len(text) / min_length if min_length > 0 else 0.0
        
        # Structure checks: should have reasonable word count and sentence structure
        words = text.split()
        if len(words) < 10:  # Very short text
            logger.debug(f"Fulltext has too few words: {len(words)} < 10")
            return False, len(words) / 10.0
        
        # Check for reasonable sentence structure (look for periods, question marks, etc.)
        sentence_indicators = len(re.findall(r'[.!?]\s+', text))
        if sentence_indicators == 0 and len(text) > 500:
            # Long text without sentence indicators might be malformed
            logger.debug(f"Fulltext lacks sentence indicators (might be malformed)")
            return False, 0.3
        
        # Quality score: based on length and structure
        length_score = min(1.0, len(text) / (min_length * 10))  # Scale to reasonable max
        structure_score = min(1.0, sentence_indicators / 10.0)  # Normalize to 10 sentences
        quality_score = (length_score + structure_score) / 2.0
        
        return True, quality_score

    def _parse_zotero_fulltext_pages(self, fulltext: str) -> dict[int, str]:
        """
        Parse Zotero fulltext into page-indexed text.
        
        Zotero fulltext typically doesn't have explicit page markers,
        so we attempt to detect page breaks using common patterns.
        
        Args:
            fulltext: Raw fulltext from Zotero
        
        Returns:
            Dict mapping page number (1-indexed) to page text
        """
        pages: dict[int, str] = {}
        
        # Zotero fulltext may not have explicit page boundaries
        # For now, we treat the entire fulltext as page 1
        # More sophisticated parsing could detect page breaks if Zotero stores them
        if fulltext.strip():
            pages[1] = fulltext.strip()
        
        return pages

    def _extract_docling_pages(
        self,
        conversion_result: dict[str, Any],
    ) -> tuple[str, dict[int, str]]:
        """
        Extract pages from Docling conversion result.
        
        Args:
            conversion_result: Conversion result dict from Docling
        
        Returns:
            Tuple of (plain_text, page_map) where page_map maps page number to text
        """
        plain_text = conversion_result.get("plain_text", "")
        if not plain_text:
            structure = conversion_result.get("structure", {})
            if isinstance(structure, dict):
                plain_text = structure.get("text", "") or structure.get("content", "")
        
        # Extract page_map if available
        page_map: dict[int, tuple[int, int]] = {}
        structure = conversion_result.get("structure", {})
        if isinstance(structure, dict):
            page_map = structure.get("page_map", {})
        
        # Build page-indexed text dictionary
        pages: dict[int, str] = {}
        if page_map and plain_text:
            # Extract text for each page using page_map offsets
            for page_num, (start_offset, end_offset) in page_map.items():
                if start_offset < len(plain_text) and end_offset <= len(plain_text):
                    pages[page_num] = plain_text[start_offset:end_offset]
        elif plain_text:
            # No page_map available, treat entire text as page 1
            pages[1] = plain_text
        
        return plain_text, pages

    def _merge_mixed_provenance(
        self,
        zotero_pages: dict[int, str],
        docling_pages: dict[int, str],
    ) -> tuple[str, list[int], list[int]]:
        """
        Merge pages from Zotero and Docling sources with sequential concatenation.
        
        Args:
            zotero_pages: Dict of page number -> text from Zotero
            docling_pages: Dict of page number -> text from Docling
        
        Returns:
            Tuple of (merged_text, pages_from_zotero, pages_from_docling)
        """
        merged_text_parts: list[str] = []
        pages_from_zotero: list[int] = []
        pages_from_docling: list[int] = []
        
        # Determine page range: union of both sources
        all_pages = sorted(set(list(zotero_pages.keys()) + list(docling_pages.keys())))
        
        for page_num in all_pages:
            zotero_text = zotero_pages.get(page_num, "").strip()
            docling_text = docling_pages.get(page_num, "").strip()
            
            # Prefer Zotero if available, fallback to Docling
            if zotero_text:
                merged_text_parts.append(zotero_text)
                pages_from_zotero.append(page_num)
            elif docling_text:
                merged_text_parts.append(docling_text)
                pages_from_docling.append(page_num)
        
        merged_text = "\n\n".join(merged_text_parts)
        return merged_text, pages_from_zotero, pages_from_docling

    def resolve_fulltext(
        self,
        attachment_key: str,
        file_path: Path,
        prefer_zotero: bool = True,
        min_length: int = 100,
    ) -> FulltextResult:
        """
        Resolve full-text content with preference strategy.
        
        Checks Zotero fulltext table first if prefer_zotero=True, validates quality,
        falls back to Docling conversion if fulltext unavailable or low-quality.
        Supports page-level mixed provenance (some pages from Zotero, some from Docling).
        
        Args:
            attachment_key: Zotero attachment key (for querying fulltext table)
            file_path: Local file path (for Docling conversion fallback)
            prefer_zotero: If True, prefer Zotero fulltext when available
            min_length: Minimum text length for quality validation
        
        Returns:
            FulltextResult with text, source, and provenance metadata
        
        Raises:
            Exception: If Docling conversion fails (specific exception depends on converter)
            ZoteroDatabaseError: If database access fails (non-fatal, falls back to Docling)
        """
        zotero_fulltext = None
        zotero_pages: dict[int, str] = {}
        
        # Try Zotero fulltext first if preferred
        if prefer_zotero:
            zotero_fulltext = self.get_zotero_fulltext(attachment_key)
            
            if zotero_fulltext is not None:
                # Validate quality
                is_valid, quality_score = self._validate_fulltext_quality(zotero_fulltext, min_length)
                
                if is_valid:
                    # Parse Zotero fulltext into pages
                    zotero_pages = self._parse_zotero_fulltext_pages(zotero_fulltext)
                    
                    # If we have converter, try to get Docling for missing pages (mixed provenance)
                    if self._converter is not None:
                        try:
                            conversion_result = self._converter.convert(str(file_path))
                            _, docling_pages = self._extract_docling_pages(conversion_result)
                            
                            # Merge pages from both sources
                            merged_text, pages_from_zotero, pages_from_docling = self._merge_mixed_provenance(
                                zotero_pages, docling_pages
                            )
                            
                            if pages_from_docling:
                                # Mixed provenance
                                logger.info(
                                    f"Using mixed provenance for {attachment_key}: "
                                    f"{len(pages_from_zotero)} pages from Zotero, "
                                    f"{len(pages_from_docling)} pages from Docling",
                                )
                                return FulltextResult(
                                    text=merged_text,
                                    source="mixed",
                                    pages_from_zotero=pages_from_zotero,
                                    pages_from_docling=pages_from_docling,
                                    zotero_quality_score=quality_score,
                                )
                        except Exception as e:
                            logger.debug(
                                f"Docling conversion failed for mixed provenance, using Zotero only: {e}",
                            )
                            # Fall through to use Zotero only
                    
                    # Use Zotero fulltext only
                    logger.info(
                        f"Using Zotero fulltext for {attachment_key} (quality_score={quality_score:.2f})",
                    )
                    return FulltextResult(
                        text=zotero_fulltext,
                        source="zotero",
                        pages_from_zotero=list(zotero_pages.keys()) if zotero_pages else [],
                        zotero_quality_score=quality_score,
                    )
                else:
                    logger.info(
                        f"Zotero fulltext quality too low for {attachment_key} "
                        f"(quality_score={quality_score:.2f}), falling back to Docling",
                    )
                    # Fall through to Docling conversion
        
        # Fallback to Docling conversion
        if self._converter is None:
            raise ValueError(
                "Converter not provided and Zotero fulltext unavailable. "
                "Cannot resolve fulltext without either Zotero fulltext or Docling converter."
            )
        
        try:
            logger.info(f"Converting {file_path} via Docling (Zotero fulltext unavailable or low-quality)")
            conversion_result = self._converter.convert(str(file_path))
            
            plain_text, docling_pages = self._extract_docling_pages(conversion_result)
            
            if not plain_text:
                raise ValueError(f"Docling conversion did not produce text for {file_path}")
            
            return FulltextResult(
                text=plain_text,
                source="docling",
                pages_from_docling=list(docling_pages.keys()) if docling_pages else [],
            )
        except Exception as e:
            logger.error(
                f"Docling conversion failed for {file_path}: {e}",
                exc_info=True,
            )
            raise

