# Research: Comprehensive Zotero Integration Improvements

**Date**: 2025-01-27  
**Feature**: 005-zotero-improvements  
**Status**: Complete  
**Reference**: `docs/analysis/zotero-improvement-roadmap.md`

---

## Research Summary

This research consolidates implementation patterns from zotero-mcp repository and Zotero SQLite database schema documentation to guide the implementation of local SQLite access, full-text reuse, annotation extraction, incremental deduplication, and source routing features.

**Key Research Areas**:
1. SQLite immutable read-only access patterns
2. Platform-aware Zotero profile detection
3. Zotero database schema and SQL query patterns
4. Full-text table structure and quality validation
5. Annotation extraction via Web API
6. Content hashing strategies for deduplication
7. Source routing and fallback strategies

---

## 1. SQLite Immutable Read-Only Access

### Decision: Use SQLite URI mode with immutable=1 and mode=ro flags

**Rationale**: 
- SQLite immutable read-only mode creates a snapshot view that prevents interference from concurrent Zotero writes
- SQLite guarantees isolation - reads from immutable connection see consistent snapshot regardless of writes
- No database locks required - multiple readers can access simultaneously
- Prevents corruption risk when Zotero is actively syncing or writing

**Implementation Pattern** (from zotero-mcp):
```python
import sqlite3
from pathlib import Path

def open_zotero_db_readonly(db_path: Path) -> sqlite3.Connection:
    """Open Zotero SQLite database in immutable read-only mode."""
    abs_path = db_path.resolve()
    uri = f"file:{abs_path}?immutable=1&mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    # Enable JSON1 extension for parsing items.data
    conn.enable_load_extension(True)  # Optional, for JSON parsing
    return conn
```

**Key Points**:
- Must resolve to absolute path for URI mode
- `immutable=1` flag ensures read-only snapshot (no writes possible)
- `mode=ro` explicitly marks read-only
- JSON1 extension enables `json_extract()` queries on `items.data` field

**Alternatives Considered**:
- **Read-write mode**: ❌ Rejected - risk of corruption, requires locks, conflicts with Zotero
- **WAL mode with read-only**: ❌ Rejected - still allows writes, less safe than immutable
- **Copy database**: ❌ Rejected - unnecessary overhead, stale data risk

---

## 2. Platform-Aware Profile Detection

### Decision: Implement platform-specific path detection with profiles.ini parsing

**Rationale**:
- Zotero stores profiles in platform-specific locations
- Standard installations follow predictable paths
- profiles.ini contains profile metadata including default selection
- Allows override via configuration for non-standard setups

**Implementation Pattern** (from zotero-mcp):
```python
import platform
import os
from pathlib import Path
from configparser import ConfigParser

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
    config = ConfigParser()
    config.read(profiles_ini)
    
    # Look for [Profile0] with Default=1, or use first profile
    for section in config.sections():
        if section.startswith("Profile") and config.getboolean(section, "Default", fallback=False):
            profile_id = config.get(section, "Path", fallback=None)
            if profile_id:
                return base / "Profiles" / profile_id
    
    # Fallback: use first profile if no default marked
    for section in config.sections():
        if section.startswith("Profile"):
            profile_id = config.get(section, "Path", fallback=None)
            if profile_id:
                return base / "Profiles" / profile_id
    
    return None
```

**Platform Paths**:
- **Windows**: `%APPDATA%\Zotero\Profiles\{profile_id}\`
- **macOS**: `~/Library/Application Support/Zotero/Profiles/{profile_id}/`
- **Linux**: `~/.zotero/zotero/Profiles/{profile_id}/`

**Key Points**:
- Uses Python stdlib `platform` and `configparser` modules (no external dependencies)
- Handles missing profiles gracefully (returns None)
- Supports override via configuration for portable Zotero or custom paths

**Alternatives Considered**:
- **Hardcoded paths**: ❌ Rejected - doesn't handle non-standard installations
- **Environment variable only**: ❌ Rejected - should auto-detect for better UX
- **Registry/plist queries**: ❌ Rejected - adds complexity, filesystem approach is simpler

---

## 3. Zotero Database Schema and SQL Queries

### Decision: Use direct SQL queries on Zotero SQLite schema

**Rationale**:
- Zotero SQLite schema is well-documented and stable
- Direct SQL queries are faster than API calls
- No network overhead or rate limits
- JSON fields in `items.data` enable rich metadata extraction

**Key Tables**:
- `collections`: Collection hierarchy (collectionID, collectionName, parentCollectionID)
- `collectionItems`: Junction table linking collections to items
- `items`: Zotero items (itemID, key, data JSONB field)
- `itemAttachments`: Attachment metadata (itemID, key, linkMode, path, data JSONB)
- `fulltext`: Cached full-text content (itemID, text, indexedChars, totalChars)

**SQL Query Patterns**:

**Collection Listing with Hierarchy**:
```sql
SELECT 
    c.collectionID,
    c.collectionName,
    c.parentCollectionID,
    (SELECT COUNT(*) FROM collectionItems ci WHERE ci.collectionID = c.collectionID) as item_count
FROM collections c
ORDER BY c.collectionName;
```

**Collection Items (with subcollections via recursive CTE)**:
```sql
WITH RECURSIVE subcollections(collectionID) AS (
    SELECT ? AS collectionID
    UNION ALL
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

**Attachment Resolution**:
```sql
SELECT 
    ia.itemID,
    ia.key as attachment_key,
    json_extract(ia.data, '$.filename') as filename,
    json_extract(ia.data, '$.contentType') as contentType,
    json_extract(ia.data, '$.linkMode') as linkMode,
    json_extract(ia.data, '$.path') as path,
    (SELECT key FROM items WHERE itemID = ia.parentItemID) as parent_item_key
FROM itemAttachments ia
WHERE ia.parentItemID = (SELECT itemID FROM items WHERE key = ?)
AND json_extract(ia.data, '$.contentType') = 'application/pdf';
```

**Key Points**:
- JSON1 extension enables `json_extract()` for parsing `items.data` JSON field
- `linkMode=0` indicates imported file (path in storage directory)
- `linkMode=1` indicates linked file (absolute path in database)
- Recursive CTEs enable subcollection traversal

**Alternatives Considered**:
- **ORM approach**: ❌ Rejected - adds complexity, direct SQL is simpler for read-only access
- **ORM with SQLAlchemy**: ❌ Rejected - overkill for simple read-only queries, adds dependency

---

## 4. Full-Text Table Structure and Quality Validation

### Decision: Query fulltext table and validate quality before reuse

**Rationale**:
- Zotero stores extracted text in `fulltext` table with metadata
- Not all documents have fulltext (indexing may fail or never run)
- Quality validation prevents using corrupted or incomplete text
- Page-level fallback enables mixed provenance when fulltext is partial

**Full-Text Retrieval Query**:
```sql
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

**Quality Validation Criteria**:
1. **Non-empty check**: `text IS NOT NULL AND text != ''`
2. **Minimum length**: At least 100 characters (configurable threshold)
3. **Structure validation**: Contains sentence/paragraph patterns (reasonable document structure)
4. **Completeness**: `indexedChars` vs `totalChars` ratio indicates coverage (optional check)

**Implementation Pattern**:
```python
def validate_fulltext_quality(text: str, min_length: int = 100) -> bool:
    """Validate fulltext quality before reuse."""
    if not text or len(text.strip()) < min_length:
        return False
    
    # Check for reasonable document structure
    # Simple heuristic: contains sentences (periods), paragraphs (newlines or multiple spaces)
    has_sentences = '.' in text
    has_structure = '\n' in text or '  ' in text  # Paragraphs or multiple spaces
    
    return has_sentences and has_structure
```

**Key Points**:
- Quality thresholds are configurable (default 100 chars minimum)
- Falls back to Docling if validation fails
- Supports page-level mixed provenance (some pages from Zotero, some from Docling)

**Alternatives Considered**:
- **Always use fulltext**: ❌ Rejected - risk of using corrupted/incomplete text
- **No quality checks**: ❌ Rejected - may result in poor chunking quality
- **ML-based quality scoring**: ❌ Rejected - overkill, simple heuristics sufficient

---

## 5. Annotation Extraction via Web API

### Decision: Fetch annotations via Web API using pyzotero children() method

**Rationale**:
- Annotations are stored as child items with `itemType=annotation`
- Local SQLite database doesn't easily expose annotation relationships
- Web API `children()` method provides clean access to annotation items
- Supports normalization (pageIndex → page, extract quote/comment/color/tags)

**Implementation Pattern** (from zotero-mcp):
```python
from pyzotero import zotero

def fetch_annotations(zotero_client: zotero.Zotero, attachment_key: str) -> list[dict]:
    """Fetch annotations for an attachment via Web API."""
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

**Annotation Data Structure**:
- `pageIndex`: 0-indexed page number (convert to 1-indexed for CiteLoom)
- `text`: Highlighted/quoted text
- `comment`: User's comment/note on annotation
- `color`: Highlight color (hex format)
- `tags`: Array of tag objects with `tag` field

**Error Handling**:
- Retry with exponential backoff (3 retries, base 1s, max 30s, with jitter)
- Skip attachment annotations if all retries fail
- Log warning with failed attachment keys
- Continue import without blocking

**Key Points**:
- Web API access required (not available via local SQLite easily)
- Follows existing retry patterns from ZoteroImporterAdapter
- Normalization ensures consistent format for indexing

**Alternatives Considered**:
- **Local SQLite annotation queries**: ❌ Rejected - complex joins, Web API is cleaner
- **Batch annotation fetching**: ❌ Rejected - rate limit risk, per-attachment is safer
- **Skip annotations on failure**: ✅ Accepted - graceful degradation, import continues

---

## 6. Content Hashing for Deduplication

### Decision: Use first 1MB + file size + policy versions for hash, with metadata verification

**Rationale**:
- Full file hash would be too slow for large files
- First 1MB + file size provides good uniqueness (collision rate acceptable)
- Policy versions in hash ensure re-processing on policy changes
- File metadata (mtime + size) serves as secondary collision protection

**Implementation Pattern**:
```python
import hashlib
from pathlib import Path
from datetime import datetime

def compute_content_hash(
    file_path: Path,
    embedding_model: str,
    chunking_policy_version: str,
    embedding_policy_version: str
) -> str:
    """Compute deterministic hash for deduplication."""
    with open(file_path, 'rb') as f:
        content_preview = f.read(1024 * 1024)  # First 1MB
        file_size = f.seek(0, 2)  # Get total size
    
    hash_input = (
        str(file_size).encode() +
        content_preview +
        embedding_model.encode() +
        chunking_policy_version.encode() +
        embedding_policy_version.encode()
    )
    
    return hashlib.sha256(hash_input).hexdigest()

def create_content_fingerprint(
    file_path: Path,
    content_hash: str,
    embedding_model: str,
    chunking_policy_version: str,
    embedding_policy_version: str
) -> dict[str, Any]:
    """Create content fingerprint with metadata."""
    stat = file_path.stat()
    return {
        'content_hash': content_hash,
        'file_mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'file_size': stat.st_size,
        'embedding_model': embedding_model,
        'chunking_policy_version': chunking_policy_version,
        'embedding_policy_version': embedding_policy_version,
    }
```

**Fingerprint Comparison Logic**:
```python
def is_unchanged(
    stored_fingerprint: dict[str, Any],
    computed_hash: str,
    file_path: Path
) -> bool:
    """Check if document is unchanged (skip re-processing)."""
    # Primary check: content hash matches
    if stored_fingerprint['content_hash'] != computed_hash:
        return False
    
    # Secondary check: file metadata matches (collision protection)
    stat = file_path.stat()
    stored_mtime = datetime.fromisoformat(stored_fingerprint['file_mtime'])
    stored_size = stored_fingerprint['file_size']
    
    if stat.st_mtime != stored_mtime.timestamp() or stat.st_size != stored_size:
        return False  # Hash matches but metadata differs - treat as different document
    
    # Policy versions must match (policy changes invalidate fingerprints)
    # This is checked separately before calling is_unchanged()
    
    return True
```

**Key Points**:
- Hash includes policy versions to invalidate on policy changes
- Metadata verification prevents hash collisions
- 1MB preview balances performance vs accuracy
- Policy version tracking ensures correctness on policy changes

**Alternatives Considered**:
- **Full file hash**: ❌ Rejected - too slow for large files (multi-GB PDFs)
- **Filename + size only**: ❌ Rejected - not unique enough, files can be renamed
- **No metadata verification**: ❌ Rejected - collision risk unacceptable

---

## 7. Source Routing and Fallback Strategies

### Decision: Implement per-file routing with strategy modes and automatic fallback

**Rationale**:
- Per-file routing allows mixed sources in same collection (some files local, some web)
- Strategy modes give users control over optimization (speed vs completeness)
- Automatic fallback provides resilience when primary source fails
- Source markers in manifest enable debugging and audit

**Strategy Modes**:

1. **`local-first`**: Check each file individually via local DB, fallback to Web API per-file if missing
2. **`web-first`**: Use Web API primarily, fallback to local DB on rate limits or unavailability
3. **`auto`**: Smart selection based on availability (prefer local if available and files exist, prefer web if local unavailable)
4. **`local-only`**: Strict mode - only local DB, no fallback (for debugging)
5. **`web-only`**: Strict mode - only Web API, no fallback (backward compatible)

**Implementation Pattern**:
```python
class ZoteroSourceRouter:
    """Routes Zotero operations to local DB or Web API based on strategy."""
    
    Strategy = Literal["local-first", "web-first", "auto", "local-only", "web-only"]
    
    def download_attachment(
        self,
        item_key: str,
        attachment_key: str,
        output_path: Path,
    ) -> tuple[Path, str]:  # Returns (file_path, source_marker)
        """Route download with fallback logic."""
        if self.strategy == "local-first":
            # Try local first
            if self.local_adapter.can_resolve_locally(attachment_key):
                path = self.local_adapter.resolve_attachment_path(...)
                if path.exists():
                    return (path, "local")
            # Fallback to web
            return (self.web_adapter.download_attachment(...), "web")
        
        elif self.strategy == "web-first":
            # Try web first
            try:
                return (self.web_adapter.download_attachment(...), "web")
            except ZoteroRateLimitError:
                # Fallback to local
                if self.local_adapter.can_resolve_locally(...):
                    return (self.local_adapter.resolve_attachment_path(...), "local")
                raise
        
        elif self.strategy == "auto":
            # Smart selection based on availability
            if self.local_adapter.is_available() and self.local_adapter.can_resolve_locally(...):
                return (self.local_adapter.resolve_attachment_path(...), "local")
            return (self.web_adapter.download_attachment(...), "web")
        
        # ... other strategies
```

**Key Points**:
- Per-file routing enables granular fallback (not collection-level)
- Source markers stored in manifest for audit/debugging
- Fallback logic handles: database locks, network failures, rate limits, missing files

**Alternatives Considered**:
- **Collection-level routing**: ❌ Rejected - too coarse, misses opportunities for mixed sources
- **Always use one source**: ❌ Rejected - loses resilience and flexibility
- **Manual source selection per file**: ❌ Rejected - too complex for users

---

## 8. Payload Enrichment with Zotero Keys

### Decision: Add zotero.item_key and zotero.attachment_key to chunk payloads with keyword indexes

**Rationale**:
- Enables targeted queries: "find all chunks from this Zotero paper"
- Improves traceability and debugging
- Supports targeted re-imports and verification
- Keyword indexes ensure fast queries (< 500ms for 10k chunks)

**Payload Schema Enhancement**:
```python
payload = {
    # Existing fields...
    "project_id": project_id,
    "doc_id": doc_id,
    "chunk_text": chunk_text,
    # ... other existing fields
    
    # New fields for Zotero traceability
    "zotero": {
        "item_key": item_key,        # Parent Zotero item
        "attachment_key": attachment_key,  # Source PDF attachment
    },
}
```

**Index Creation**:
```python
# In QdrantIndexAdapter.ensure_collection()
collection.create_payload_index(
    field_name="zotero.item_key",
    field_schema=PayloadSchemaType.KEYWORD
)
collection.create_payload_index(
    field_name="zotero.attachment_key",
    field_schema=PayloadSchemaType.KEYWORD
)
```

**Query Pattern**:
```python
# Find all chunks from a specific Zotero item
filters = Filter(
    must=[
        FieldCondition(key="zotero.item_key", match={"value": "ABC123"}),
        FieldCondition(key="project_id", match={"value": project_id}),
    ]
)
results = collection.query(..., query_filter=filters)
```

**Key Points**:
- Keyword indexes enable fast exact-match queries
- Nested under `zotero` namespace for organization
- Maintains backward compatibility (optional fields)

**Alternatives Considered**:
- **Top-level fields**: ❌ Rejected - namespace prevents conflicts, cleaner organization
- **Separate collection for annotations**: ✅ Accepted for annotations (separate `type:annotation` points)
- **No indexes**: ❌ Rejected - queries would be slow for large collections

---

## 9. Annotation Indexing Strategy

### Decision: Index annotations as separate vector points with type:annotation tag

**Rationale**:
- Annotations are high-signal content that deserves separate indexing
- Enables "only annotations" queries via filtering
- Better retrieval quality (annotations contain key insights)
- Separate points allow independent ranking and scoring

**Annotation Point Schema**:
```python
annotation_payload = {
    "type": "annotation",
    "project_id": project_id,
    "zotero": {
        "item_key": item_key,
        "attachment_key": attachment_key,
        "annotation": {
            "page": page_number,
            "quote": highlighted_text,
            "comment": user_comment,
            "color": highlight_color,
            "tags": annotation_tags,
        },
    },
    # Text for embedding: quote + (comment if present)
    "chunk_text": f"{quote}\n\n{comment}" if comment else quote,
}
```

**Indexing Strategy**:
- Create separate vector points (not attached to document chunks)
- Tag with `type:annotation` for filtering
- Use same embedding model as document chunks
- Store in same collection (project-scoped)

**Key Points**:
- Enables focused annotation queries
- Improves retrieval quality for research insights
- Storage overhead acceptable (separate points per annotation)
- Opt-in via `include_annotations` flag (disabled by default)

**Alternatives Considered**:
- **Attach to chunk metadata**: ❌ Rejected - can't query independently, less flexible
- **Separate collection**: ❌ Rejected - adds complexity, same collection is simpler
- **Inline in chunk text**: ❌ Rejected - dilutes chunk content, harder to trace

---

## 10. Embedding Model Governance Enhancement

### Decision: Store model/provider in collection metadata and provide friendly diagnostics

**Rationale**:
- Write-guard already exists but diagnostics are technical
- Friendly error messages help users understand and resolve mismatches
- CLI/MCP inspection tools enable verification before imports
- Prevents accidental recall degradation

**Current Implementation** (existing):
- Collection metadata stores `embed_model` (already implemented)
- Write-guard blocks mismatches (already implemented)

**Enhancement**:
```python
# Enhanced error message
def validate_embedding_model(
    collection_name: str,
    stored_model: str,
    requested_model: str
) -> None:
    """Validate embedding model match with friendly error."""
    if stored_model != requested_model:
        raise EmbeddingModelMismatch(
            f"Collection '{collection_name}' is bound to embedding model "
            f"'{stored_model}'. You requested '{requested_model}'. "
            f"Use `reindex --force-rebuild` to migrate to the new model, "
            f"or switch back to '{stored_model}'."
        )
```

**CLI Enhancement**:
```bash
citeloom inspect project my-project --show-embedding-model
# Output:
# Collection: my-project
# Embedding Model: BAAI/bge-small-en-v1.5
# Provider: FastEmbed
```

**Key Points**:
- Builds on existing write-guard infrastructure
- Adds user-friendly messaging
- Provides clear migration path
- Low effort, high value improvement

**Alternatives Considered**:
- **No diagnostics**: ❌ Rejected - users confused by technical errors
- **Auto-migration**: ❌ Rejected - too risky, explicit flag required
- **Separate config file**: ❌ Rejected - metadata approach is simpler

---

## 11. Policy Version Tracking

### Decision: Version chunking and embedding policies together and include in content hash

**Rationale**:
- Policy changes (chunking params, embedding model) affect document processing
- Content hash must include policy versions to invalidate fingerprints on policy changes
- Versioning together simplifies tracking (single version string)

**Policy Version Format**:
```python
# Example: "1.0" represents chunking policy v1.0 and embedding policy v1.0
# When either changes, bump to "1.1" or "2.0"
policy_version = f"{chunking_policy_version}"  # e.g., "1.0"

# Include in hash
hash_input = (
    file_content_preview +
    file_size +
    embedding_model_id +
    chunking_policy_version +  # e.g., "1.0"
    embedding_policy_version   # e.g., "1.0" (same as chunking for simplicity)
)
```

**Version Bumping Rules**:
- Chunking policy changes (max_tokens, overlap, heading_context): bump version
- Embedding model changes: bump version
- Any policy change invalidates all fingerprints (requires re-processing)

**Key Points**:
- Simplified: single version for both policies (easier tracking)
- Alternative: separate versions if needed later (adds complexity)
- Version included in hash ensures correctness on policy changes

**Alternatives Considered**:
- **Separate versions**: ⚠️ Considered - more granular but adds complexity
- **No version tracking**: ❌ Rejected - risk of incorrect deduplication on policy changes
- **Hash-only (no version)**: ❌ Rejected - can't detect policy changes that don't affect file content

---

## 12. Error Handling and Resilience

### Decision: Graceful degradation with clear error messages and fallback strategies

**Rationale**:
- Local DB may be unavailable (locked, corrupted, profile not found)
- Web API may be unavailable (network, rate limits, auth failures)
- Individual document failures shouldn't block entire collection import
- Clear error messages help users diagnose and resolve issues

**Error Categories**:
1. **Database unavailable**: Clear message + fallback to Web API if configured
2. **File not found locally**: Fallback to Web API download (per-file)
3. **Rate limit encountered**: Retry with backoff, fallback to local DB if available
4. **Docling conversion failure**: Fail individual document, continue import
5. **Annotation extraction failure**: Skip annotations, continue import

**Implementation Pattern**:
```python
try:
    result = local_adapter.resolve_attachment_path(...)
except ZoteroDatabaseLockedError:
    if fallback_adapter:
        logger.warning("Local DB locked, falling back to Web API")
        return fallback_adapter.download_attachment(...)
    raise ZoteroConnectionError(
        "Zotero database is locked. Close Zotero or use Web API mode."
    )
except FileNotFoundError:
    if fallback_adapter:
        logger.info("File not found locally, downloading via Web API")
        return fallback_adapter.download_attachment(...)
    raise
```

**Key Points**:
- Per-file error handling enables partial success
- Clear messages guide user resolution
- Fallback strategies maintain import progress

**Alternatives Considered**:
- **Fail entire import on any error**: ❌ Rejected - too brittle, wastes progress
- **Silent failures**: ❌ Rejected - users can't diagnose issues
- **Retry everything indefinitely**: ❌ Rejected - may hang on permanent failures

---

## 13. Configuration Schema

### Decision: Extend citeloom.toml with Zotero section and environment variables

**Rationale**:
- Centralized configuration follows existing patterns
- Environment variables for sensitive config (API keys)
- TOML file for user preferences (mode, flags)
- Backward compatible defaults

**Configuration Schema**:
```toml
[zotero]
mode = "auto"              # local-first | web-first | auto | local-only | web-only
db_path = ""               # Override for local sqlite (empty = auto-detect)
storage_dir = ""            # Override for storage dir (empty = derive from profile)
include_annotations = false # Enable annotation extraction/indexing
prefer_zotero_fulltext = true  # Use Zotero fulltext when available

[zotero.web]
library_id = ""             # For Web API (fallback)
api_key = ""                # For Web API (fallback, prefer .env)

[zotero.fulltext]
min_length = 100            # Minimum characters for quality validation
```

**Environment Variables**:
- `ZOTERO_LOCAL=true/false` (enable local DB access)
- `ZOTERO_LIBRARY_ID` (Web API)
- `ZOTERO_API_KEY` (Web API, should be in .env)
- `ZOTERO_EMBEDDING_MODEL` (override default)

**Key Points**:
- Sensitive config (API keys) in .env file (not committed)
- Non-sensitive config in citeloom.toml
- Environment variables override TOML values
- Defaults maintain backward compatibility

**Alternatives Considered**:
- **All in environment**: ❌ Rejected - TOML provides better UX for non-sensitive config
- **All in TOML**: ❌ Rejected - API keys shouldn't be committed
- **Separate config file**: ❌ Rejected - adds complexity, TOML is sufficient

---

## References

### zotero-mcp Repository
- **Main Repository**: [github.com/54yyyu/zotero-mcp](https://github.com/54yyyu/zotero-mcp)
- **Source Directory**: [src/zotero_mcp/](https://github.com/54yyyu/zotero-mcp/tree/main/src/zotero_mcp)
- **Local DB Implementation**: [local_db.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py)
- **PDF Annotations**: [pdfannots_downloader.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/pdfannots_downloader.py)
- **MCP Tools**: [tools.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/tools.py)

### Zotero Official Documentation
- **Client Coding Guide**: [zotero.org/support/dev/client_coding](https://www.zotero.org/support/dev/client_coding)
- **Zotero SQLite Schema**: [zotero.org/support/kb/sqlite_database](https://www.zotero.org/support/kb/sqlite_database)
- **Web API Documentation**: [zotero.org/support/dev/web_api](https://www.zotero.org/support/dev/web_api)

### CiteLoom Documentation
- **Zotero Improvement Roadmap**: `docs/analysis/zotero-improvement-roadmap.md`
- **Zotero Batch Import Spec**: `specs/004-zotero-batch-import/spec.md`
- **Zotero Ports Contract**: `specs/004-zotero-batch-import/contracts/ports.md`

---

**Research Status**: ✅ Complete - All implementation patterns documented, ready for design phase.

