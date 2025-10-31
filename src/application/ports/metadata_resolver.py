from typing import Protocol, runtime_checkable

from domain.models.citation_meta import CitationMeta


@runtime_checkable
class MetadataResolverPort(Protocol):
    """Protocol for resolving citation metadata from reference management exports."""
    
    def resolve(
        self, 
        citekey: str | None,
        references_path: str,
        doc_id: str,
        source_hint: str | None = None
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
            Non-blocking: Returns None if no match, doesn't raise errors
        """
        ...
