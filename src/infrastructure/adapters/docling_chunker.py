"""Docling chunker adapter with optional import handling for Windows compatibility."""

from typing import Mapping, Any, Sequence

try:
    import docling
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


class DoclingHybridChunkerAdapter:
    """
    Adapter for Docling heading-aware chunking (optional on Windows).
    
    Note: Currently uses placeholder implementation. Full Docling integration
    requires Windows support or WSL.
    """

    def __init__(self):
        if not DOCLING_AVAILABLE:
            # Don't raise error - use placeholder implementation
            pass

    def chunk(
        self,
        conversion_result: Mapping[str, Any],
        policy: Any,  # ChunkingPolicy - avoiding circular import
    ) -> Sequence[Any]:  # Returns list[Chunk]
        """
        Chunk a ConversionResult into semantic chunks according to policy.
        
        Args:
            conversion_result: ConversionResult dict from TextConverterPort
            policy: ChunkingPolicy with max_tokens, overlap, heading_context, tokenizer_id
        
        Returns:
            List of Chunk objects with:
            - Deterministic id
            - doc_id, text, page_span
            - section_heading, section_path, chunk_idx
        
        Note:
            Uses placeholder implementation when Docling is not available.
            Full implementation requires Docling library and proper heading tree extraction.
        """
        if not DOCLING_AVAILABLE:
            # Use placeholder implementation
            pass
        
        # TODO: Replace with real Docling chunking implementation
        # from docling import HybridChunker
        # chunker = HybridChunker(
        #     max_tokens=policy.max_tokens,
        #     overlap_tokens=policy.overlap_tokens,
        #     heading_context=policy.heading_context,
        # )
        # chunks = chunker.chunk(conversion_result)
        # return chunks
        
        # Placeholder implementation
        # TODO: Replace with real Docling chunking when available
        from ...domain.models.chunk import Chunk, generate_chunk_id
        
        doc_id = conversion_result.get("doc_id", "unknown")
        pages = conversion_result.get("structure", {}).get("page_map", {})
        plain_text = conversion_result.get("plain_text", "")
        chunks: list[Chunk] = []
        
        # Placeholder: create one chunk per page for now
        # Real implementation should use heading tree and tokenizer for proper chunking
        embedding_model_id = getattr(policy, "tokenizer_id", "minilm") or "minilm"
        
        if pages and plain_text:
            page_nums = sorted(pages.keys())
            for idx, page_num in enumerate(page_nums):
                # Simple page-based chunking (placeholder)
                page_start = pages[page_num]
                page_end = pages.get(page_num + 1, len(plain_text)) if page_num + 1 in pages else len(plain_text)
                chunk_text = plain_text[page_start:page_end].strip()[:2000]  # Limit text length
                
                if not chunk_text:
                    continue
                
                # Generate deterministic chunk ID
                chunk_id = generate_chunk_id(
                    doc_id=doc_id,
                    page_span=(page_num, page_num),
                    section_path=[],
                    embedding_model_id=embedding_model_id,
                    chunk_idx=idx,
                )
                
                chunk = Chunk(
                    id=chunk_id,
                    doc_id=doc_id,
                    text=chunk_text,
                    page_span=(page_num, page_num),
                    section_heading=None,
                    section_path=[],
                    chunk_idx=idx,
                )
                chunks.append(chunk)
        
        # Fallback if no pages
        if not chunks:
            chunk_id = generate_chunk_id(
                doc_id=doc_id,
                page_span=(1, 1),
                section_path=[],
                embedding_model_id=embedding_model_id,
                chunk_idx=0,
            )
            chunks.append(Chunk(
                id=chunk_id,
                doc_id=doc_id,
                text=plain_text[:2000] or "Placeholder chunk - Docling chunking not yet implemented",
                page_span=(1, 1),
                section_heading=None,
                section_path=[],
                chunk_idx=0,
            ))
        
        return chunks
