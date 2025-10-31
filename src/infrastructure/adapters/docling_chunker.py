"""Docling chunker adapter with optional import handling for Windows compatibility."""

from typing import Mapping, Any, Sequence

try:
    import docling
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False


class DoclingHybridChunkerAdapter:
    """Adapter for Docling heading-aware chunking (optional on Windows)."""

    def __init__(self):
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "Docling is not available on Windows (Python 3.12). "
                "deepsearch-glm dependency lacks Windows wheels for Python 3.12. "
                "Windows users should either:\n"
                "1. Use WSL (Windows Subsystem for Linux)\n"
                "2. Use Python 3.11 (not recommended - project requires 3.12)\n"
                "3. Wait for Windows support from docling/deepsearch-glm"
            )

    def chunk(
        self,
        conversion_result: Mapping[str, Any],
        policy: Any,  # ChunkingPolicy - avoiding circular import
    ) -> Sequence[Mapping[str, Any]]:
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
        
        Raises:
            ImportError: If docling is not available (Windows compatibility)
        """
        if not DOCLING_AVAILABLE:
            raise ImportError("Docling is not installed. See __init__ error for details.")
        
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
        doc_id = conversion_result.get("doc_id", "unknown")
        pages = conversion_result.get("structure", {}).get("page_map", {})
        chunks: list[dict[str, Any]] = []
        
        for page_num in sorted(pages.keys()):
            chunks.append({
                "id": f"{doc_id}:p{page_num}:0",
                "doc_id": doc_id,
                "text": conversion_result.get("plain_text", "")[:450] or f"Page {page_num} placeholder",
                "page_span": (page_num, page_num),
                "section_heading": None,
                "section_path": [],
                "chunk_idx": len(chunks),
            })
        
        return chunks if chunks else [{
            "id": f"{doc_id}:p1:0",
            "doc_id": doc_id,
            "text": "Placeholder chunk - Docling chunking not yet implemented",
            "page_span": (1, 1),
            "section_heading": None,
            "section_path": [],
            "chunk_idx": 0,
        }]
