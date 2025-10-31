from typing import Protocol, runtime_checkable, Any

from ...domain.policy.chunking_policy import ChunkingPolicy
from ...domain.models.chunk import Chunk


@runtime_checkable
class ChunkerPort(Protocol):
    """Protocol for chunking ConversionResult into semantic chunks."""
    
    def chunk(
        self, 
        conversion_result: dict[str, Any], 
        policy: ChunkingPolicy
    ) -> list[Chunk]:
        """
        Chunk a ConversionResult into semantic chunks according to policy.
        
        Args:
            conversion_result: ConversionResult dict from TextConverterPort
            policy: ChunkingPolicy with max_tokens, overlap_tokens, heading_context, tokenizer_id
        
        Returns:
            List of Chunk objects with:
            - Deterministic id
            - doc_id, text, page_span
            - section_heading, section_path, chunk_idx
        
        Raises:
            ChunkingError: If chunking fails (e.g., invalid structure)
        """
        ...
