"""Port for extracting PDF annotations from Zotero."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyzotero import zotero
    from ..ports.metadata_resolver import MetadataResolverPort
    from ..ports.vector_index import VectorIndexPort


@dataclass
class Annotation:
    """
    Normalized PDF annotation from Zotero.
    
    Attributes:
        page: Page number (1-indexed, converted from Zotero's 0-indexed)
        quote: Highlighted/quoted text
        comment: User's comment/note
        color: Highlight color (hex format)
        tags: List of annotation tags
    """
    page: int
    quote: str
    comment: str | None = None
    color: str | None = None
    tags: list[str] = field(default_factory=list)


class AnnotationResolverPort(ABC):
    """Port for extracting PDF annotations from Zotero."""
    
    @abstractmethod
    def fetch_annotations(
        self,
        attachment_key: str,
        zotero_client: zotero.Zotero,
    ) -> list[Annotation]:
        """
        Fetch annotations for attachment via Web API.
        
        Args:
            attachment_key: Zotero attachment key
            zotero_client: PyZotero client instance (for Web API access)
        
        Returns:
            List of normalized Annotation objects
        
        Raises:
            ZoteroAPIError: If API request fails after retries
            ZoteroRateLimitError: If rate limit encountered (after retries)
        """
        pass
    
    @abstractmethod
    def index_annotations(
        self,
        annotations: list[Annotation],
        item_key: str,
        attachment_key: str,
        project_id: str,
        vector_index: VectorIndexPort,
        embedding_model: str,
        resolver: MetadataResolverPort | None = None,
    ) -> int:
        """
        Index annotations as separate vector points.
        
        Args:
            annotations: List of Annotation objects to index
            item_key: Parent Zotero item key
            attachment_key: Parent attachment key
            project_id: CiteLoom project ID
            vector_index: Vector index port for storage
            embedding_model: Embedding model identifier
            resolver: Optional metadata resolver for citation metadata
        
        Returns:
            Number of annotation points successfully indexed
        
        Raises:
            IndexError: If indexing fails
        """
        pass

