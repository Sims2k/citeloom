# Critical Analysis: Zotero Implementation Improvements

**Date**: 2025-01-27  
**Status**: Analysis & Roadmap  
**Related**: zotero-mcp patterns, specs/004-zotero-batch-import

---

## Executive Summary

This document provides a critical analysis of CiteLoom's current Zotero integration compared to the zotero-mcp server patterns, identifies functional gaps, and proposes a comprehensive improvement roadmap. The analysis reveals that while CiteLoom has a solid foundation with Web API integration, local SQLite access, full-text reuse, annotation support, and embedding governance would significantly enhance performance, offline capability, and retrieval quality.

**Key Findings**:
- ✅ **Strong foundation**: Web API integration, two-phase import, checkpointing, tag filtering
- ⚠️ **Missing**: Local SQLite read-only access for instant browsing and offline use
- ⚠️ **Missing**: Full-text reuse from Zotero (avoids redundant OCR)
- ⚠️ **Missing**: PDF annotation extraction and indexing
- ⚠️ **Missing**: Embedding model/provider governance and mismatch detection
- ⚠️ **Missing**: Incremental deduplication based on content hashes
- ⚠️ **Missing**: Comprehensive library browsing tools (offline-capable)

---

## 1. Current Implementation Assessment

### 1.1 Architecture Overview

CiteLoom implements Zotero integration via:

- **`ZoteroImporterAdapter`** (Infrastructure): PyZotero-based adapter implementing `ZoteroImporterPort`
- **`ZoteroPyzoteroResolver`** (Infrastructure): Metadata resolution via Better BibTeX JSON-RPC
- **`batch_import_from_zotero`** (Application): Two-phase orchestration (download → process)
- **Clean Architecture**: Clear separation of ports/adapters, domain models, use cases

**Strengths**:
- Rate limiting (0.5s min interval, 2 req/sec)
- Retry with exponential backoff (3 retries, 1s base, 30s max)
- Local API fallback (`local=True` via pyzotero)
- Two-phase import with manifest persistence
- Checkpointing for resumability
- Tag-based filtering (OR include, ANY exclude)
- Collection/subcollection recursion

### 1.2 Current Limitations

#### **No Local SQLite Access**
- Relies solely on PyZotero API (local HTTP server or Web API)
- Cannot browse library structure when offline
- Subject to API rate limits even with local API
- No instant file path resolution for imported attachments

#### **No Full-Text Reuse**
- Always runs Docling conversion/OCR, even if Zotero already extracted text
- Wastes CPU and time for documents already processed by Zotero

#### **No Annotation Support**
- Does not extract PDF annotations/highlights from Zotero
- Missing high-signal content that improves retrieval quality

#### **No Embedding Mismatch Detection**
- Write-guard exists but doesn't surface friendly diagnostics
- No collection-level embedding model tracking visible to users
- Risk of silent recall degradation on model changes

#### **No Incremental Deduplication**
- Re-processes unchanged documents on re-runs
- No content-based fingerprinting to skip unchanged files

#### **Limited Library Browsing**
- Collection listing exists but not deeply integrated
- No offline-capable browsing without API access
- Missing hierarchical collection view with counts

---

## 2. Zotero-MCP Pattern Analysis

### 2.1 What zotero-mcp Does Well

#### **Local Database Access (`local_db.py`)**
- Opens `zotero.sqlite` read-only/immutable (`?immutable=1&mode=ro`)
- Traverses collections → items → attachments without network calls
- Platform-aware profile detection (Windows/macOS/Linux)
- Graceful fallback to Web API when DB locked/unavailable

**Key Implementation Patterns** (from [zotero-mcp/local_db.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py)):
- **SQLite URI mode**: `f"file:{db_path}?immutable=1&mode=ro"` ensures read-only immutable access
- **Platform detection**: Checks `%APPDATA%\Zotero\Profiles\` (Windows), `~/Library/Application Support/Zotero/Profiles/` (macOS), `~/.zotero/zotero/Profiles/` (Linux)
- **Profile discovery**: Reads `profiles.ini` or detects default profile automatically
- **SQL queries**: Direct joins on `collections`, `collectionItems`, `items`, `itemAttachments` tables
- **JSON field parsing**: Extracts metadata from `items.data` JSONB field
- **Attachment path resolution**: Queries `itemAttachments.linkMode` to distinguish imported vs linked

#### **Attachment Resolution (`pdfannots_downloader.py`)**
- Distinguishes **imported** vs **linked** files
- Resolves imported: `storage/<ATTACHMENT_KEY>/<filename>`
- Resolves linked: absolute path from DB
- Validates existence and handles missing files gracefully

**Key Implementation Patterns** (from [zotero-mcp/pdfannots_downloader.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/pdfannots_downloader.py)):
- **Link mode detection**: `linkMode == 0` (imported) vs `linkMode == 1` (linked)
- **Storage path construction**: `{storageDir}/storage/{itemKey}/{filename}` for imported files
- **Path validation**: Checks file existence before returning path
- **Fallback logic**: Attempts multiple path patterns if primary resolution fails

#### **Full-Text Reuse**
- Checks Zotero `fulltext` table for cached text
- Falls back to extractors only when needed
- Significant speedup for documents already in Zotero

**Key Implementation Patterns**:
- **Fulltext table query**: `SELECT text FROM fulltext WHERE itemID = ?` joins to `items` via `itemID`
- **Quality check**: Validates fulltext is not empty and has reasonable length
- **Page extraction**: Can extract per-page text from fulltext `text` field when structured
- **Fallback trigger**: If fulltext missing/empty, triggers Docling or other extractor

#### **Annotation Extraction**
- Fetches annotation items (`itemType=annotation`) per attachment
- Normalizes: page, quote, comment, color, tags
- Stores as separate indexed points with `type:annotation` tag

**Key Implementation Patterns** (from [zotero-mcp/tools.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/tools.py)):
- **Annotation query**: Filters items by `itemType=annotation` and `parentItem=attachmentKey`
- **Data normalization**: Extracts from `annotation.data` JSON field:
  - `pageIndex` → `page` (0-indexed, convert to 1-indexed)
  - `text` → `quote` (highlighted text)
  - `comment` → `comment` (user notes)
  - `color` → `color` (highlight color hex)
  - `tags` → `tags[]` (annotation tags)
- **Indexing strategy**: Creates separate vector points with:
  - `type: "annotation"`
  - `zotero.item_key`: parent item key
  - `zotero.attachment_key`: parent attachment key
  - `zotero.annotation.page`: page number
  - Text: `quote + (comment if present)` for embedding

#### **Embedding Governance**
- Tracks `embed_model` and `provider` per collection
- Warns on mismatch: "Collection exists with different embedding function"
- Blocks writes unless migration flag set

**Key Implementation Patterns**:
- **Model tracking**: Stores `embedding_model` and `embedding_provider` in collection metadata or separate config table
- **Mismatch detection**: On collection init, checks stored model vs requested model
- **Error message**: `f"Collection '{name}' exists with embedding model '{stored}'. Requested '{requested}'. Use --force-rebuild to migrate."`
- **Migration flag**: `--force-rebuild` or `force_rebuild=True` bypasses write-guard after user confirmation

#### **Incremental Indexing**
- Uses deterministic IDs based on content + embedding model
- Skips re-processing unchanged items
- Fast unchanged checks via content hash

**Key Implementation Patterns**:
- **Content hashing**: `hashlib.sha256(file_content + embedding_model_id + chunking_policy_version).hexdigest()`
- **Fingerprint storage**: Stores `content_hash` and `file_mtime + file_size` in manifest
- **Skip logic**: Before processing, checks if `content_hash` matches and file hasn't changed
- **Policy versioning**: Includes chunking/embedding policy versions in hash to invalidate on policy changes

---

## 3. Gap Analysis & Improvement Opportunities

### 3.1 Critical Gaps (P0)

#### **GAP-001: Local SQLite Database Access**
**Impact**: High — Enables offline browsing, instant structure access, zero rate limits

**What's Missing**:
- Read-only SQLite adapter for `zotero.sqlite`
- Platform-aware profile directory detection
- Collection/item/attachment traversal via SQL queries
- Immutable read mode to avoid locks when Zotero is running

**Benefits**:
- Instant collection browsing (no API round-trips)
- Offline capability (works without internet)
- Zero rate limits
- Faster attachment path resolution

**Implementation Complexity**: Medium  
**Estimated Effort**: 2-3 days

---

#### **GAP-002: Full-Text Reuse from Zotero**
**Impact**: High — Reduces processing time by 50-80% for documents already in Zotero

**What's Missing**:
- Detection of Zotero `fulltext` table entries
- Preference for Zotero fulltext over Docling when available
- Page-level fallback to Docling for missing pages
- Audit trail showing which pages came from Zotero vs Docling

**Benefits**:
- Faster imports (skip OCR for already-processed documents)
- Reduced CPU usage
- Better user experience for large libraries

**Implementation Complexity**: Medium  
**Estimated Effort**: 1-2 days

---

### 3.2 High-Value Gaps (P1)

#### **GAP-003: PDF Annotation Extraction & Indexing**
**Impact**: High — Annotations are high-signal snippets that dramatically improve retrieval

**What's Missing**:
- Fetch annotation items via Web API (`itemType=annotation`)
- Normalize annotations: page, quote, comment, color, tags
- Option 1: Attach as chunk metadata (`doc.annotations[]`)
- Option 2: Index as separate points with `type:annotation` tag (preferred)

**Benefits**:
- Better retrieval quality (annotations contain key insights)
- Enable "only annotations" queries via hybrid search
- Richer citation context in LLM responses

**Implementation Complexity**: Medium  
**Estimated Effort**: 2-3 days

---

#### **GAP-004: Embedding Model Governance & Diagnostics**
**Impact**: Medium — Prevents silent recall degradation on model changes

**What's Missing**:
- Store `embed_model` and `provider` at collection creation
- Friendly mismatch diagnostics ("Collection bound to X, you requested Y")
- CLI/MCP `inspect` command showing bound model
- Clear migration path messaging

**Benefits**:
- Prevents accidental model mismatches
- Better user experience with clear error messages
- Maintains collection coherence over time

**Implementation Complexity**: Low  
**Estimated Effort**: 1 day

---

#### **GAP-005: Incremental Deduplication**
**Impact**: Medium — Avoids re-processing unchanged documents on re-runs

**What's Missing**:
- Deterministic `doc_id` based on content hash + embedding model + policy version
- File fingerprint (mtime + size or content hash) in manifest
- Fast "unchanged" checks before extraction/embedding
- Skip processing if doc unchanged and policies match

**Benefits**:
- Faster re-runs on large collections
- Reduces unnecessary computation
- Better resource efficiency

**Implementation Complexity**: Medium  
**Estimated Effort**: 1-2 days

---

### 3.3 Enhancement Opportunities (P2)

#### **GAP-006: Enhanced Library Browsing (Offline-Capable)**
**Impact**: Medium — Better UX for exploring library before import

**What's Missing**:
- Hierarchical collection view with item counts
- Collection browsing with first N items preview
- Tag browsing with usage counts
- Recent items view
- All working offline via local DB

**Benefits**:
- Better import planning
- Verify collection selection before large imports
- Works without internet connection

**Implementation Complexity**: Low  
**Estimated Effort**: 1 day

---

#### **GAP-007: Enhanced Source Router**
**Impact**: Medium — Flexible local/web source selection

**What's Missing**:
- Strategy modes: `local-first`, `web-first`, `auto`, `local-only`, `web-only`
- Automatic fallback logic
- Source markers in manifest (`source: "local" | "web"`)

**Benefits**:
- Optimized workflows (local for speed, web for completeness)
- Better error handling (fallback between sources)
- User control over data source

**Implementation Complexity**: Medium  
**Estimated Effort**: 1-2 days

---

#### **GAP-008: Payload Enrichment with Zotero Keys**
**Impact**: Low — Enables targeted queries by item/attachment key

**What's Missing**:
- Add `zotero.item_key` and `zotero.attachment_key` to payload
- Index both fields for fast queries
- Enable "find everything from this paper" queries

**Benefits**:
- Better traceability to Zotero items
- Targeted retrieval by item/attachment
- Improved debugging and audit

**Implementation Complexity**: Low  
**Estimated Effort**: 0.5 days

---

## 4. Implementation Roadmap

### 4.1 Phase 1: Foundation (Weeks 1-2)

#### **1.1 Local SQLite Adapter** ⭐ **CRITICAL**
**Task**: Implement `LocalZoteroDbAdapter` in Infrastructure layer

**Requirements**:
- Open SQLite read-only/immutable: `file:/path/to/zotero.sqlite?immutable=1&mode=ro`
- Platform detection: Windows (`%APPDATA%\Zotero\...`), macOS (`~/Library/...`), Linux (`~/.zotero/...`)
- Implement `ZoteroImporterPort` methods:
  - `list_collections()`: SQL query on `collections` table with hierarchy
  - `get_collection_items()`: Join `collectionItems` → `items` → `itemAttachments`
  - `get_item_attachments()`: Query `itemAttachments` filtered by `itemType=attachment`
  - `get_item_metadata()`: Extract from `items.data` JSON field
- Resolve attachment paths:
  - **Imported**: `{storageDir}/storage/{attachmentKey}/{filename}`
  - **Linked**: Absolute path from `itemAttachments.path` field
- Fallback to Web API on lock/unavailable DB
- Error handling: Clear diagnostics when DB locked or profile not found

**Files to Create/Modify**:
- `src/infrastructure/adapters/zotero_local_db.py` (new)
- `src/infrastructure/adapters/zotero_importer.py` (extend or refactor)

**Tests**:
- Test ro/immutable open on each platform
- Test fallback when DB locked
- Test path resolution (imported vs linked)
- Test collection/item/attachment traversal matches PyZotero parity

**Dependencies**: None (SQLite3 in stdlib)

---

#### **1.2 Source Router** ⭐ **CRITICAL**
**Task**: Implement `ZoteroSourceRouter` in Application layer

**Requirements**:
- Strategy selection: `local-first`, `web-first`, `auto`, `local-only`, `web-only`
- Implement routing logic:
  - `local-first`: Try local DB; fallback to Web API for missing files
  - `web-first`: Try Web API; fallback to local DB for rate limits
  - `auto`: Smart selection based on availability
  - `local-only`/`web-only`: Strict modes for debugging
- Preserve existing tag filters, collection recursion, two-phase workflow
- Add source markers to manifest (`source: "local" | "web"`)

**Files to Create/Modify**:
- `src/application/services/zotero_source_router.py` (new)
- `src/application/use_cases/batch_import_from_zotero.py` (integrate router)

**Tests**:
- Test each strategy mode
- Test fallback logic
- Test source markers in manifest

**Dependencies**: Requires LocalZoteroDbAdapter

---

### 4.2 Phase 2: Performance & Quality (Weeks 3-4)

#### **2.1 Full-Text Resolver** ⭐ **HIGH VALUE**
**Task**: Implement `FulltextResolver` to prefer Zotero fulltext

**Requirements**:
- Check Zotero `fulltext` table for attachment key
- If present and quality acceptable, use as fast path
- If missing/low-quality, fall back to Docling
- Page-level fallback: Mixed provenance (some pages from Zotero, some from Docling)
- Audit trail: Mark which pages came from which source
- Policy toggle: `prefer_zotero_fulltext=true|false` (default `true`)

**Files to Create/Modify**:
- `src/infrastructure/adapters/zotero_fulltext_resolver.py` (new)
- `src/infrastructure/adapters/docling_converter.py` (integrate resolver)
- `src/application/use_cases/ingest_document.py` (use resolver)

**Tests**:
- Test fulltext preference when available
- Test fallback to Docling on missing/thin text
- Test page-level mixed provenance
- Test audit trail accuracy

**Dependencies**: Requires LocalZoteroDbAdapter

---

#### **2.2 Annotation Resolver** ⭐ **HIGH VALUE**
**Task**: Implement annotation extraction and indexing

**Requirements**:
- Fetch annotations via Web API (`itemType=annotation`, filter by `parentItem`)
- Normalize annotations: page, quote, comment, color, tags
- **Option 1** (recommended): Index as separate points with:
  - `type: "annotation"`
  - `zotero.annotation.page`, `zotero.annotation.quote`, `zotero.annotation.comment`
  - Tag with `type:annotation` for filtering
- **Option 2**: Attach as chunk metadata (`doc.annotations[]`)
- Optional flag: `include_annotations=true|false` (default `false` for now)
- Graceful skip when API unavailable

**Files to Create/Modify**:
- `src/infrastructure/adapters/zotero_annotation_resolver.py` (new)
- `src/application/use_cases/batch_import_from_zotero.py` (integrate resolver)
- `src/infrastructure/adapters/qdrant_index.py` (support annotation payload schema)

**Tests**:
- Test annotation extraction when enabled
- Test graceful skip when disabled
- Test indexing as separate points
- Test retrieval of annotation-only queries

**Dependencies**: Requires Web API (local API doesn't support annotations well)

---

#### **2.3 Incremental Deduplication** ⭐ **HIGH VALUE**
**Task**: Implement content-based fingerprinting and skip logic

**Requirements**:
- Deterministic `doc_id`: `hash(attachment_content_hash + embedding_model_id + policy_version)`
- Store fingerprint in manifest: `file_mtime + file_size` or `content_hash`
- Fast unchanged check: Compare fingerprint before extraction/embedding
- Skip processing if unchanged and policies match
- Policy version tracking: Include chunking/embedding policy versions in hash

**Files to Create/Modify**:
- `src/domain/models/download_manifest.py` (add fingerprint fields)
- `src/application/use_cases/batch_import_from_zotero.py` (add fingerprinting logic)
- `src/application/use_cases/ingest_document.py` (add unchanged check)

**Tests**:
- Test unchanged detection on re-runs
- Test re-processing when content changes
- Test re-processing when policy changes
- Test fingerprint accuracy

**Dependencies**: None (hashing in stdlib)

---

### 4.3 Phase 3: Governance & UX (Week 5)

#### **3.1 Embedding Governance Enhancement** ⭐ **MEDIUM VALUE**
**Task**: Enhance write-guard with friendly diagnostics

**Requirements**:
- Store `embed_model` and `provider` at collection creation (already done, but make visible)
- Friendly mismatch error: "Collection 'X' is bound to embedding model 'Y'. You requested 'Z'. Use `reindex --force-rebuild` or switch back to 'Y'."
- CLI command: `citeloom inspect project --show-embedding-model`
- MCP tool: Expose embedding model in status/inspect responses

**Files to Create/Modify**:
- `src/infrastructure/adapters/qdrant_index.py` (enhance error messages)
- `src/infrastructure/cli/commands/inspect.py` (new or extend)
- `src/infrastructure/mcp/tools.py` (add embedding model to status)

**Tests**:
- Test mismatch detection and error message
- Test inspect command output
- Test MCP status response

**Dependencies**: None (builds on existing write-guard)

---

#### **3.2 Library Browsing Tools** ⭐ **MEDIUM VALUE**
**Task**: Enhance collection/item browsing with offline support

**Requirements**:
- Hierarchical collection view: `list_collections` with subcollection hierarchy and item counts
- Collection browsing: `browse_collection` with first N items, attachment counts, tags
- Tag browsing: `list_tags` with usage counts
- Recent items: `recent_items` with dateAdded sorting
- All working offline via local DB when available

**Files to Create/Modify**:
- `src/infrastructure/cli/commands/zotero.py` (extend with new commands)
- `src/infrastructure/mcp/tools.py` (add browsing tools)
- `src/application/ports/zotero_importer.py` (extend port if needed)

**Tests**:
- Test collection hierarchy display
- Test offline browsing capability
- Test tag/list/recent items views

**Dependencies**: Requires LocalZoteroDbAdapter

---

#### **3.3 Payload Enrichment** ⭐ **LOW VALUE**
**Task**: Add Zotero keys to payload and indexes

**Requirements**:
- Add `zotero.item_key` and `zotero.attachment_key` to Qdrant payload
- Create keyword indexes on both fields
- Enable queries: "Find all chunks from item X" or "Find all chunks from attachment Y"

**Files to Create/Modify**:
- `src/infrastructure/adapters/qdrant_index.py` (add fields to payload, create indexes)
- `src/application/use_cases/batch_import_from_zotero.py` (pass keys to payload)

**Tests**:
- Test keys in payload
- Test index queries by item/attachment key

**Dependencies**: None

---

### 4.4 Configuration & Documentation (Week 6)

#### **4.1 Configuration Enhancement**
**Task**: Extend `citeloom.toml` with Zotero options

**Configuration Schema**:
```toml
[zotero]
mode = "auto"              # local-first | web-first | local-only | web-only | auto
db_path = ""               # Override for local sqlite (else auto-discover)
storage_dir = ""            # Override for storage dir (else derive from profile)
include_annotations = false # Enable annotation extraction/indexing

[zotero.web]
library_id = ""             # For Web API (fallback)
api_key = ""                # For Web API (fallback)
rate_limit_ms = 500         # Rate limit interval in ms

[zotero.filters]
include_tags = []           # Tag filtering (OR logic)
exclude_tags = []           # Tag exclusion (ANY-match)

[zotero.fulltext]
prefer_zotero_fulltext = true  # Use Zotero fulltext when available
```

**Files to Create/Modify**:
- `src/infrastructure/config/settings.py` (extend Settings class)
- `citeloom.toml` (example configuration)

**Dependencies**: None

---

#### **4.2 FastMCP Configuration**
**Task**: Fix FastMCP deprecation warnings

**Requirements**:
- Add `fastmcp.json` with dependencies and entrypoint
- Remove ad-hoc "dependencies" arg in code

**Files to Create/Modify**:
- `fastmcp.json` (verify/update)
- `src/infrastructure/mcp/server.py` (remove deprecated args)

**Dependencies**: None

---

#### **4.3 Documentation**
**Task**: Document new features and patterns

**Documents to Create/Update**:
- Platform-specific Zotero profile paths guide
- Cloud-sync caveats (don't read from syncing profiles)
- Local vs Web API trade-offs
- Annotation indexing guide
- Full-text reuse policy explanation
- Embedding model governance guide

**Files to Create/Modify**:
- `docs/zotero-local-access.md` (new)
- `docs/zotero-annotations.md` (new)
- `docs/embedding-governance.md` (new)
- `README.md` (update Zotero section)

**Dependencies**: None

---

## 5. Technical Specifications

### 5.0 Reference Implementation Patterns (from zotero-mcp)

This section documents concrete implementation patterns observed in the [zotero-mcp repository](https://github.com/54yyyu/zotero-mcp/tree/main/src/zotero_mcp).

#### **SQLite Connection Pattern**
```python
import sqlite3
from pathlib import Path

def open_zotero_db_readonly(db_path: Path) -> sqlite3.Connection:
    """Open Zotero SQLite database in immutable read-only mode."""
    # Convert to absolute path for URI mode
    abs_path = db_path.resolve()
    # Use URI mode with immutable=1 and mode=ro flags
    uri = f"file:{abs_path}?immutable=1&mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    # Enable JSON1 extension for parsing items.data
    conn.enable_load_extension(True)
    return conn
```

#### **Profile Detection Pattern**
```python
import platform
from pathlib import Path

def get_zotero_profile_path() -> Path | None:
    """Detect Zotero profile directory per platform."""
    system = platform.system()
    
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", "")) / "Zotero"
        profiles_ini = base / "Profiles" / "profiles.ini"
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support" / "Zotero"
        profiles_ini = base / "Profiles" / "profiles.ini"
    else:  # Linux
        base = Path.home() / ".zotero" / "zotero"
        profiles_ini = base / "Profiles" / "profiles.ini"
    
    if not profiles_ini.exists():
        return None
    
    # Parse profiles.ini to find default profile
    # Look for [Profile0] with Default=1, or use first profile
    # Return: base / "Profiles" / "{profile_id}"
```

#### **Collection Listing SQL Query**
```sql
-- Get all collections with hierarchy
SELECT 
    c.collectionID,
    c.collectionName,
    c.parentCollectionID,
    (SELECT COUNT(*) FROM collectionItems ci WHERE ci.collectionID = c.collectionID) as item_count
FROM collections c
ORDER BY c.collectionName;
```

#### **Collection Items SQL Query**
```sql
-- Get items in a collection (including subcollections)
WITH RECURSIVE subcollections(collectionID) AS (
    -- Base case: start collection
    SELECT ? AS collectionID
    UNION ALL
    -- Recursive case: child collections
    SELECT c.collectionID 
    FROM collections c
    JOIN subcollections sc ON c.parentCollectionID = sc.collectionID
)
SELECT DISTINCT
    i.itemID,
    i.key,
    json_extract(i.data, '$.title') as title,
    json_extract(i.data, '$.itemType') as itemType,
    json_extract(i.data, '$.creators') as creators,
    json_extract(i.data, '$.date') as date,
    json_extract(i.data, '$.tags') as tags
FROM items i
JOIN collectionItems ci ON i.itemID = ci.itemID
JOIN subcollections sc ON ci.collectionID = sc.collectionID
WHERE json_extract(i.data, '$.itemType') != 'attachment'
  AND json_extract(i.data, '$.itemType') != 'annotation';
```

#### **Attachment Resolution SQL Query**
```sql
-- Get attachments for an item
SELECT 
    ia.itemID,
    ia.key as attachment_key,
    json_extract(ia.data, '$.filename') as filename,
    json_extract(ia.data, '$.contentType') as contentType,
    json_extract(ia.data, '$.linkMode') as linkMode,
    json_extract(ia.data, '$.path') as path,
    -- Parent item key for storage path construction
    (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key
FROM itemAttachments ia
WHERE ia.parentItemID = (
    SELECT itemID FROM items WHERE key = ?
)
AND json_extract(ia.data, '$.contentType') = 'application/pdf';
```

#### **Full-Text Retrieval SQL Query**
```sql
-- Get fulltext for an attachment
SELECT 
    ft.text,
    ft.indexedChars,
    ft.totalChars
FROM fulltext ft
JOIN items i ON ft.itemID = i.itemID
WHERE i.key = ?  -- attachment item key
AND ft.text IS NOT NULL
AND ft.text != '';
```

#### **Annotation Extraction Query (via Web API pattern)**
```python
# zotero-mcp pattern for fetching annotations
def fetch_annotations(zotero_client, attachment_key: str) -> list[dict]:
    """Fetch annotations for an attachment."""
    # Query items with itemType=annotation and parentItem=attachment_key
    annotations = zotero_client.children(
        attachment_key,
        itemType='annotation'
    )
    
    normalized = []
    for ann in annotations:
        data = ann.get('data', {})
        normalized.append({
            'page': data.get('pageIndex', 0) + 1,  # 0-indexed → 1-indexed
            'quote': data.get('text', ''),
            'comment': data.get('comment', ''),
            'color': data.get('color', ''),
            'tags': [tag.get('tag', '') for tag in data.get('tags', [])],
        })
    
    return normalized
```

#### **Content Hash Pattern**
```python
import hashlib
from pathlib import Path

def compute_content_hash(
    file_path: Path,
    embedding_model: str,
    chunking_policy_version: str
) -> str:
    """Compute deterministic hash for deduplication."""
    # Read file content (first 1MB for performance, or full file for accuracy)
    with open(file_path, 'rb') as f:
        content_preview = f.read(1024 * 1024)  # First 1MB
        file_size = f.seek(0, 2)  # Get total size
    
    # Include file size, content preview, embedding model, and policy version
    hash_input = (
        str(file_size).encode() +
        content_preview +
        embedding_model.encode() +
        chunking_policy_version.encode()
    )
    
    return hashlib.sha256(hash_input).hexdigest()
```

---

### 5.1 Local SQLite Adapter Interface

```python
class LocalZoteroDbAdapter(ZoteroImporterPort):
    """
    Read-only SQLite adapter for Zotero database access.
    
    Opens zotero.sqlite in immutable read-only mode to avoid locks.
    Falls back to Web API adapter if DB unavailable.
    """
    
    def __init__(
        self,
        db_path: Path | None = None,
        storage_dir: Path | None = None,
        fallback_adapter: ZoteroImporterPort | None = None,
    ):
        """
        Initialize local DB adapter.
        
        Args:
            db_path: Override DB path (else auto-detect)
            storage_dir: Override storage dir (else derive from profile)
            fallback_adapter: Web API adapter for fallback
        """
        
    def _detect_zotero_profile(self) -> Path:
        """Detect Zotero profile directory per platform."""
        
    def _open_db_readonly(self) -> sqlite3.Connection:
        """Open SQLite DB in immutable read-only mode."""
        
    def list_collections(self) -> list[dict[str, Any]]:
        """List collections with hierarchy via SQL query."""
        
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Get items via SQL join: collectionItems → items."""
        
    def get_item_attachments(self, item_key: str) -> list[dict[str, Any]]:
        """Get attachments via SQL query on itemAttachments."""
        
    def resolve_attachment_path(
        self,
        attachment_key: str,
        item_key: str,
        link_mode: str,
    ) -> Path:
        """Resolve file path: imported vs linked."""
```

---

### 5.2 Full-Text Resolver Interface

```python
class FulltextResolver:
    """
    Resolves document full-text, preferring Zotero cached text.
    """
    
    def resolve_fulltext(
        self,
        attachment_key: str,
        file_path: Path,
        prefer_zotero: bool = True,
    ) -> FulltextResult:
        """
        Resolve full-text with preference strategy.
        
        Returns:
            FulltextResult with:
            - text: Full text content
            - source: "zotero" | "docling" | "mixed"
            - pages_from_zotero: List of page numbers
            - pages_from_docling: List of page numbers
        """
        
    def _get_zotero_fulltext(self, attachment_key: str) -> str | None:
        """Query Zotero fulltext table."""
        
    def _get_docling_fulltext(self, file_path: Path) -> str:
        """Fallback to Docling conversion."""
```

---

### 5.3 Annotation Resolver Interface

```python
class AnnotationResolver:
    """
    Extracts and indexes PDF annotations from Zotero.
    """
    
    def fetch_annotations(
        self,
        attachment_key: str,
        zotero_client: zotero.Zotero,
    ) -> list[Annotation]:
        """
        Fetch annotations for attachment via Web API.
        
        Returns:
            List of Annotation objects:
            - page: int
            - quote: str
            - comment: str | None
            - color: str | None
            - tags: list[str]
        """
        
    def index_annotations(
        self,
        annotations: list[Annotation],
        item_key: str,
        attachment_key: str,
        project_id: str,
        index: VectorIndexPort,
    ) -> int:
        """
        Index annotations as separate points.
        
        Returns:
            Number of annotation points indexed
        """
```

---

### 5.4 Source Router Interface

```python
class ZoteroSourceRouter:
    """
    Routes Zotero operations to local DB or Web API based on strategy.
    """
    
    Strategy = Literal["local-first", "web-first", "auto", "local-only", "web-only"]
    
    def __init__(
        self,
        local_adapter: ZoteroImporterPort | None,
        web_adapter: ZoteroImporterPort,
        strategy: Strategy = "auto",
    ):
        """Initialize router with adapters and strategy."""
        
    def list_collections(self) -> list[dict[str, Any]]:
        """Route collection listing based on strategy."""
        
    def get_collection_items(
        self,
        collection_key: str,
        include_subcollections: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """Route item fetching based on strategy."""
        
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> Path:
        """
        Route download with fallback logic.
        
        Strategy behaviors:
        - local-first: Try local, fallback to web if missing
        - web-first: Try web, fallback to local on rate limit
        - auto: Smart selection
        - local-only/web-only: No fallback
        """
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

**LocalZoteroDbAdapter**:
- Test ro/immutable open on each platform
- Test profile detection (Windows/macOS/Linux)
- Test collection/item/attachment SQL queries
- Test path resolution (imported vs linked)
- Test fallback when DB locked

**FulltextResolver**:
- Test Zotero fulltext preference
- Test fallback to Docling
- Test page-level mixed provenance
- Test audit trail

**AnnotationResolver**:
- Test annotation extraction
- Test indexing as separate points
- Test graceful skip when disabled

**ZoteroSourceRouter**:
- Test each strategy mode
- Test fallback logic
- Test source markers

---

### 6.2 Integration Tests

**End-to-End Import with Local DB**:
- Import collection using local-first strategy
- Verify files resolved correctly
- Verify metadata extracted correctly
- Verify chunks stored with correct payload

**Full-Text Reuse**:
- Import document with Zotero fulltext
- Verify fast path used
- Verify fallback to Docling for missing pages
- Verify audit trail accuracy

**Annotation Indexing**:
- Import collection with annotations enabled
- Verify annotations indexed as separate points
- Verify annotation queries work

**Incremental Deduplication**:
- Import collection twice
- Verify unchanged documents skipped
- Verify changed documents re-processed

---

### 6.3 Platform Testing Matrix

| Platform | Local DB Access | Profile Detection | Path Resolution |
|----------|----------------|-------------------|-----------------|
| Windows  | ✅ Test        | ✅ Test           | ✅ Test         |
| macOS    | ✅ Test        | ✅ Test           | ✅ Test         |
| Linux    | ✅ Test        | ✅ Test           | ✅ Test         |

**Edge Cases**:
- Zotero running (DB may be locked)
- Zotero not running (local DB should work)
- Multiple Zotero profiles (detect default)
- Cloud-synced profile (document risks)
- Non-ASCII paths (Windows path quirks)

---

## 7. Migration & Rollout

### 7.1 Backward Compatibility

**Maintain Existing Behavior**:
- Default to `web-first` strategy (current behavior)
- Local DB adapter is opt-in via `mode=local-first` or `mode=auto`
- Existing Web API workflows continue to work
- Annotation indexing disabled by default

**Gradual Migration**:
1. Phase 1: Add local DB adapter (opt-in)
2. Phase 2: Enable full-text reuse (opt-in via config)
3. Phase 3: Enable annotations (opt-in via flag)
4. Phase 4: Make `auto` mode default (smart selection)

---

### 7.2 Feature Flags

**Configuration Flags**:
- `zotero.mode`: Source selection strategy
- `zotero.include_annotations`: Annotation extraction
- `zotero.fulltext.prefer_zotero_fulltext`: Full-text reuse
- CLI flags: `--local-only`, `--web-only`, `--include-annotations`

---

## 8. Success Metrics

### 8.1 Performance Improvements

**Expected Gains**:
- **Import Speed**: 50-80% faster for documents with Zotero fulltext
- **Offline Capability**: 100% functionality without internet (local DB mode)
- **Browsing Speed**: 10x faster collection/item browsing (local DB vs Web API)
- **Rate Limit Avoidance**: Zero rate limits when using local DB

**Measurement**:
- Benchmark import time: before vs after full-text reuse
- Benchmark browsing: Web API vs local DB (latency)
- Track rate limit encounters (should be zero with local DB)

---

### 8.2 Quality Improvements

**Retrieval Quality**:
- Annotation indexing: Measure recall improvement on queries targeting annotations
- Full-text quality: Compare Zotero fulltext vs Docling accuracy

**User Experience**:
- Error clarity: Measure time to resolution with improved diagnostics
- Offline usage: Track offline capability usage

---

## 9. Risks & Mitigations

### 9.1 Technical Risks

**Risk**: SQLite DB corruption if opened incorrectly  
**Mitigation**: Always use immutable read-only mode (`?immutable=1&mode=ro`)

**Risk**: DB lock when Zotero is running  
**Mitigation**: Immutable mode allows concurrent reads; fallback to Web API if lock detected

**Risk**: Cloud-synced profile changes during read  
**Mitigation**: Document risk; recommend Web API or local auto-export for cloud-synced profiles

**Risk**: Path resolution failures for linked files  
**Mitigation**: Validate path existence; fallback to Web API download

**Risk**: Full-text quality issues (Zotero fulltext may be incomplete)  
**Mitigation**: Page-level fallback to Docling for missing/low-quality pages

---

### 9.2 Operational Risks

**Risk**: Users confused by strategy modes  
**Mitigation**: Clear documentation; default to `auto` (smart selection)

**Risk**: Annotation indexing increases storage  
**Mitigation**: Disabled by default; opt-in flag

**Risk**: Migration complexity for existing collections  
**Mitigation**: Backward compatible; no migration required

---

## 10. Conclusion & Next Steps

### 10.1 Summary

This analysis identifies **8 critical improvements** to CiteLoom's Zotero integration, inspired by zotero-mcp patterns:

1. **Local SQLite Access** (P0) - Enables offline browsing, instant access, zero rate limits
2. **Full-Text Reuse** (P0) - Reduces processing time by 50-80% for already-processed documents
3. **Annotation Extraction** (P1) - Dramatically improves retrieval quality
4. **Embedding Governance** (P1) - Prevents silent recall degradation
5. **Incremental Deduplication** (P1) - Avoids re-processing unchanged documents
6. **Library Browsing Tools** (P2) - Better UX for exploring library structure
7. **Source Router** (P2) - Flexible local/web source selection
8. **Payload Enrichment** (P2) - Better traceability and targeted queries

**Total Estimated Effort**: 10-15 days across 3 phases

---

### 10.2 Immediate Next Steps

1. **Review & Approval**: Review this analysis with stakeholders
2. **Prioritize**: Confirm priority order (recommend: Phase 1 → Phase 2 → Phase 3)
3. **Spec Writing**: Convert roadmap items into detailed specs (contracts, tasks)
4. **Implementation**: Begin Phase 1 (Local SQLite Adapter + Source Router)

---

### 10.3 Questions for Discussion

- Should annotation indexing be enabled by default or opt-in?
- Should `auto` mode be the default strategy, or `web-first` for backward compatibility?
- What's the priority order if we can't do all improvements?
- Are there any zotero-mcp patterns we should avoid (lessons learned)?

---

## 11. Additional Insights from zotero-mcp

### 11.1 Code Organization Patterns

**Module Structure** (from [zotero-mcp/src/zotero_mcp/](https://github.com/54yyyu/zotero-mcp/tree/main/src/zotero_mcp)):
- `local_db.py`: SQLite database access layer
- `pdfannots_downloader.py`: PDF annotation and attachment handling
- `tools.py`: MCP tool definitions and orchestration
- `server.py`: FastMCP server setup and configuration

**Separation of Concerns**:
- Database access is isolated in `local_db.py`
- Annotation logic is separate from general item handling
- Tools layer orchestrates between adapters

### 11.2 Error Handling Patterns

**Graceful Degradation**:
- Always attempts local DB first, falls back to Web API
- Validates file existence before returning paths
- Provides clear error messages with actionable guidance

**Connection Resilience**:
- Handles SQLite locked errors gracefully
- Retries with exponential backoff for Web API calls
- Validates connection before use

### 11.3 Configuration Patterns

**Environment Variable Support**:
- `ZOTERO_LOCAL`: Enable local access
- `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`: Embedding provider config
- `ZOTERO_EMBEDDING_MODEL`: Override default model

**FastMCP Configuration**:
- Uses `fastmcp.json` for dependency declaration
- Avoids deprecated `dependencies` parameter in code

### 11.4 Performance Optimizations

**Lazy Loading**:
- Collections/items loaded on-demand via generators
- Fulltext fetched only when needed
- Annotations fetched per attachment, not batch-loaded

**Caching Strategies**:
- Profile path detection cached after first lookup
- Database connection reused when possible
- Fulltext results cached in memory during batch processing

### 11.5 Lessons Learned (What to Avoid)

**Database Locking Issues**:
- ❌ **Avoid**: Opening DB in read-write mode when Zotero is running
- ✅ **Do**: Always use `immutable=1&mode=ro` for concurrent reads

**Path Resolution Failures**:
- ❌ **Avoid**: Assuming storage directory structure
- ✅ **Do**: Query `linkMode` from DB and validate paths exist

**Cloud Sync Conflicts**:
- ❌ **Avoid**: Reading from actively syncing profiles
- ✅ **Do**: Document risk and recommend Web API for cloud-synced libraries

---

## References

### zotero-mcp Repository
- **Main Repository**: [github.com/54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp)
- **Source Directory**: [src/zotero_mcp/](https://github.com/54yyyu/zotero-mcp/tree/main/src/zotero_mcp)
- **Local DB Implementation**: [local_db.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py)
- **PDF Annotations**: [pdfannots_downloader.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/pdfannots_downloader.py)
- **MCP Tools**: [tools.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/tools.py)

### CiteLoom Documentation
- **Zotero Batch Import Spec**: `specs/004-zotero-batch-import/spec.md`
- **Zotero Ports Contract**: `specs/004-zotero-batch-import/contracts/ports.md`
- **Framework Implementation**: `specs/003-framework-implementation/spec.md`

### Zotero Official Documentation
- **Client Coding Guide**: [zotero.org/support/dev/client_coding](https://www.zotero.org/support/dev/client_coding)
- **Zotero SQLite Schema**: [zotero.org/support/kb/sqlite_database](https://www.zotero.org/support/kb/sqlite_database)
- **Web API Documentation**: [zotero.org/support/dev/web_api](https://www.zotero.org/support/dev/web_api)

---

**Document Status**: Analysis Complete - Ready for Review  
**Last Updated**: 2025-01-27

