from typing import Protocol, runtime_checkable, Any

from ...domain.policy.chunking_policy import ChunkingPolicy
from ...domain.models.chunk import Chunk


@runtime_checkable
class ChunkerPort(Protocol):
    """
    Protocol for chunking ConversionResult into semantic chunks with quality filtering.
    
    Implementation Requirements:
    - Must use tokenizer matching policy.tokenizer_id for accurate sizing (must match embedding model tokenizer family)
    - Must respect max_tokens (≈450) and overlap_tokens (≈60) from policy
    - Must include heading_context (1-2) ancestor headings in chunks
    - Must generate deterministic chunk IDs: (doc_id, page_span/section_path, embedding_model_id, chunk_idx)
    - Must preserve section hierarchy in section_path
    - Must filter out chunks below minimum length (50 tokens) or signal-to-noise ratio (< 0.3)
    - Must validate tokenizer family matches embedding model tokenizer family
    """
    
    def chunk(
        self, 
        conversion_result: dict[str, Any], 
        policy: ChunkingPolicy
    ) -> list[Chunk]:
        """
        Chunk a ConversionResult into semantic chunks according to policy.
        
        Args:
            conversion_result: ConversionResult dict from TextConverterPort with:
                - doc_id (str): Document identifier
                - structure (dict): Contains heading_tree and page_map
                - plain_text (str, optional): Converted text
            policy: ChunkingPolicy with max_tokens, overlap_tokens, heading_context, tokenizer_id,
                   min_chunk_length, min_signal_to_noise
        
        Returns:
            List of Chunk objects with:
            - Deterministic id
            - doc_id, text, page_span
            - section_heading, section_path, chunk_idx
            - token_count (validated against embedding model tokenizer)
            - signal_to_noise_ratio (quality metric)
        
        Note:
            Chunks below quality threshold (minimum 50 tokens, signal-to-noise ratio ≥ 0.3) 
            are filtered out with appropriate logging.
        
        Raises:
            ChunkingError: If chunking fails (e.g., invalid structure, tokenizer mismatch)
        """
        ...
