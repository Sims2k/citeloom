# Port Contracts: Comprehensive Zotero Integration Improvements

**Date**: 2025-01-27  
**Feature**: 005-zotero-improvements  
**Status**: Design Complete

This document defines the port (protocol) interfaces for Zotero integration improvements, including local SQLite database access, full-text reuse, annotation extraction, source routing, and incremental deduplication. Ports are defined in the application layer and implemented by infrastructure adapters.

---

## 1. ZoteroImporterPort (ENHANCED)

**Purpose**: Interface for importing documents from Zotero collections. Enhanced to support local SQLite database access via new `LocalZoteroDbAdapter` implementation.

**Location**: `src/application/ports/zotero_importer.py`

**Status**: Extends existing interface (no breaking changes, new implementation)

**Existing Methods** (unchanged):
- `list_collections()` → `list[dict[str, Any]]`
- `get_collection_items(collection_key, include_subcollections)` → `Iterator[dict[str, Any]]`
- `get_item_attachments(item_key)` → `list[dict[str, Any]]`
- `download_attachment(item_key, attachment_key, output_path)` → `Path`
- `get_item_metadata(item_key)` → `dict[str, Any]`
- `list_tags()` → `list[dict[str, Any]]`
- `get_recent_items(limit)` → `list[dict[str, Any]]`
- `find_collection_by_name(collection_name)` → `dict[str, Any] | None`

**New Implementation Requirements**:
- **LocalZoteroDbAdapter**: Must implement all methods using SQLite queries
- **Platform detection**: Auto-detect Zotero profile per platform (Windows/macOS/Linux)
- **Immutable read-only mode**: Open SQLite DB with `?immutable=1&mode=ro` flags
- **Attachment path resolution**: Distinguish imported (`linkMode=0`) vs linked (`linkMode=1`) files
- **Fallback support**: Gracefully handle database locks, corruption, missing profiles

**Error Types**:
- `ZoteroDatabaseLockedError`: Database is locked by another process
- `ZoteroDatabaseNotFoundError`: Database file not found
- `ZoteroProfileNotFoundError`: Zotero profile directory not found
- `ZoteroPathResolutionError`: Attachment path resolution failed
- Existing: `ZoteroAPIError`, `ZoteroConnectionError`, `ZoteroRateLimitError`

**Contract** (full interface):
```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterator

class ZoteroImporterPort(ABC):
    """Port for importing documents from Zotero collections."""
    
    @abstractmethod
    def list_collections(self) -> list[dict[str, Any]]:
        """
        List all collections in Zotero library with hierarchy.
        
        Returns:
            List of collections with keys:
            - 'key': Zotero collection key
            - 'name': Collection name
            - 'parentCollection': Parent collection key (None for top-level)
            - 'item_count': Number of items in collection (optional, for local DB)
        """
        pass
    
    @abstractmethod
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Get items in a collection (generator to avoid loading all into memory).
        
        Args:
            collection_key: Zotero collection key
            include_subcollections: If True, recursively include items from subcollections
        
        Yields:
            Zotero items with keys:
            - 'key': Zotero item key
            - 'data': Dict containing title, itemType, creators, date, tags (for Web API)
            - For local DB: Direct fields (title, item_type, creators, date, tags)
        """
        pass
    
    @abstractmethod
    def get_item_attachments(
        self,
        item_key: str,
    ) -> list[dict[str, Any]]:
        """
        Get PDF attachments for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            List of attachments with keys:
            - 'key': Zotero attachment key
            - 'filename': Attachment filename
            - 'contentType': MIME type (e.g., 'application/pdf')
            - 'linkMode': 0 (imported) or 1 (linked)
            - 'path': File path (for local DB) or URL (for Web API)
        """
        pass
    
    @abstractmethod
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> Path:
        """
        Download a file attachment from Zotero.
        
        For LocalZoteroDbAdapter: Copy file from local storage to output_path.
        For Web API adapter: Download via HTTP.
        
        Args:
            item_key: Zotero item key
            attachment_key: Zotero attachment key
            output_path: Local path where file should be saved
        
        Returns:
            Path to downloaded/copied file
        
        Raises:
            ZoteroAPIError: If download fails after retries (Web API)
            ZoteroPathResolutionError: If file not found locally (local DB)
            FileNotFoundError: If file doesn't exist at resolved path
        """
        pass
    
    @abstractmethod
    def get_item_metadata(
        self,
        item_key: str,
    ) -> dict[str, Any]:
        """
        Get full metadata for a Zotero item.
        
        Args:
            item_key: Zotero item key
        
        Returns:
            Item metadata dict with keys: title, creators (authors), date (year), DOI, tags, collections
        """
        pass
    
    @abstractmethod
    def list_tags(self) -> list[dict[str, Any]]:
        """
        List all tags used in Zotero library.
        
        Returns:
            List of tags with keys:
            - 'tag': Tag name
            - 'count': Number of items with this tag (optional, for local DB)
            - 'meta': Dict with numItems count (for Web API)
        """
        pass
    
    @abstractmethod
    def get_recent_items(
        self,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get recently added items to Zotero library.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of items sorted by dateAdded (descending) with keys: 'key', 'title', 'dateAdded'
        """
        pass
    
    @abstractmethod
    def find_collection_by_name(
        self,
        collection_name: str,
    ) -> dict[str, Any] | None:
        """
        Find collection by name (case-insensitive partial match).
        
        Args:
            collection_name: Collection name to search for
        
        Returns:
            Collection dict with keys: 'key', 'name', or None if not found
        """
        pass
    
    # NEW: Optional method for local DB adapters to check if attachment can be resolved locally
    def can_resolve_locally(self, attachment_key: str) -> bool:
        """
        Check if attachment can be resolved locally (for source routing).
        
        Optional method - only implemented by LocalZoteroDbAdapter.
        Web API adapter returns False or raises NotImplementedError.
        
        Args:
            attachment_key: Zotero attachment key
        
        Returns:
            True if attachment can be resolved locally, False otherwise
        """
        raise NotImplementedError("can_resolve_locally() not implemented by this adapter")
```

---

## 2. FulltextResolverPort (NEW)

**Purpose**: Interface for resolving document full-text content, preferring Zotero cached fulltext when available.

**Location**: `src/application/ports/fulltext_resolver.py` (new file)

**Status**: New port for full-text resolution abstraction

**Contract**:
```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

@dataclass
class FulltextResult:
    """
    Result of full-text resolution.
    
    Attributes:
        text: Full text content (from Zotero or Docling)
        source: "zotero" | "docling" | "mixed"
        pages_from_zotero: List of page numbers from Zotero fulltext (for mixed provenance)
        pages_from_docling: List of page numbers from Docling conversion (for mixed provenance)
        zotero_quality_score: Quality score for Zotero fulltext (0.0 to 1.0, None if not used)
    """
    text: str
    source: str  # "zotero" | "docling" | "mixed"
    pages_from_zotero: list[int] = field(default_factory=list)
    pages_from_docling: list[int] = field(default_factory=list)
    zotero_quality_score: float | None = None


class FulltextResolverPort(ABC):
    """Port for resolving document full-text content."""
    
    @abstractmethod
    def resolve_fulltext(
        self,
        attachment_key: str,
        file_path: Path,
        prefer_zotero: bool = True,
        min_length: int = 100,
    ) -> FulltextResult:
        """
        Resolve full-text content with preference strategy.
        
        Checks Zotero fulltext table first if prefer_zotero=True, validates quality,
        falls back to Docling conversion if fulltext unavailable or low-quality.
        Supports page-level mixed provenance (some pages from Zotero, some from Docling).
        
        Args:
            attachment_key: Zotero attachment key (for querying fulltext table)
            file_path: Local file path (for Docling conversion fallback)
            prefer_zotero: If True, prefer Zotero fulltext when available
            min_length: Minimum text length for quality validation
        
        Returns:
            FulltextResult with text, source, and provenance metadata
        
        Raises:
            DocumentConversionError: If Docling conversion fails
            ZoteroDatabaseError: If database access fails
        """
        pass
    
    @abstractmethod
    def get_zotero_fulltext(
        self,
        attachment_key: str,
    ) -> str | None:
        """
        Get fulltext from Zotero fulltext table (if available).
        
        Args:
            attachment_key: Zotero attachment key
        
        Returns:
            Fulltext string or None if not available
        """
        pass
```

**Implementation**: `ZoteroFulltextResolverAdapter` in `src/infrastructure/adapters/zotero_fulltext_resolver.py`

**Error Types**:
- `ZoteroFulltextNotFoundError`: Fulltext not available in database
- `ZoteroFulltextQualityError`: Fulltext quality too low (fallback to Docling)
- `DocumentConversionError`: Docling conversion failed (from converter port)

---

## 3. AnnotationResolverPort (NEW)

**Purpose**: Interface for extracting and indexing PDF annotations from Zotero.

**Location**: `src/application/ports/annotation_resolver.py` (new file)

**Status**: New port for annotation extraction abstraction

**Contract**:
```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from pyzotero import zotero

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
    ) -> int:
        """
        Index annotations as separate vector points.
        
        Args:
            annotations: List of Annotation objects to index
            item_key: Parent Zotero item key
            attachment_key: Parent attachment key
            project_id: CiteLoom project ID
            vector_index: Vector index port for storage
        
        Returns:
            Number of annotation points successfully indexed
        
        Raises:
            IndexError: If indexing fails
        """
        pass
```

**Implementation**: `ZoteroAnnotationResolverAdapter` in `src/infrastructure/adapters/zotero_annotation_resolver.py`

**Error Types**:
- `ZoteroAnnotationNotFoundError`: No annotations found (non-error, returns empty list)
- `ZoteroAPIError`: Web API request failed
- `ZoteroRateLimitError`: Rate limit encountered (after retries)

---

## 4. ZoteroSourceRouter (Application Service)

**Purpose**: Application service that routes Zotero operations to local database or Web API based on strategy mode.

**Location**: `src/application/services/zotero_source_router.py` (new file)

**Status**: Application service (not a port, but orchestrates ports)

**Contract**:
```python
from typing import Literal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Iterator

Strategy = Literal["local-first", "web-first", "auto", "local-only", "web-only"]

class ZoteroSourceRouter:
    """
    Routes Zotero operations to local database or Web API based on strategy.
    
    Not a port interface - application service that orchestrates adapters.
    """
    
    def __init__(
        self,
        local_adapter: ZoteroImporterPort | None,
        web_adapter: ZoteroImporterPort,
        strategy: Strategy = "auto",
    ):
        """
        Initialize router with adapters and strategy.
        
        Args:
            local_adapter: Local SQLite adapter (None if unavailable)
            web_adapter: Web API adapter (required)
            strategy: Routing strategy mode
        """
        pass
    
    def list_collections(self) -> list[dict[str, Any]]:
        """
        Route collection listing based on strategy.
        
        Strategy behaviors:
        - local-first: Try local, fallback to web if unavailable
        - web-first: Use web, fallback to local on rate limit
        - auto: Prefer local if available, else web
        - local-only: Only local, raise if unavailable
        - web-only: Only web
        
        Returns:
            List of collections
        """
        pass
    
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Route item fetching based on strategy."""
        pass
    
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> tuple[Path, str]:
        """
        Route download with fallback logic.
        
        Returns:
            Tuple of (file_path, source_marker) where source_marker is "local" or "web"
        """
        pass
    
    def is_local_available(self) -> bool:
        """Check if local database adapter is available."""
        pass
```

**Strategy Behaviors**:
- **`local-first`**: Check each file individually via local DB, fallback to Web API per-file if missing
- **`web-first`**: Use Web API primarily, fallback to local DB on rate limits or file unavailability
- **`auto`**: Smart selection based on availability (prefer local if available and files exist, prefer web if local unavailable)
- **`local-only`**: Strict mode - only local DB, raise if unavailable (for debugging)
- **`web-only`**: Strict mode - only Web API, no fallback (backward compatible)

---

## 5. TextConverterPort (ENHANCED - Optional Integration)

**Purpose**: Existing converter port. May be enhanced to integrate with FulltextResolver for seamless fallback.

**Location**: `src/application/ports/converter.py`

**Status**: May add optional parameter for fulltext preference, or FulltextResolver handles integration

**Contract** (unchanged, FulltextResolver handles integration):
```python
@runtime_checkable
class TextConverterPort(Protocol):
    def convert(
        self,
        source_path: str,
        ocr_languages: list[str] | None = None,
    ) -> Mapping[str, Any]:
        """
        Convert a document at source_path into structured text and metadata.
        
        Note: FulltextResolver integrates with this port for fallback.
        FulltextResolver checks Zotero fulltext first, then calls convert() if needed.
        
        Args:
            source_path: Path to source document (PDF, DOCX, PPTX, HTML, images)
            ocr_languages: Optional OCR language codes
        
        Returns:
            ConversionResult-like dict with keys: doc_id, structure, plain_text, ocr_languages
        """
        ...
```

---

## 6. VectorIndexPort (ENHANCED)

**Purpose**: Existing vector index port. Enhanced to support annotation indexing and Zotero key indexes.

**Location**: `src/application/ports/vector_index.py`

**Status**: Enhanced payload schema and index requirements

**Enhancements**:
1. **Payload Schema**: Add `zotero.item_key` and `zotero.attachment_key` fields
2. **Index Creation**: Create keyword indexes on `zotero.item_key` and `zotero.attachment_key`
3. **Annotation Support**: Support `type:annotation` payloads for annotation points

**Contract** (enhancements only):
```python
class VectorIndexPort(ABC):
    """Port for vector storage and retrieval."""
    
    # Existing methods unchanged...
    
    def ensure_collection(
        self,
        project_id: str,
        embedding_model: str,
    ) -> None:
        """
        Ensure collection exists with proper schema.
        
        Enhanced to create keyword indexes on:
        - zotero.item_key
        - zotero.attachment_key
        
        These indexes enable fast queries filtered by Zotero keys.
        """
        pass
    
    def upsert_chunks(
        self,
        project_id: str,
        chunks: list[Chunk],
        payloads: list[dict[str, Any]],
    ) -> None:
        """
        Upsert chunks with payloads.
        
        Enhanced payload structure:
        {
            # Existing fields...
            "zotero": {
                "item_key": str | None,        # Parent Zotero item
                "attachment_key": str | None,   # Source PDF attachment
            },
        }
        """
        pass
    
    def upsert_annotations(
        self,
        project_id: str,
        annotations: list[Annotation],
        payloads: list[dict[str, Any]],
    ) -> None:
        """
        Upsert annotation points as separate vectors.
        
        Payload structure:
        {
            "type": "annotation",
            "project_id": str,
            "chunk_text": str,  # quote + comment
            "zotero": {
                "item_key": str,
                "attachment_key": str,
                "annotation": {
                    "page": int,
                    "quote": str,
                    "comment": str | None,
                    "color": str | None,
                    "tags": list[str],
                },
            },
            # ... other metadata fields
        }
        """
        pass
```

---

## 7. Content Fingerprinting (Domain Service)

**Purpose**: Domain service for computing content fingerprints (not a port, pure domain logic).

**Location**: `src/domain/services/content_fingerprint.py` (new file)

**Status**: Pure domain service (no I/O)

**Contract**:
```python
from pathlib import Path
from ..models.content_fingerprint import ContentFingerprint

class ContentFingerprintService:
    """Domain service for computing content fingerprints."""
    
    @staticmethod
    def compute_fingerprint(
        file_path: Path,
        embedding_model: str,
        chunking_policy_version: str,
        embedding_policy_version: str,
        preview_size: int = 1024 * 1024,  # 1MB default
    ) -> ContentFingerprint:
        """
        Compute content fingerprint for deduplication.
        
        Args:
            file_path: Path to file
            embedding_model: Embedding model identifier
            chunking_policy_version: Chunking policy version (e.g., "1.0")
            embedding_policy_version: Embedding policy version (e.g., "1.0")
            preview_size: Size of file content preview for hashing (default 1MB)
        
        Returns:
            ContentFingerprint with hash and metadata
        
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be read
        """
        pass
    
    @staticmethod
    def is_unchanged(
        stored: ContentFingerprint,
        computed: ContentFingerprint,
    ) -> bool:
        """
        Check if document is unchanged (skip re-processing).
        
        Compares content hash and file metadata.
        
        Args:
            stored: Stored fingerprint from manifest
            computed: Newly computed fingerprint
        
        Returns:
            True if unchanged (skip processing), False if changed (re-process)
        """
        pass
```

---

## Error Type Definitions

**New Error Types** (in `src/domain/errors.py`):

```python
class ZoteroDatabaseLockedError(ZoteroConnectionError):
    """Zotero database is locked by another process."""
    pass

class ZoteroDatabaseNotFoundError(ZoteroConnectionError):
    """Zotero database file not found."""
    pass

class ZoteroProfileNotFoundError(ZoteroConnectionError):
    """Zotero profile directory not found."""
    pass

class ZoteroPathResolutionError(ZoteroAPIError):
    """Attachment path resolution failed."""
    pass

class ZoteroFulltextNotFoundError(ZoteroAPIError):
    """Fulltext not available in Zotero database."""
    pass

class ZoteroFulltextQualityError(ZoteroAPIError):
    """Fulltext quality too low (fallback to Docling)."""
    pass

class ZoteroAnnotationNotFoundError(ZoteroAPIError):
    """No annotations found for attachment (non-fatal)."""
    pass
```

---

## Implementation Responsibilities

### Infrastructure Adapters

**LocalZoteroDbAdapter** (implements `ZoteroImporterPort`):
- Platform-aware profile detection (Windows/macOS/Linux)
- SQLite immutable read-only access (`?immutable=1&mode=ro`)
- SQL queries for collections, items, attachments
- Attachment path resolution (imported vs linked)
- Graceful fallback to Web API on errors

**ZoteroFulltextResolverAdapter** (implements `FulltextResolverPort`):
- Query Zotero `fulltext` table via SQLite
- Quality validation (length, structure checks)
- Integration with DoclingConverterAdapter for fallback
- Page-level mixed provenance tracking

**ZoteroAnnotationResolverAdapter** (implements `AnnotationResolverPort`):
- Fetch annotations via Web API (`children()` method)
- Normalize annotation data (pageIndex → page, extract fields)
- Index annotations as separate vector points
- Retry logic with exponential backoff

**QdrantIndexAdapter** (implements `VectorIndexPort`, enhanced):
- Create keyword indexes on `zotero.item_key` and `zotero.attachment_key`
- Support annotation payloads with `type:annotation`
- Enhanced payload schema with Zotero keys

### Application Services

**ZoteroSourceRouter**:
- Strategy-based routing logic
- Per-file fallback handling
- Source marker tracking in manifests
- Error handling and fallback strategies

---

**Contract Status**: ✅ Complete - All port interfaces defined, ready for implementation.

