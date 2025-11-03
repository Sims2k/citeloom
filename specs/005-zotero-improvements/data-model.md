# Data Model: Comprehensive Zotero Integration Improvements

**Date**: 2025-01-27  
**Feature**: 005-zotero-improvements  
**Status**: Design Complete

---

## Overview

This document defines the domain entities, value objects, and data structures for Zotero integration improvements, including local SQLite access, full-text reuse, annotation indexing, incremental deduplication, and source routing.

**New Entities**:
- `ContentFingerprint`: Document identity for deduplication

**Enhanced Entities**:
- `DownloadManifestAttachment`: Added `source` and `content_fingerprint` fields

**Related Entities** (unchanged):
- `Chunk`: Enhanced payload with Zotero keys (`zotero.item_key`, `zotero.attachment_key`)
- `ConversionResult`: May be enhanced with fulltext provenance metadata
- `DownloadManifest`: Container for manifest items (unchanged structure)

---

## 1. ContentFingerprint (NEW)

**Purpose**: Represents a document's unique identity for incremental deduplication, enabling fast unchanged detection to skip re-processing.

**Location**: `src/domain/models/content_fingerprint.py`

**Entity Type**: Domain Entity (pure, no I/O)

```python
@dataclass(frozen=True)
class ContentFingerprint:
    """
    Content fingerprint for deduplication.
    
    Represents a document's unique identity based on:
    - Content hash (first 1MB + file size + policy versions)
    - File metadata (mtime + size) for collision protection
    - Policy versions (chunking + embedding) for invalidation
    
    Fields:
        content_hash: SHA256 hash of (file_content_preview + file_size + embedding_model_id + chunking_policy_version + embedding_policy_version)
        file_mtime: File modification time (ISO format string)
        file_size: File size in bytes
        embedding_model: Embedding model identifier
        chunking_policy_version: Chunking policy version (e.g., "1.0")
        embedding_policy_version: Embedding policy version (e.g., "1.0")
    
    Validation:
        - content_hash must be non-empty hex string
        - file_mtime must be valid ISO format datetime string
        - file_size must be >= 0
        - embedding_model must be non-empty
        - Policy versions must be non-empty strings
    """
    
    content_hash: str
    file_mtime: str  # ISO format datetime string
    file_size: int
    embedding_model: str
    chunking_policy_version: str
    embedding_policy_version: str
    
    def __post_init__(self) -> None:
        """Validate content fingerprint."""
        if not self.content_hash or len(self.content_hash) < 8:
            raise ValueError("content_hash must be non-empty hex string (>= 8 chars)")
        try:
            datetime.fromisoformat(self.file_mtime)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"file_mtime must be valid ISO format datetime string: {e}")
        if self.file_size < 0:
            raise ValueError(f"file_size must be >= 0, got {self.file_size}")
        if not self.embedding_model:
            raise ValueError("embedding_model must be non-empty")
        if not self.chunking_policy_version:
            raise ValueError("chunking_policy_version must be non-empty")
        if not self.embedding_policy_version:
            raise ValueError("embedding_policy_version must be non-empty")
    
    def matches(
        self,
        other: ContentFingerprint,
        check_metadata: bool = True,
    ) -> bool:
        """
        Check if fingerprints match (document unchanged).
        
        Args:
            other: Fingerprint to compare against
            check_metadata: If True, also verify file metadata matches (collision protection)
        
        Returns:
            True if fingerprints match (document unchanged)
        """
        if self.content_hash != other.content_hash:
            return False
        
        if check_metadata:
            if self.file_mtime != other.file_mtime or self.file_size != other.file_size:
                return False  # Hash collision protection
        
        return True
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        return {
            "content_hash": self.content_hash,
            "file_mtime": self.file_mtime,
            "file_size": self.file_size,
            "embedding_model": self.embedding_model,
            "chunking_policy_version": self.chunking_policy_version,
            "embedding_policy_version": self.embedding_policy_version,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContentFingerprint:
        """Deserialize from dict."""
        return cls(
            content_hash=data["content_hash"],
            file_mtime=data["file_mtime"],
            file_size=data["file_size"],
            embedding_model=data["embedding_model"],
            chunking_policy_version=data["chunking_policy_version"],
            embedding_policy_version=data["embedding_policy_version"],
        )
```

**Relationships**:
- Used by: `DownloadManifestAttachment` (stored in `content_fingerprint` field)
- Computed by: Infrastructure adapters (content hashing logic)

**Invariants**:
- Content hash is deterministic (same input always produces same hash)
- File metadata must match when hash matches (collision protection)
- Policy versions included to invalidate on policy changes

---

## 2. DownloadManifestAttachment (ENHANCED)

**Purpose**: Represents a downloaded file attachment with source tracking and content fingerprinting for deduplication.

**Location**: `src/domain/models/download_manifest.py`

**Enhancements**:
- Add `source: str` field (`"local" | "web"`) indicating which source provided the attachment
- Add `content_fingerprint: ContentFingerprint | None` field for deduplication

**Enhanced Structure**:
```python
@dataclass
class DownloadManifestAttachment:
    """
    Represents a downloaded file attachment in the manifest.
    
    Attributes:
        attachment_key: Zotero attachment key
        filename: Original filename
        local_path: Local file path where downloaded
        download_status: "success" | "failed" | "pending"
        file_size: File size in bytes (if download succeeded)
        error: Error message (if download failed)
        source: Source marker ("local" | "web") indicating which source provided the attachment [NEW]
        content_fingerprint: Content fingerprint for deduplication (None if not computed yet) [NEW]
    """
    
    attachment_key: str
    filename: str
    local_path: Path
    download_status: str = "pending"
    file_size: int | None = None
    error: str | None = None
    source: str | None = None  # NEW: "local" | "web"
    content_fingerprint: ContentFingerprint | None = None  # NEW
    
    def __post_init__(self) -> None:
        """Validate download manifest attachment."""
        # ... existing validations ...
        if self.source is not None and self.source not in {"local", "web"}:
            raise ValueError(f"source must be 'local' or 'web' if provided, got {self.source}")
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict."""
        result = {
            # ... existing fields ...
            "attachment_key": self.attachment_key,
            "filename": self.filename,
            "local_path": str(self.local_path),
            "download_status": self.download_status,
        }
        if self.file_size is not None:
            result["file_size"] = self.file_size
        if self.error is not None:
            result["error"] = self.error
        if self.source is not None:
            result["source"] = self.source  # NEW
        if self.content_fingerprint is not None:
            result["content_fingerprint"] = self.content_fingerprint.to_dict()  # NEW
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DownloadManifestAttachment:
        """Deserialize from dict."""
        fingerprint_data = data.get("content_fingerprint")
        fingerprint = ContentFingerprint.from_dict(fingerprint_data) if fingerprint_data else None
        
        return cls(
            attachment_key=data["attachment_key"],
            filename=data["filename"],
            local_path=Path(data["local_path"]),
            download_status=data.get("download_status", "pending"),
            file_size=data.get("file_size"),
            error=data.get("error"),
            source=data.get("source"),  # NEW
            content_fingerprint=fingerprint,  # NEW
        )
```

**Relationships**:
- Contains: `ContentFingerprint` (optional, computed after download)
- Used by: `DownloadManifestItem` (attachment collection)

**Invariants**:
- `source` must be `"local"` or `"web"` if provided
- `content_fingerprint` is None` until computed (after download and before processing)

---

## 3. Chunk Payload Enhancement

**Purpose**: Add Zotero keys to chunk payloads for traceability and targeted queries.

**Location**: Payload structure in `src/infrastructure/adapters/qdrant_index.py`

**Enhancement**: Add nested `zotero` object to chunk payload:

```python
# Enhanced chunk payload structure
chunk_payload = {
    # Existing fields...
    "project_id": project_id,
    "doc_id": doc_id,
    "section_path": section_path,
    "page_start": page_span[0],
    "page_end": page_span[1],
    "citekey": citekey,
    "chunk_text": chunk.text,
    "heading_chain": heading_chain,
    "embed_model": embedding_model_id,
    
    # NEW: Zotero traceability fields
    "zotero": {
        "item_key": item_key,           # Parent Zotero item
        "attachment_key": attachment_key,  # Source PDF attachment
    },
}
```

**Index Requirements**:
- Keyword indexes on `zotero.item_key` and `zotero.attachment_key`
- Enable fast queries: `find all chunks from item X` or `find all chunks from attachment Y`

**Relationships**:
- Stored in: Qdrant vector index (per-project collection)
- Queried by: Query use cases (with filter conditions)

**Invariants**:
- `zotero.item_key` must match parent Zotero item
- `zotero.attachment_key` must match source PDF attachment
- Both fields are optional (may be None for non-Zotero imports)

---

## 4. Annotation Point (NEW - Vector Index Payload Type)

**Purpose**: Represents a PDF annotation indexed as a separate vector point.

**Location**: Created by `AnnotationResolver`, stored in Qdrant vector index

**Payload Structure**:
```python
annotation_payload = {
    "type": "annotation",
    "project_id": project_id,
    "doc_id": doc_id,  # Same as parent document
    "chunk_text": f"{quote}\n\n{comment}" if comment else quote,
    
    # Zotero traceability
    "zotero": {
        "item_key": item_key,
        "attachment_key": attachment_key,
        "annotation": {
            "page": page_number,      # 1-indexed (converted from 0-indexed)
            "quote": highlighted_text,
            "comment": user_comment,
            "color": highlight_color,  # Hex format
            "tags": annotation_tags,   # List of strings
        },
    },
    
    # Metadata for citation
    "citekey": citekey,
    "page_start": page_number,
    "page_end": page_number,
    "title": document_title,
    "authors": authors,
    "year": year,
    
    # Standard fields
    "embed_model": embedding_model_id,
    "version": "1.0",
}
```

**Indexing Strategy**:
- Separate vector points (not attached to document chunks)
- Tagged with `type:annotation` for filtering
- Uses same embedding model as document chunks
- Stored in same collection (project-scoped)

**Relationships**:
- Created by: `AnnotationResolver.index_annotations()`
- Stored in: Qdrant vector index (same collection as document chunks)
- Queried by: Query use cases (with `type:annotation` filter)

**Invariants**:
- `type` must be `"annotation"`
- `zotero.annotation.page` must be 1-indexed (converted from Zotero's 0-indexed)
- `chunk_text` contains quote + comment (if comment exists)

---

## 5. Fulltext Provenance Metadata

**Purpose**: Track which pages came from Zotero fulltext vs Docling conversion.

**Location**: Stored in audit logs and conversion metadata (not a domain entity, but metadata tracked)

**Structure**:
```python
fulltext_provenance = {
    "source": "zotero" | "docling" | "mixed",
    "pages_from_zotero": list[int],      # Page numbers from Zotero fulltext
    "pages_from_docling": list[int],      # Page numbers from Docling conversion
    "total_pages": int,
    "zotero_coverage": float,             # Percentage of pages from Zotero (0.0 to 1.0)
}
```

**Usage**:
- Stored in audit logs for transparency
- Included in conversion result metadata (optional)
- Used for debugging and performance analysis

**Relationships**:
- Generated by: `FulltextResolver.resolve_fulltext()`
- Logged by: Audit logging infrastructure

---

## 6. Zotero Collection Hierarchy

**Purpose**: Represent Zotero collection structure with parent-child relationships.

**Location**: Returned by `LocalZoteroDbAdapter.list_collections()`, used in CLI browsing commands

**Structure** (DTO, not domain entity):
```python
collection_dict = {
    "key": str,                    # Zotero collection key
    "name": str,                   # Collection name
    "parent_collection": str | None,  # Parent collection key (None for top-level)
    "item_count": int,             # Number of items in collection (including subcollections if recursive)
    "depth": int,                  # Hierarchy depth (0 for top-level)
}
```

**Relationships**:
- Retrieved by: `LocalZoteroDbAdapter.list_collections()`
- Displayed by: CLI `list-collections` command
- Used for: Collection browsing and import planning

---

## 7. Zotero Item Preview

**Purpose**: Lightweight item information for browsing (not full metadata).

**Location**: Returned by `LocalZoteroDbAdapter.get_collection_items()`, used in CLI browsing commands

**Structure** (DTO, not domain entity):
```python
item_preview = {
    "key": str,                    # Zotero item key
    "title": str,                  # Item title
    "item_type": str,              # Zotero item type (e.g., "journalArticle", "book")
    "attachment_count": int,      # Number of PDF attachments
    "tags": list[str],            # Tag names
    "year": int | None,           # Publication year
    "creators": list[str],        # Author names (first 3)
    "date_added": str | None,     # ISO format datetime string
}
```

**Relationships**:
- Retrieved by: `LocalZoteroDbAdapter.get_collection_items()` or `browse_collection()` method
- Displayed by: CLI `browse-collection` command
- Used for: Collection exploration before import

---

## 8. Tag Usage Statistics

**Purpose**: Tag information with usage counts for browsing.

**Location**: Returned by `LocalZoteroDbAdapter.list_tags()`, used in CLI `list-tags` command

**Structure** (DTO, not domain entity):
```python
tag_info = {
    "tag": str,                    # Tag name
    "count": int,                  # Number of items with this tag
}
```

**Relationships**:
- Retrieved by: `LocalZoteroDbAdapter.list_tags()`
- Displayed by: CLI `list-tags` command
- Used for: Tag-based import planning

---

## Validation Rules Summary

### ContentFingerprint
- `content_hash`: Non-empty hex string (>= 8 chars)
- `file_mtime`: Valid ISO format datetime string
- `file_size`: >= 0
- `embedding_model`: Non-empty string
- `chunking_policy_version`: Non-empty string
- `embedding_policy_version`: Non-empty string

### DownloadManifestAttachment (Enhanced)
- `source`: Must be `"local"` or `"web"` if provided
- `content_fingerprint`: Must be valid `ContentFingerprint` instance if provided
- Existing validations remain unchanged

### Chunk Payload (Enhanced)
- `zotero.item_key`: Optional, non-empty string if provided
- `zotero.attachment_key`: Optional, non-empty string if provided
- Both fields must be present together (or both None) for Zotero imports

### Annotation Point Payload
- `type`: Must be `"annotation"`
- `zotero.annotation.page`: Must be >= 1 (1-indexed)
- `zotero.annotation.quote`: Non-empty string
- `zotero.annotation.comment`: Optional string
- `chunk_text`: Contains quote + comment (if comment exists)

---

## Entity Relationships

```
DownloadManifest
    └── DownloadManifestItem
            └── DownloadManifestAttachment
                    ├── source: "local" | "web"
                    └── content_fingerprint: ContentFingerprint

ContentFingerprint (standalone entity, used by DownloadManifestAttachment)

Chunk (enhanced payload)
    └── zotero.item_key, zotero.attachment_key

AnnotationPoint (separate vector point)
    └── zotero.item_key, zotero.attachment_key, zotero.annotation.*
```

---

## Data Flow

**Import Flow with Deduplication**:
1. Check manifest for existing `content_fingerprint`
2. Compute new `ContentFingerprint` from file + policies
3. Compare fingerprints (hash + metadata)
4. If unchanged: Skip processing, update checkpoint
5. If changed: Process document, compute new fingerprint, store in manifest

**Full-Text Reuse Flow**:
1. Query Zotero `fulltext` table for attachment key
2. Validate fulltext quality (length, structure)
3. If valid: Use fulltext as fast path (skip Docling conversion)
4. If invalid/missing: Fallback to Docling conversion
5. Track provenance (which pages from which source)
6. Chunk, embed, index (always required, regardless of text source)

**Annotation Indexing Flow**:
1. Fetch annotations via Web API (`children()` with `itemType=annotation`)
2. Normalize annotations (pageIndex → page, extract quote/comment/color/tags)
3. Create `AnnotationPoint` payload for each annotation
4. Index as separate vector points with `type:annotation` tag
5. Store in same collection as document chunks (project-scoped)

---

**Data Model Status**: ✅ Complete - All entities and enhancements defined, ready for implementation.

