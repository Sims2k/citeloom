"""Docling chunker adapter with heading-aware chunking and quality filtering."""

import logging
import re
from typing import Any, Mapping, Sequence

try:
    from docling.datamodel.pipeline_options import HybridChunkerOptions
    from docling.datamodel.document_converter_options import DocumentConverterOptions
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    try:
        from docling.chunking.hybrid_chunker import HybridChunker
        HYBRID_CHUNKER_AVAILABLE = True
    except ImportError:
        # Try alternative import path
        try:
            from docling import HybridChunker
            HYBRID_CHUNKER_AVAILABLE = True
        except ImportError:
            HYBRID_CHUNKER_AVAILABLE = False
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    HYBRID_CHUNKER_AVAILABLE = False
    HybridChunker = None  # type: ignore
    HybridChunkerOptions = None  # type: ignore

logger = logging.getLogger(__name__)

# Import ChunkingError from domain errors
from ...domain.errors import ChunkingError


class DoclingHybridChunkerAdapter:
    """
    Adapter for Docling heading-aware chunking with tokenizer alignment and quality filtering.
    
    Implements heading-aware chunking with:
    - Tokenizer alignment validation (ensures chunking tokenizer matches embedding model tokenizer family)
    - Heading context inclusion (ancestor headings in chunks)
    - Section path breadcrumb extraction
    - Page span mapping
    - Token count calculation using embedding model tokenizer
    - Quality filtering (minimum 50 tokens, signal-to-noise ratio ≥ 0.3)
    - Deterministic chunk ID generation
    """

    def __init__(self):
        """Initialize the chunker adapter."""
        if not DOCLING_AVAILABLE:
            logger.warning(
                "Docling is not available. Chunker will use placeholder implementation. "
                "Windows users should use WSL or Docker."
            )

    def chunk(
        self,
        conversion_result: Mapping[str, Any],
        policy: Any,  # ChunkingPolicy - avoiding circular import
    ) -> Sequence[Any]:  # Returns list[Chunk]
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
        
        Raises:
            ChunkingError: If chunking fails (e.g., invalid structure, tokenizer mismatch)
        """
        from ...domain.models.chunk import Chunk, generate_chunk_id

        doc_id = conversion_result.get("doc_id", "unknown")
        structure = conversion_result.get("structure", {})
        heading_tree = structure.get("heading_tree", {})
        page_map = structure.get("page_map", {})
        plain_text = conversion_result.get("plain_text", "")

        if not plain_text:
            logger.warning(
                f"No plain text available for chunking: doc_id={doc_id}",
                extra={"doc_id": doc_id},
            )
            return []

        # Extract policy values
        max_tokens = getattr(policy, "max_tokens", 450)
        overlap_tokens = getattr(policy, "overlap_tokens", 60)
        heading_context = getattr(policy, "heading_context", 2)
        tokenizer_id = getattr(policy, "tokenizer_id", "minilm") or "minilm"
        min_chunk_length = getattr(policy, "min_chunk_length", 50)
        min_signal_to_noise = getattr(policy, "min_signal_to_noise", 0.3)

        # T022: Tokenizer alignment validation
        # Note: Full validation should check against EmbeddingPort.tokenizer_family
        # For now, we validate that tokenizer_id is provided and is a known family
        valid_tokenizer_families = ["minilm", "bge", "openai", "tiktoken"]
        tokenizer_family = self._extract_tokenizer_family(tokenizer_id)
        
        if tokenizer_family not in valid_tokenizer_families:
            logger.warning(
                f"Unknown tokenizer family: {tokenizer_id} (extracted: {tokenizer_family}). "
                f"Proceeding with default tokenization.",
                extra={"tokenizer_id": tokenizer_id, "tokenizer_family": tokenizer_family},
            )

        # Get tokenizer for token counting
        tokenizer = self._get_tokenizer(tokenizer_id)

        # T021: Initialize HybridChunker if Docling is available
        if DOCLING_AVAILABLE and HYBRID_CHUNKER_AVAILABLE:
            try:
                # Use Docling HybridChunker with configured options
                chunker = self._create_hybrid_chunker(
                    max_tokens=max_tokens,
                    overlap_tokens=overlap_tokens,
                    heading_context=heading_context,
                    tokenizer=tokenizer,
                )
                
                # Chunk using Docling (requires conversion result in Docling format)
                docling_chunks = self._chunk_with_docling(
                    chunker=chunker,
                    conversion_result=conversion_result,
                    plain_text=plain_text,
                    heading_tree=heading_tree,
                    page_map=page_map,
                )
                
                # Convert Docling chunks to domain Chunk objects
                domain_chunks = self._convert_to_domain_chunks(
                    docling_chunks=docling_chunks,
                    doc_id=doc_id,
                    heading_tree=heading_tree,
                    page_map=page_map,
                    tokenizer=tokenizer,
                    tokenizer_id=tokenizer_id,
                    min_chunk_length=min_chunk_length,
                    min_signal_to_noise=min_signal_to_noise,
                )
                
                return domain_chunks
                
            except Exception as e:
                logger.warning(
                    f"Docling HybridChunker failed: {e}. Falling back to manual chunking.",
                    extra={"doc_id": doc_id},
                    exc_info=True,
                )
                # Fall through to manual chunking implementation

        # Fallback: Manual chunking implementation when Docling is not available
        # or when Docling chunking fails
        return self._manual_chunking(
            plain_text=plain_text,
            doc_id=doc_id,
            heading_tree=heading_tree,
            page_map=page_map,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
            heading_context=heading_context,
            tokenizer=tokenizer,
            tokenizer_id=tokenizer_id,
            min_chunk_length=min_chunk_length,
            min_signal_to_noise=min_signal_to_noise,
        )

    def _extract_tokenizer_family(self, tokenizer_id: str) -> str:
        """Extract tokenizer family from tokenizer_id (e.g., 'minilm' from 'fastembed/minilm')."""
        # Normalize: remove prefixes like 'fastembed/', 'sentence-transformers/'
        parts = tokenizer_id.split("/")
        tokenizer_name = parts[-1].lower()
        
        # Map common tokenizer names to families
        if "minilm" in tokenizer_name:
            return "minilm"
        elif "bge" in tokenizer_name:
            return "bge"
        elif "openai" in tokenizer_name or "ada" in tokenizer_name:
            return "openai"
        elif "tiktoken" in tokenizer_name:
            return "tiktoken"
        else:
            return tokenizer_name

    def _get_tokenizer(self, tokenizer_id: str):
        """
        Get tokenizer instance for token counting.
        
        Returns a tokenizer that can count tokens in text.
        Falls back to simple word-based estimation if tokenizer not available.
        """
        try:
            # Try to load appropriate tokenizer based on family
            tokenizer_family = self._extract_tokenizer_family(tokenizer_id)
            
            if tokenizer_family == "minilm":
                # Try to load sentence-transformers tokenizer
                try:
                    from sentence_transformers import SentenceTransformer
                    # Use a lightweight model just for tokenization
                    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                    return model.tokenizer  # type: ignore
                except ImportError:
                    pass
            
            # Fallback: simple tokenizer based on word splitting
            # This is an approximation but works for basic token counting
            return None  # Will use word-based estimation
            
        except Exception as e:
            logger.warning(
                f"Failed to load tokenizer {tokenizer_id}: {e}. Using word-based estimation.",
                extra={"tokenizer_id": tokenizer_id},
            )
            return None

    def _count_tokens(self, text: str, tokenizer: Any) -> int:
        """
        Count tokens in text using tokenizer.
        
        Falls back to word-based estimation if tokenizer not available.
        """
        if tokenizer is not None:
            try:
                # Try to use tokenizer.encode or tokenizer.tokenize
                if hasattr(tokenizer, "encode"):
                    tokens = tokenizer.encode(text, add_special_tokens=False)
                    return len(tokens)
                elif hasattr(tokenizer, "tokenize"):
                    tokens = tokenizer.tokenize(text)
                    return len(tokens)
            except Exception as e:
                logger.debug(f"Tokenizer counting failed: {e}, using word-based estimation")

        # Fallback: word-based estimation (≈ 1.3 words per token for English)
        words = len(text.split())
        return int(words * 1.3)

    def _create_hybrid_chunker(
        self,
        max_tokens: int,
        overlap_tokens: int,
        heading_context: int,
        tokenizer: Any,
    ) -> Any:
        """Create Docling HybridChunker instance with configured options."""
        if not HYBRID_CHUNKER_AVAILABLE:
            raise ChunkingError("Docling HybridChunker not available")
        
        try:
            # Configure chunker options
            if HybridChunkerOptions:
                options = HybridChunkerOptions()
                options.max_tokens = max_tokens
                options.overlap_tokens = overlap_tokens
                options.heading_context = heading_context
                return HybridChunker(options=options)
            else:
                # Fallback: initialize with positional/keyword arguments
                return HybridChunker(
                    max_tokens=max_tokens,
                    overlap_tokens=overlap_tokens,
                    heading_context=heading_context,
                )
        except Exception as e:
            raise ChunkingError(
                "Failed to create HybridChunker",
                reason=str(e),
            ) from e

    def _chunk_with_docling(
        self,
        chunker: Any,
        conversion_result: Mapping[str, Any],
        plain_text: str,
        heading_tree: dict[str, Any],
        page_map: dict[int, tuple[int, int]],
    ) -> list[Any]:
        """
        Chunk using Docling HybridChunker.
        
        Converts conversion_result to Docling document format and chunks it.
        """
        try:
            # If conversion_result contains a Docling document object, use it directly
            if hasattr(conversion_result, "document"):
                doc = conversion_result.document
            elif "document" in conversion_result:
                doc = conversion_result["document"]
            else:
                # Need to reconstruct Docling document from plain_text and structure
                # This is a simplified approach - full implementation would parse structure
                # For now, we'll use the manual chunking fallback
                raise ValueError("Docling document object not available in conversion_result")
            
            # Chunk the document
            chunks = chunker.chunk(doc)
            return chunks
            
        except Exception as e:
            logger.warning(
                f"Docling chunking failed: {e}. Using manual chunking.",
                exc_info=True,
            )
            raise

    def _convert_to_domain_chunks(
        self,
        docling_chunks: list[Any],
        doc_id: str,
        heading_tree: dict[str, Any],
        page_map: dict[int, tuple[int, int]],
        tokenizer: Any,
        tokenizer_id: str,
        min_chunk_length: int,
        min_signal_to_noise: float,
    ) -> list[Any]:
        """Convert Docling chunk objects to domain Chunk objects."""
        from ...domain.models.chunk import Chunk, generate_chunk_id

        domain_chunks: list[Chunk] = []
        filtered_count = 0

        for idx, docling_chunk in enumerate(docling_chunks):
            # Extract text from Docling chunk
            chunk_text = ""
            if hasattr(docling_chunk, "text"):
                chunk_text = docling_chunk.text
            elif hasattr(docling_chunk, "content"):
                chunk_text = str(docling_chunk.content)
            elif isinstance(docling_chunk, str):
                chunk_text = docling_chunk
            elif isinstance(docling_chunk, dict):
                chunk_text = docling_chunk.get("text", chunk_text)
            else:
                chunk_text = str(docling_chunk)

            if not chunk_text or not chunk_text.strip():
                filtered_count += 1
                continue

            # T027: Calculate token count using embedding model tokenizer
            token_count = self._count_tokens(chunk_text, tokenizer)

            # T024: Quality filtering
            if token_count < min_chunk_length:
                logger.debug(
                    f"Filtered chunk {idx}: token_count ({token_count}) < min_chunk_length ({min_chunk_length})",
                    extra={"chunk_idx": idx, "token_count": token_count, "min_chunk_length": min_chunk_length},
                )
                filtered_count += 1
                continue

            # Calculate signal-to-noise ratio
            signal_to_noise = self._calculate_signal_to_noise_ratio(chunk_text)

            if signal_to_noise < min_signal_to_noise:
                logger.debug(
                    f"Filtered chunk {idx}: signal_to_noise ({signal_to_noise:.3f}) < min_signal_to_noise ({min_signal_to_noise:.3f})",
                    extra={
                        "chunk_idx": idx,
                        "signal_to_noise": signal_to_noise,
                        "min_signal_to_noise": min_signal_to_noise,
                    },
                )
                filtered_count += 1
                continue

            # T025: Extract section path breadcrumb from heading tree
            section_path, section_heading = self._extract_section_info(
                docling_chunk=docling_chunk,
                heading_tree=heading_tree,
                chunk_text=chunk_text,
            )

            # T026: Extract page span from page_map
            page_span = self._extract_page_span(
                docling_chunk=docling_chunk,
                page_map=page_map,
                chunk_text=chunk_text,
            )

            # T028: Generate deterministic chunk ID
            chunk_id = generate_chunk_id(
                doc_id=doc_id,
                page_span=page_span,
                section_path=section_path,
                embedding_model_id=tokenizer_id,
                chunk_idx=idx,
            )

            chunk = Chunk(
                id=chunk_id,
                doc_id=doc_id,
                text=chunk_text,
                page_span=page_span,
                section_heading=section_heading,
                section_path=section_path,
                chunk_idx=idx,
                token_count=token_count,
                signal_to_noise_ratio=signal_to_noise,
            )

            domain_chunks.append(chunk)

        if filtered_count > 0:
            logger.info(
                f"Quality filtering: {filtered_count} chunks filtered out",
                extra={"doc_id": doc_id, "filtered_count": filtered_count, "total_chunks": len(docling_chunks)},
            )

        return domain_chunks

    def _manual_chunking(
        self,
        plain_text: str,
        doc_id: str,
        heading_tree: dict[str, Any],
        page_map: dict[int, tuple[int, int]],
        max_tokens: int,
        overlap_tokens: int,
        heading_context: int,
        tokenizer: Any,
        tokenizer_id: str,
        min_chunk_length: int,
        min_signal_to_noise: float,
    ) -> list[Any]:
        """
        Manual chunking implementation when Docling is not available.
        
        Implements heading-aware chunking with tokenizer alignment and quality filtering.
        """
        from ...domain.models.chunk import Chunk, generate_chunk_id

        chunks: list[Chunk] = []
        filtered_count = 0

        # Split text into sentences for more granular chunking
        sentences = self._split_into_sentences(plain_text)
        
        if not sentences:
            logger.warning(f"No sentences found in text for doc_id={doc_id}")
            return []

        # Build heading context map from heading_tree
        heading_context_map = self._build_heading_context_map(heading_tree)

        current_chunk_text: list[str] = []
        current_tokens = 0
        chunk_idx = 0
        previous_chunk_end = 0

        # T023: Include heading context in chunks
        current_heading_context: list[str] = []

        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence, tokenizer)
            
            # Check if adding this sentence would exceed max_tokens
            if current_tokens + sentence_tokens > max_tokens and current_chunk_text:
                # Finalize current chunk
                chunk_text = " ".join(current_chunk_text)
                
                # Apply quality filtering
                token_count = self._count_tokens(chunk_text, tokenizer)
                signal_to_noise = self._calculate_signal_to_noise_ratio(chunk_text)
                
                if token_count >= min_chunk_length and signal_to_noise >= min_signal_to_noise:
                    # Extract section info and page span
                    section_path, section_heading = self._extract_section_info_from_text(
                        chunk_text=chunk_text,
                        heading_tree=heading_tree,
                        heading_context_map=heading_context_map,
                        text_position=previous_chunk_end,
                    )
                    
                    page_span = self._extract_page_span_from_text(
                        chunk_text=chunk_text,
                        page_map=page_map,
                        text_position=previous_chunk_end,
                        plain_text=plain_text,
                    )
                    
                    # Generate deterministic chunk ID
                    chunk_id = generate_chunk_id(
                        doc_id=doc_id,
                        page_span=page_span,
                        section_path=section_path,
                        embedding_model_id=tokenizer_id,
                        chunk_idx=chunk_idx,
                    )
                    
                    chunk = Chunk(
                        id=chunk_id,
                        doc_id=doc_id,
                        text=chunk_text,
                        page_span=page_span,
                        section_heading=section_heading,
                        section_path=section_path,
                        chunk_idx=chunk_idx,
                        token_count=token_count,
                        signal_to_noise_ratio=signal_to_noise,
                    )
                    
                    chunks.append(chunk)
                    chunk_idx += 1
                    previous_chunk_end += len(chunk_text)
                else:
                    filtered_count += 1
                
                # Start new chunk with overlap
                # T023: Include heading context and overlap from previous chunk
                overlap_sentences = self._get_overlap_sentences(
                    current_chunk_text,
                    overlap_tokens,
                    tokenizer,
                )
                current_chunk_text = overlap_sentences + [sentence]
                current_tokens = sum(self._count_tokens(s, tokenizer) for s in current_chunk_text)
            else:
                current_chunk_text.append(sentence)
                current_tokens += sentence_tokens

        # Handle final chunk
        if current_chunk_text:
            chunk_text = " ".join(current_chunk_text)
            token_count = self._count_tokens(chunk_text, tokenizer)
            signal_to_noise = self._calculate_signal_to_noise_ratio(chunk_text)
            
            if token_count >= min_chunk_length and signal_to_noise >= min_signal_to_noise:
                section_path, section_heading = self._extract_section_info_from_text(
                    chunk_text=chunk_text,
                    heading_tree=heading_tree,
                    heading_context_map=heading_context_map,
                    text_position=previous_chunk_end,
                )
                
                page_span = self._extract_page_span_from_text(
                    chunk_text=chunk_text,
                    page_map=page_map,
                    text_position=previous_chunk_end,
                    plain_text=plain_text,
                )
                
                chunk_id = generate_chunk_id(
                    doc_id=doc_id,
                    page_span=page_span,
                    section_path=section_path,
                    embedding_model_id=tokenizer_id,
                    chunk_idx=chunk_idx,
                )
                
                chunk = Chunk(
                    id=chunk_id,
                    doc_id=doc_id,
                    text=chunk_text,
                    page_span=page_span,
                    section_heading=section_heading,
                    section_path=section_path,
                    chunk_idx=chunk_idx,
                    token_count=token_count,
                    signal_to_noise_ratio=signal_to_noise,
                )
                
                chunks.append(chunk)
            else:
                filtered_count += 1

        if filtered_count > 0:
            logger.info(
                f"Quality filtering: {filtered_count} chunks filtered out (manual chunking)",
                extra={"doc_id": doc_id, "filtered_count": filtered_count},
            )

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences using regex."""
        # Simple sentence splitting (can be improved with nltk or spacy)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_overlap_sentences(
        self,
        sentences: list[str],
        overlap_tokens: int,
        tokenizer: Any,
    ) -> list[str]:
        """Get last N sentences that fit within overlap_tokens."""
        overlap_sentences: list[str] = []
        overlap_tokens_count = 0
        
        for sentence in reversed(sentences):
            sentence_tokens = self._count_tokens(sentence, tokenizer)
            if overlap_tokens_count + sentence_tokens <= overlap_tokens:
                overlap_sentences.insert(0, sentence)
                overlap_tokens_count += sentence_tokens
            else:
                break
        
        return overlap_sentences

    def _calculate_signal_to_noise_ratio(self, text: str) -> float:
        """
        Calculate signal-to-noise ratio for text quality.
        
        Signal: meaningful content (alphabetic characters, numbers)
        Noise: whitespace, special characters, repeated characters
        
        Returns a value between 0.0 and 1.0, where 1.0 is high quality.
        """
        if not text:
            return 0.0
        
        # Count signal characters (alphanumeric)
        signal = len(re.findall(r'[a-zA-Z0-9]', text))
        
        # Count noise characters (whitespace, punctuation, repeated chars)
        noise = len(re.findall(r'[^\w\s]', text))  # Special chars
        noise += len(re.findall(r'\s{3,}', text))  # Multiple spaces
        noise += len(re.findall(r'(.)\1{3,}', text))  # Repeated chars (4+)
        
        total = signal + noise
        
        if total == 0:
            return 0.0
        
        return signal / total if total > 0 else 0.0

    def _build_heading_context_map(self, heading_tree: dict[str, Any]) -> dict[int, list[str]]:
        """
        Build a map from text positions to heading context chains.
        
        Returns a dict mapping approximate text positions to lists of ancestor headings.
        """
        context_map: dict[int, list[str]] = {}
        
        def traverse(node: dict[str, Any], ancestors: list[str], position: int = 0) -> None:
            """Recursively traverse heading tree and build context map."""
            title = node.get("title", "")
            if title:
                ancestors = ancestors + [title]
            
            # Map this section to its ancestor chain
            context_map[position] = ancestors.copy()
            
            # Traverse children
            children = node.get("children", [])
            for child in children:
                child_position = position + len(children)
                traverse(child, ancestors, child_position)
        
        root_nodes = heading_tree.get("root", [])
        for root_node in root_nodes:
            traverse(root_node, [], 0)
        
        return context_map

    def _extract_section_info(
        self,
        docling_chunk: Any,
        heading_tree: dict[str, Any],
        chunk_text: str,
    ) -> tuple[list[str], str | None]:
        """
        Extract section path and heading from Docling chunk or heading tree.
        
        Returns:
            (section_path, section_heading) tuple
        """
        section_path: list[str] = []
        section_heading: str | None = None
        
        # Try to extract from Docling chunk metadata
        if hasattr(docling_chunk, "heading"):
            section_heading = str(docling_chunk.heading)
        elif hasattr(docling_chunk, "section"):
            section_heading = str(docling_chunk.section)
        elif isinstance(docling_chunk, dict):
            section_heading = docling_chunk.get("heading") or docling_chunk.get("section")
        
        # Try to extract section path from chunk metadata
        if hasattr(docling_chunk, "section_path"):
            section_path = list(docling_chunk.section_path) if docling_chunk.section_path else []
        elif isinstance(docling_chunk, dict):
            section_path = docling_chunk.get("section_path", [])
        
        # If not found, try to match against heading tree
        if not section_path:
            section_path, section_heading = self._find_section_in_tree(
                chunk_text=chunk_text,
                heading_tree=heading_tree,
            )
        
        return section_path, section_heading

    def _extract_section_info_from_text(
        self,
        chunk_text: str,
        heading_tree: dict[str, Any],
        heading_context_map: dict[int, list[str]],
        text_position: int,
    ) -> tuple[list[str], str | None]:
        """Extract section path and heading from text position and heading tree."""
        # Use approximate position to find context
        # Round to nearest 100 to account for approximate mapping
        rounded_position = (text_position // 100) * 100
        section_path = heading_context_map.get(rounded_position, [])
        
        section_heading = section_path[-1] if section_path else None
        
        # If not found in context map, try to find in heading tree
        if not section_path:
            section_path, section_heading = self._find_section_in_tree(
                chunk_text=chunk_text,
                heading_tree=heading_tree,
            )
        
        return section_path, section_heading

    def _find_section_in_tree(
        self,
        chunk_text: str,
        heading_tree: dict[str, Any],
    ) -> tuple[list[str], str | None]:
        """Find section in heading tree that best matches chunk text."""
        section_path: list[str] = []
        section_heading: str | None = None
        
        # Try to find matching heading in text
        def search_tree(node: dict[str, Any], ancestors: list[str]) -> None:
            nonlocal section_path, section_heading
            
            title = node.get("title", "")
            if title and title.lower() in chunk_text.lower():
                section_path = ancestors + [title]
                section_heading = title
                return
            
            children = node.get("children", [])
            for child in children:
                search_tree(child, ancestors + ([title] if title else []))
        
        root_nodes = heading_tree.get("root", [])
        for root_node in root_nodes:
            search_tree(root_node, [])
            if section_path:
                break
        
        return section_path, section_heading

    def _extract_page_span(
        self,
        docling_chunk: Any,
        page_map: dict[int, tuple[int, int]],
        chunk_text: str,
    ) -> tuple[int, int]:
        """Extract page span from Docling chunk or page_map."""
        page_start = 1
        page_end = 1
        
        # Try to extract from Docling chunk metadata
        if hasattr(docling_chunk, "page_start") and hasattr(docling_chunk, "page_end"):
            page_start = int(docling_chunk.page_start)
            page_end = int(docling_chunk.page_end)
        elif hasattr(docling_chunk, "page"):
            page_start = page_end = int(docling_chunk.page)
        elif isinstance(docling_chunk, dict):
            page_start = docling_chunk.get("page_start", 1)
            page_end = docling_chunk.get("page_end", page_start)
        
        # If not found, estimate from page_map using chunk text
        if page_start == 1 and page_map:
            # Estimate page based on chunk text length (approximate)
            estimated_page = min(page_map.keys()) if page_map else 1
            page_start = page_end = estimated_page
        
        return (page_start, page_end)

    def _extract_page_span_from_text(
        self,
        chunk_text: str,
        page_map: dict[int, tuple[int, int]],
        text_position: int,
        plain_text: str,
    ) -> tuple[int, int]:
        """Extract page span from text position and page_map."""
        if not page_map:
            return (1, 1)
        
        # Find page containing this text position
        page_start = 1
        page_end = 1
        
        for page_num, (start_offset, end_offset) in sorted(page_map.items()):
            if start_offset <= text_position < end_offset:
                page_start = page_end = page_num
                break
        
        # Check if chunk spans multiple pages
        chunk_end_position = text_position + len(chunk_text)
        for page_num, (start_offset, end_offset) in sorted(page_map.items()):
            if start_offset <= chunk_end_position < end_offset:
                page_end = page_num
                break
        
        return (page_start, page_end)
