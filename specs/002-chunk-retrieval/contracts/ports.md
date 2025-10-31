# Application Layer Port Contracts

**Date**: 2025-01-27  
**Feature**: 002-chunk-retrieval  
**Status**: Design Complete

This document defines the protocol contracts (ports) for outbound dependencies in the application layer. All ports are defined as `Protocol` types in Python (runtime checkable interfaces).

## TextConverterPort

Converts source documents into structured text with document structure.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class TextConverterPort(Protocol):
    def convert(self, source_path: str) -> dict[str, Any]:
        """
        Convert a document at source_path into structured text and metadata.
        
        Args:
            source_path: Path to source document (PDF, etc.)
        
        Returns:
            ConversionResult-like dict with keys:
            - doc_id (str): Stable document identifier
            - structure (dict): heading_tree and page_map
            - plain_text (str, optional): Converted text
        
        Raises:
            DocumentConversionError: If document cannot be converted
        """
        ...
```

**Implementation Requirements**:
- Must produce stable `doc_id` for same document
- Must extract heading tree hierarchy
- Must provide page map (page → text offsets)
- Should enable OCR for scanned documents
- Should normalize whitespace and fix hyphen breaks

**Adapter**: `DoclingConverterAdapter` in `src/infrastructure/adapters/docling_converter.py`

---

## ChunkerPort

Segments converted documents into heading-aware chunks.

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
        
        Raises:
            ChunkingError: If chunking fails (e.g., invalid structure)
        """
        ...
```

**Implementation Requirements**:
- Must use tokenizer matching `policy.tokenizer_id` for accurate sizing
- Must respect `max_tokens` and `overlap_tokens` from policy
- Must include `heading_context` ancestor headings in chunks
- Must generate deterministic chunk IDs
- Must preserve section hierarchy in `section_path`

**Adapter**: `DoclingHybridChunkerAdapter` in `src/infrastructure/adapters/docling_chunker.py`

---

## MetadataResolverPort

Resolves citation metadata from reference management exports.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable
from domain.models.citation_meta import CitationMeta

@runtime_checkable
class MetadataResolverPort(Protocol):
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
```

**Implementation Requirements**:
- Must match by DOI first (if available in source_hint)
- Must fallback to normalized title matching (fuzzy threshold)
- Must extract: citekey, title, authors, year, doi/url, tags, collections
- Should log `MetadataMissing` warning if unresolved (non-blocking)
- Must handle Unicode/diacritics in names

**Adapter**: `ZoteroCslJsonResolver` in `src/infrastructure/adapters/zotero_metadata.py`

---

## EmbeddingPort

Generates embeddings for text chunks.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class EmbeddingPort(Protocol):
    @property
    def model_id(self) -> str:
        """Return the embedding model identifier (e.g., 'fastembed/all-MiniLM-L6-v2')."""
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
- Must support batch embedding (list of texts → list of vectors)
- Must handle text normalization consistently
- Should support local (FastEmbed) and cloud (OpenAI) models
- Must never log API keys or secrets

**Adapters**:
- `FastEmbedAdapter` in `src/infrastructure/adapters/fastembed_embeddings.py` (default)
- `OpenAIAdapter` in `src/infrastructure/adapters/openai_embeddings.py` (optional)

---

## VectorIndexPort

Stores and retrieves chunks from vector database.

**Protocol Definition**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class VectorIndexPort(Protocol):
    def upsert(
        self, 
        items: list[dict[str, Any]], 
        project_id: str, 
        model_id: str
    ) -> None:
        """
        Upsert chunks into project collection.
        
        Args:
            items: List of chunk dicts with embedding, metadata, payload
            project_id: Project identifier (determines collection)
            model_id: Embedding model identifier (for write-guard)
        
        Raises:
            EmbeddingModelMismatch: If model_id doesn't match collection's model
            ProjectNotFound: If project collection doesn't exist
        """
        ...
    
    def search(
        self, 
        query_vector: list[float], 
        project_id: str, 
        top_k: int,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Vector search with project filtering.
        
        Args:
            query_vector: Query embedding vector
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters (e.g., tags)
        
        Returns:
            List of hit dicts with score, payload (text, metadata, citation info)
        
        Raises:
            ProjectNotFound: If project collection doesn't exist
        """
        ...
    
    def hybrid_query(
        self,
        query_text: str,
        query_vector: list[float],
        project_id: str,
        top_k: int,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Hybrid search (full-text + vector fusion).
        
        Args:
            query_text: Query text for BM25/full-text search
            query_vector: Query embedding vector
            project_id: Project identifier (mandatory filter)
            top_k: Maximum number of results
            filters: Additional Qdrant filters
        
        Returns:
            List of hit dicts with combined scores and payload
        
        Raises:
            HybridNotSupported: If hybrid not enabled for project
            ProjectNotFound: If project collection doesn't exist
        
        Note:
            Optional method - only required if hybrid_enabled=True
        """
        ...
```

**Implementation Requirements**:
- Must create per-project collections on first use
- Must store `embed_model` in collection metadata
- Must enforce write-guard (block upsert if model mismatch, unless migration flag)
- Must enforce project filter in all search operations
- Must create payload indexes: keyword on `project`, `zotero.tags`, full-text on `fulltext` (if hybrid)
- Must support deterministic chunk IDs for idempotent upserts

**Adapter**: `QdrantIndexAdapter` in `src/infrastructure/adapters/qdrant_index.py`

---

## Port Usage Summary

| Port | Use Case | Adapter |
|------|----------|---------|
| `TextConverterPort` | `IngestDocument` | `DoclingConverterAdapter` |
| `ChunkerPort` | `IngestDocument` | `DoclingHybridChunkerAdapter` |
| `MetadataResolverPort` | `IngestDocument` | `ZoteroCslJsonResolver` |
| `EmbeddingPort` | `IngestDocument`, `QueryChunks` | `FastEmbedAdapter`, `OpenAIAdapter` |
| `VectorIndexPort` | `IngestDocument`, `QueryChunks`, `ReindexProject` | `QdrantIndexAdapter` |

## Testing Strategy

- **Unit tests**: Use doubles (mocks/stubs) implementing protocols
- **Integration tests**: Test adapters against real services (Docling, Qdrant, Zotero files)
- **Architecture tests**: Verify all ports are implemented by adapters, no direct framework usage in application layer

