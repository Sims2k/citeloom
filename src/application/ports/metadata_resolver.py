from typing import Any, Protocol, runtime_checkable

from ...domain.models.citation_meta import CitationMeta


@runtime_checkable
class MetadataResolverPort(Protocol):
    """Protocol for resolving citation metadata from Zotero library via pyzotero API."""
    
    def resolve(
        self, 
        citekey: str | None,
        doc_id: str,
        source_hint: str | None = None,
        zotero_config: dict[str, Any] | None = None
    ) -> CitationMeta | None:
        """
        Resolve citation metadata from Zotero library via pyzotero API.
        
        Args:
            citekey: Citation key hint (if available, from Better BibTeX)
            doc_id: Document identifier for matching
            source_hint: Additional source hint (title, DOI, etc.)
            zotero_config: Optional Zotero configuration dict with library_id, 
                          library_type, api_key (for remote), or local=True 
                          (for local access). If None, uses environment variables.
        
        Returns:
            CitationMeta with language field if match found, None otherwise
        
        Note:
            Non-blocking: Returns None if no match, logs MetadataMissing warning.
            Gracefully handles pyzotero API connection failures and Better BibTeX
            JSON-RPC unavailability.
        """
        ...
