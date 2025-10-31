# Application Layer Port Contracts

**Date**: 2025-10-31  
**Feature**: 003-framework-implementation  
**Status**: Design Complete

This document defines the protocol contracts (ports) for outbound dependencies in the application layer. All ports are defined as `Protocol` types in Python (runtime checkable interfaces). These contracts build on M2 foundation with production-hardening enhancements.

## TextConverterPort

Converts source documents into structured text with document structure, OCR support, and language detection.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TextConverterPort(Protocol):
    def convert(
        self, 
        source_path: str, 
        ocr_languages: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Convert a document at source_path into structured text and metadata.
        
        Args:
            source_path: Path to source document (PDF, DOCX, PPTX, HTML, images)
            ocr_languages: Optional OCR language codes (default: ['en', 'de'] or from Zotero metadata)
        
        Returns:
            ConversionResult-like dict with keys:
            - doc_id (str): Stable document identifier
            - structure (dict): heading_tree (hierarchical with page anchors) and page_map (page → (start_offset, end_offset))
            - plain_text (str, optional): Converted text (normalized, hyphen-repaired)
            - ocr_languages (list[str], optional): Languages used for OCR
        
        Raises:
            DocumentConversionError: If document cannot be converted
            TimeoutError: If conversion exceeds timeout (120s document, 10s per-page)
        """
        ...
```

**Implementation Requirements**:
- Must produce stable `doc_id` for same document
- Must extract heading tree hierarchy with page anchors
- Must provide page map (page number → character span tuple)
- Must enable OCR for scanned documents with configurable languages
- Must normalize text (hyphen line-break repair, whitespace normalization) preserving code/math blocks
- Must enforce timeouts: 120 seconds per document, 10 seconds per page
- Must log diagnostic information with page numbers when timeouts occur
- Must detect image-only pages and log or skip with clear indication

**Adapter**: `DoclingConverterAdapter` in `src/infrastructure/adapters/docling_converter.py`

---

## ChunkerPort

Segments converted documents into heading-aware chunks with quality filtering.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable
from domain.policy.chunking_policy import ChunkingPolicy
from domain.models.chunk import Chunk

@runtime_checkable
class ChunkerPort(Protocol):
    def chunk(
        self, 
        conversion_result: dict[str, Any], 
        policy: ChunkingPolicy
    ) -> list[Chunk]:
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
            - token_count (validated against embedding model tokenizer)
        
        Note:
            Chunks below quality threshold (50 tokens, signal-to-noise < 0.3) are filtered out.
        
        Raises:
            ChunkingError: If chunking fails (e.g., invalid structure, tokenizer mismatch)
        """
        ...
```

**Implementation Requirements**:
- Must use tokenizer matching `policy.tokenizer_id` for accurate sizing (must match embedding model tokenizer family)
- Must respect `max_tokens` (≈450) and `overlap_tokens` (≈60) from policy
- Must include `heading_context` (1-2) ancestor headings in chunks
- Must generate deterministic chunk IDs: `(doc_id, page_span/section_path, embedding_model_id, chunk_idx)`
- Must preserve section hierarchy in `section_path`
- Must filter out chunks below minimum length (50 tokens) or signal-to-noise ratio (< 0.3)
- Must validate tokenizer family matches embedding model tokenizer family

**Adapter**: `DoclingHybridChunkerAdapter` in `src/infrastructure/adapters/docling_chunker.py`

---

## MetadataResolverPort

Resolves citation metadata from Zotero library via pyzotero API with Better BibTeX citekey extraction and language field extraction.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable
from domain.models.citation_meta import CitationMeta

@runtime_checkable
class MetadataResolverPort(Protocol):
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
```

**Implementation Requirements**:
- Must use pyzotero to access Zotero library (remote via library_id/library_type/api_key, or local via local=True)
- Must extract Better BibTeX citekey via JSON-RPC API (port 23119 for Zotero, 24119 for Juris-M) when available, using `item.citationkey` method, falling back to parsing `item['data']['extra']` field for "Citation Key: citekey" pattern
- Must match by DOI first (exact match, normalized), then fallback to normalized title matching (lowercase, stripped punctuation, collapsed spaces, fuzzy threshold ≥ 0.8)
- Must extract: citekey (from Better BibTeX), title, authors, year, doi/url, tags, collections, **language** (for OCR)
- Should log `MetadataMissing` warning if unresolved (non-blocking, actionable hints)
- Must handle Unicode/diacritics in names
- Must map Zotero language codes to OCR language codes (e.g., 'en-US' → 'en')
- Must gracefully handle pyzotero API connection failures, Better BibTeX JSON-RPC unavailability, and timeout scenarios

**Adapter**: `ZoteroPyzoteroResolver` in `src/infrastructure/adapters/zotero_metadata.py` (replaces `ZoteroCslJsonResolver`)

---

## EmbeddingPort

Generates embeddings for text chunks with model binding support for Qdrant.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class EmbeddingPort(Protocol):
    @property
    def model_id(self) -> str:
        """Return the embedding model identifier (e.g., 'fastembed/BAAI/bge-small-en-v1.5')."""
        ...
    
    @property
    def tokenizer_family(self) -> str:
        """Return the tokenizer family identifier (e.g., 'minilm', 'bge') for alignment validation."""
        ...
    
    def embed(self, texts: list[str], model_id: str | None = None) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            model_id: Optional model override (defaults to self.model_id)
        
        Returns:
            List of embedding vectors (each is list[float])
        
        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...
```

**Implementation Requirements**:
- Must surface `model_id` property for write-guard checking
- Must surface `tokenizer_family` property for alignment validation
- Must support batch embedding (list of texts → list of vectors)
- Must handle text normalization consistently
- Should support local (FastEmbed) and cloud (OpenAI) models
- Must never log API keys or secrets
- Optional: Support sparse models (BM25/SPLADE/miniCOIL) via FastEmbed

**Adapters**:
- `FastEmbedAdapter` in `src/infrastructure/adapters/fastembed_embeddings.py` (default)
- `OpenAIAdapter` in `src/infrastructure/adapters/openai_embeddings.py` (optional)

---

## VectorIndexPort

Stores and retrieves chunks from vector database with named vectors and model binding.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class VectorIndexPort(Protocol):
    def upsert(
        self, 
        items: list[dict[str, Any]], 
        project_id: str, 
        model_id: str,
        sparse_model_id: str | None = None
    ) -> None:
        """
        Upsert chunks into project collection with named vectors.
        
        Args:
            items: List of chunk dicts with dense embedding, optional sparse embedding, metadata, payload
            project_id: Project identifier (determines collection)
            model_id: Dense embedding model identifier (for write-guard)
            sparse_model_id: Optional sparse model identifier (for hybrid search)
        
        Raises:
            EmbeddingModelMismatch: If model_id doesn't match collection's dense model
            ProjectNotFound: If project collection doesn't exist
        """
        ...
    
    def search(
        self, 
        query_text: str | None,
        query_vector: list[float] | None, 
        project_id: str, 
        top_k: int,
        filters: dict[str, Any] | None = None,
        use_named_vectors: bool = True
    ) -> list[dict[str, Any]]:
        """
        Vector search with project filtering (supports model binding for text queries).
        
        Args:
            query_text: Query text (if model binding enabled, can use text instead of vector)
            query_vector: Query embedding vector (if model binding not used)
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters (e.g., tags with AND semantics)
            use_named_vectors: Whether to use named vector 'dense' (default: True)
        
        Returns:
            List of hit dicts with score, payload (text, metadata, citation info)
        
        Raises:
            ProjectNotFound: If project collection doesn't exist
        """
        ...
    
    def hybrid_query(
        self,
        query_text: str,
        query_vector: list[float] | None,
        project_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Hybrid search using RRF fusion (named vectors with dense + sparse).
        
        Args:
            query_text: Query text for both sparse (BM25) and dense (if model binding) search
            query_vector: Query embedding vector (optional if model binding enabled)
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters (tags with AND semantics, optional section prefix)
        
        Returns:
            List of hit dicts with RRF-fused scores and payload
        
        Raises:
            HybridNotSupported: If hybrid not enabled for project or sparse model not bound
            ProjectNotFound: If project collection doesn't exist
        
        Note:
            Requires both dense and sparse models bound via set_model() and set_sparse_model()
            RRF fusion is automatic when both named vectors are configured
        """
        ...
    
    def ensure_collection(
        self,
        project_id: str,
        dense_model_id: str,
        sparse_model_id: str | None = None,
        on_disk_vectors: bool = False,
        on_disk_hnsw: bool = False
    ) -> None:
        """
        Ensure collection exists with named vectors and model bindings.
        
        Args:
            project_id: Project identifier
            dense_model_id: Dense embedding model identifier
            sparse_model_id: Optional sparse model identifier (for hybrid)
            on_disk_vectors: Whether to store vectors on-disk (for large projects)
            on_disk_hnsw: Whether to store HNSW index on-disk
        
        Creates collection with:
        - Named vectors: 'dense' and optionally 'sparse'
        - Model bindings via set_model() and set_sparse_model()
        - Payload indexes: keyword on project_id, doc_id, citekey, year, tags; full-text on chunk_text
        - On-disk storage flags if specified
        """
        ...
```

**Implementation Requirements**:
- Must create per-project collections with named vectors on first use
- Must bind dense model via `set_model()` for text-based queries
- Must bind sparse model via `set_sparse_model()` when hybrid enabled
- Must store `embed_model` in collection metadata
- Must enforce write-guard (block upsert if model mismatch, unless migration flag)
- Must enforce project filter in all search operations (server-side, never trust client)
- Must create payload indexes: keyword on `project_id`, `doc_id`, `citekey`, `year`, `tags`; full-text on `chunk_text` (if hybrid)
- Must support deterministic chunk IDs for idempotent upserts
- Must support on-disk vectors and HNSW for large projects
- Must use RRF fusion automatically when both dense and sparse models are bound

**Adapter**: `QdrantIndexAdapter` in `src/infrastructure/adapters/qdrant_index.py`

---

## Port Usage Summary

| Port | Use Case | Adapter | Updates in M3 |
|------|----------|---------|---------------|
| `TextConverterPort` | `IngestDocument` | `DoclingConverterAdapter` | OCR language from Zotero, timeout limits (120s/10s), structure extraction |
| `ChunkerPort` | `IngestDocument` | `DoclingHybridChunkerAdapter` | Quality filtering (50 tokens, SNR ≥ 0.3), tokenizer alignment validation |
| `MetadataResolverPort` | `IngestDocument` | `ZoteroCslJsonResolver` | Language field extraction for OCR |
| `EmbeddingPort` | `IngestDocument`, `QueryChunks` | `FastEmbedAdapter`, `OpenAIAdapter` | Tokenizer family property for validation |
| `VectorIndexPort` | `IngestDocument`, `QueryChunks`, `ReindexProject` | `QdrantIndexAdapter` | Named vectors, model binding, RRF fusion, on-disk storage |

## Testing Strategy

- **Unit tests**: Use doubles (mocks/stubs) implementing protocols
- **Integration tests**: Test adapters against real services (Docling v2, Qdrant with named vectors, Zotero files)
- **Architecture tests**: Verify all ports are implemented by adapters, no direct framework usage in application layer

