"""Port for resolving document full-text content from Zotero or Docling."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class FulltextResult:
    """
    Result of full-text resolution.
    
    Attributes:
        text: Full text content (from Zotero or Docling)
        source: "zotero" | "docling" | "mixed"
        pages_from_zotero: List of page numbers from Zotero fulltext (for mixed provenance)
        pages_from_docling: List of page numbers from Docling conversion (for mixed provenance)
        zotero_quality_score: Quality score for Zotero fulltext (0.0 to 1.0, None if not used)
    """
    text: str
    source: str  # "zotero" | "docling" | "mixed"
    pages_from_zotero: list[int] = field(default_factory=list)
    pages_from_docling: list[int] = field(default_factory=list)
    zotero_quality_score: float | None = None


class FulltextResolverPort(ABC):
    """Port for resolving document full-text content."""
    
    @abstractmethod
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
            DocumentConversionError: If Docling conversion fails
            ZoteroDatabaseError: If database access fails
        """
        pass
    
    @abstractmethod
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
        pass

