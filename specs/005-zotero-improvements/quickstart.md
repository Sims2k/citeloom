# Quickstart: Comprehensive Zotero Integration Improvements

**Date**: 2025-01-27  
**Feature**: 005-zotero-improvements  
**Audience**: Developers implementing Zotero improvements

---

## Overview

This quickstart provides a step-by-step guide for implementing the Zotero integration improvements, including local SQLite access, full-text reuse, annotation indexing, incremental deduplication, and source routing.

**Estimated Implementation Time**: 10-15 days across 3 phases

---

## Phase 1: Foundation (Weeks 1-2)

### 1.1 Local SQLite Adapter

**Goal**: Implement `LocalZoteroDbAdapter` for offline browsing and instant access.

**Steps**:

1. **Create adapter file**:
   ```bash
   touch src/infrastructure/adapters/zotero_local_db.py
   ```

2. **Implement platform detection**:
   - Use `platform.system()` to detect OS (Windows/macOS/Linux)
   - Parse `profiles.ini` using `configparser` to find default profile
   - Return profile directory path

3. **Implement SQLite connection**:
   ```python
   def _open_db_readonly(self) -> sqlite3.Connection:
       abs_path = self.db_path.resolve()
       uri = f"file:{abs_path}?immutable=1&mode=ro"
       return sqlite3.connect(uri, uri=True)
   ```

4. **Implement `ZoteroImporterPort` methods**:
   - `list_collections()`: Query `collections` table with hierarchy
   - `get_collection_items()`: Use recursive CTE for subcollections
   - `get_item_attachments()`: Query `itemAttachments` table
   - `resolve_attachment_path()`: Handle `linkMode=0` (imported) vs `linkMode=1` (linked)

5. **Add error handling**:
   - Catch `sqlite3.OperationalError` for database locks
   - Return appropriate error types (`ZoteroDatabaseLockedError`, etc.)
   - Support fallback to Web API adapter

**Testing**:
```bash
# Test profile detection
uv run pytest tests/integration/test_zotero_local_db.py::test_profile_detection

# Test SQLite queries
uv run pytest tests/integration/test_zotero_local_db.py::test_collection_listing

# Test path resolution
uv run pytest tests/integration/test_zotero_local_db.py::test_attachment_path_resolution
```

**Reference**: `docs/analysis/zotero-improvement-roadmap.md` section 5.0 (SQLite Connection Pattern)

---

### 1.2 Source Router

**Goal**: Implement `ZoteroSourceRouter` for intelligent source selection.

**Steps**:

1. **Create service file**:
   ```bash
   touch src/application/services/zotero_source_router.py
   ```

2. **Implement strategy modes**:
   - `local-first`: Check each file locally, fallback to Web API per-file
   - `web-first`: Use Web API, fallback to local on rate limits
   - `auto`: Smart selection based on availability
   - `local-only` / `web-only`: Strict modes for debugging

3. **Implement routing logic**:
   ```python
   def download_attachment(...) -> tuple[Path, str]:
       if self.strategy == "local-first":
           if self.local_adapter.can_resolve_locally(attachment_key):
               path = self.local_adapter.resolve_attachment_path(...)
               if path.exists():
                   return (path, "local")
           # Fallback to web
           return (self.web_adapter.download_attachment(...), "web")
   ```

4. **Track source markers**:
   - Return `(file_path, source_marker)` tuple from `download_attachment()`
   - Store `source` in `DownloadManifestAttachment`

**Testing**:
```bash
uv run pytest tests/integration/test_zotero_source_router.py
```

---

## Phase 2: Performance & Quality (Weeks 3-4)

### 2.1 Full-Text Resolver

**Goal**: Implement `FulltextResolver` to prefer Zotero fulltext over Docling conversion.

**Steps**:

1. **Create resolver file**:
   ```bash
   touch src/infrastructure/adapters/zotero_fulltext_resolver.py
   ```

2. **Implement fulltext query**:
   ```python
   def get_zotero_fulltext(self, attachment_key: str) -> str | None:
       query = """
       SELECT ft.text
       FROM fulltext ft
       JOIN items i ON ft.itemID = i.itemID
       WHERE i.key = ? AND ft.text IS NOT NULL AND ft.text != ''
       """
       # Execute query via LocalZoteroDbAdapter connection
   ```

3. **Implement quality validation**:
   ```python
   def validate_fulltext_quality(text: str, min_length: int = 100) -> bool:
       if not text or len(text.strip()) < min_length:
           return False
       has_sentences = '.' in text
       has_structure = '\n' in text or '  ' in text
       return has_sentences and has_structure
   ```

4. **Implement fallback logic**:
   - Check Zotero fulltext first
   - Validate quality
   - Fallback to Docling converter if unavailable/low-quality
   - Support page-level mixed provenance

5. **Integrate with `ingest_document` use case**:
   - Call `FulltextResolver.resolve_fulltext()` before Docling conversion
   - Use fulltext if available, otherwise proceed with Docling

**Testing**:
```bash
uv run pytest tests/integration/test_zotero_fulltext.py
```

**Reference**: `docs/analysis/zotero-improvement-roadmap.md` section 5.0 (Full-Text Retrieval SQL Query)

---

### 2.2 Annotation Resolver

**Goal**: Extract and index PDF annotations as separate vector points.

**Steps**:

1. **Create resolver file**:
   ```bash
   touch src/infrastructure/adapters/zotero_annotation_resolver.py
   ```

2. **Implement annotation fetching**:
   ```python
   def fetch_annotations(
       self,
       attachment_key: str,
       zotero_client: zotero.Zotero,
   ) -> list[Annotation]:
       annotations = zotero_client.children(
           attachment_key,
           itemType='annotation'
       )
       # Normalize: pageIndex → page, extract quote/comment/color/tags
   ```

3. **Implement normalization**:
   ```python
   normalized = []
   for ann in annotations:
       data = ann.get('data', {})
       normalized.append(Annotation(
           page=data.get('pageIndex', 0) + 1,  # 0-indexed → 1-indexed
           quote=data.get('text', ''),
           comment=data.get('comment', ''),
           color=data.get('color', ''),
           tags=[tag.get('tag', '') for tag in data.get('tags', [])],
       ))
   ```

4. **Implement indexing**:
   - Create `AnnotationPoint` payload with `type:annotation`
   - Include `zotero.item_key`, `zotero.attachment_key`, `zotero.annotation.*`
   - Index as separate vector points in same collection
   - Tag with `type:annotation` for filtering

5. **Add retry logic**:
   - Exponential backoff (3 retries, base 1s, max 30s, with jitter)
   - Skip annotations if all retries fail
   - Log warning, continue import

6. **Integrate with `batch_import_from_zotero` use case**:
   - Check `include_annotations` flag
   - Call `AnnotationResolver.fetch_annotations()` for each PDF
   - Call `AnnotationResolver.index_annotations()` after document processing

**Testing**:
```bash
uv run pytest tests/integration/test_zotero_annotations.py
```

**Reference**: `docs/analysis/zotero-improvement-roadmap.md` section 5.0 (Annotation Extraction Query)

---

### 2.3 Incremental Deduplication

**Goal**: Skip re-processing unchanged documents using content fingerprints.

**Steps**:

1. **Create domain model**:
   ```bash
   touch src/domain/models/content_fingerprint.py
   ```

2. **Implement `ContentFingerprint` entity**:
   - Fields: `content_hash`, `file_mtime`, `file_size`, `embedding_model`, policy versions
   - Validation in `__post_init__()`
   - `matches()` method for comparison

3. **Create domain service**:
   ```bash
   touch src/domain/services/content_fingerprint.py
   ```

4. **Implement fingerprint computation**:
   ```python
   def compute_fingerprint(
       file_path: Path,
       embedding_model: str,
       chunking_policy_version: str,
       embedding_policy_version: str,
   ) -> ContentFingerprint:
       # Read first 1MB of file
       # Include file size + policy versions in hash
       # Return ContentFingerprint with hash and metadata
   ```

5. **Enhance `DownloadManifestAttachment`**:
   - Add `source: str | None` field
   - Add `content_fingerprint: ContentFingerprint | None` field
   - Update `to_dict()` and `from_dict()` methods

6. **Implement deduplication logic in `batch_import_from_zotero`**:
   ```python
   # Before processing document
   stored_fingerprint = manifest_attachment.content_fingerprint
   computed_fingerprint = ContentFingerprintService.compute_fingerprint(...)
   
   if stored_fingerprint and ContentFingerprintService.is_unchanged(stored_fingerprint, computed_fingerprint):
       logger.info(f"Skipping unchanged document: {attachment_key}")
       continue  # Skip processing
   
   # Process document, then store fingerprint
   manifest_attachment.content_fingerprint = computed_fingerprint
   ```

**Testing**:
```bash
uv run pytest tests/integration/test_zotero_deduplication.py
```

**Reference**: `docs/analysis/zotero-improvement-roadmap.md` section 5.0 (Content Hash Pattern)

---

## Phase 3: Governance & UX (Week 5)

### 3.1 Embedding Model Diagnostics

**Goal**: Enhance write-guard with friendly error messages.

**Steps**:

1. **Enhance error message in `QdrantIndexAdapter`**:
   ```python
   if stored_model != requested_model:
       raise EmbeddingModelMismatch(
           f"Collection '{collection_name}' is bound to embedding model "
           f"'{stored_model}'. You requested '{requested_model}'. "
           f"Use `reindex --force-rebuild` to migrate to the new model, "
           f"or switch back to '{stored_model}'."
       )
   ```

2. **Add CLI command**:
   ```bash
   # In src/infrastructure/cli/commands/inspect.py
   @app.command()
   def inspect(
       project: str,
       show_embedding_model: bool = False,
   ):
       if show_embedding_model:
           # Query collection metadata for embed_model
           # Display friendly output
   ```

3. **Enhance MCP tool**:
   - Add embedding model to `inspect` tool response
   - Include in status/inspect responses

**Testing**:
```bash
uv run pytest tests/unit/test_qdrant_index.py::test_embedding_model_mismatch_error
```

---

### 3.2 Library Browsing Commands

**Goal**: Add CLI commands for offline library exploration.

**Steps**:

1. **Create CLI file**:
   ```bash
   touch src/infrastructure/cli/commands/zotero.py
   ```

2. **Implement commands**:
   ```python
   @app.command()
   def list_collections():
       """List Zotero collections with hierarchy."""
       adapter = LocalZoteroDbAdapter()
       collections = adapter.list_collections()
       # Display with hierarchy and item counts
   
   @app.command()
   def browse_collection(collection_name: str):
       """Browse items in a collection."""
       adapter = LocalZoteroDbAdapter()
       items = adapter.get_collection_items(...)
       # Display first 20 items with metadata
   
   @app.command()
   def list_tags():
       """List tags with usage counts."""
       adapter = LocalZoteroDbAdapter()
       tags = adapter.list_tags()
       # Display tags with counts
   
   @app.command()
   def recent_items(limit: int = 10):
       """Show recently added items."""
       adapter = LocalZoteroDbAdapter()
       items = adapter.get_recent_items(limit)
       # Display items with dates
   ```

3. **Register commands in `main.py`**:
   ```python
   from .commands import zotero
   app.add_typer(zotero.app, name="zotero")
   ```

**Testing**:
```bash
# Manual testing with local Zotero installation
citeloom zotero list-collections
citeloom zotero browse-collection "My Collection"
```

---

### 3.3 Payload Enrichment

**Goal**: Add Zotero keys to chunk payloads and create indexes.

**Steps**:

1. **Enhance payload creation in `ingest_document` use case**:
   ```python
   payload = {
       # Existing fields...
       "zotero": {
           "item_key": item_key,
           "attachment_key": attachment_key,
       },
   }
   ```

2. **Create indexes in `QdrantIndexAdapter.ensure_collection()`**:
   ```python
   collection.create_payload_index(
       field_name="zotero.item_key",
       field_schema=PayloadSchemaType.KEYWORD
   )
   collection.create_payload_index(
       field_name="zotero.attachment_key",
       field_schema=PayloadSchemaType.KEYWORD
   )
   ```

3. **Update payload schema documentation**:
   - Document new `zotero` fields in payload structure

**Testing**:
```bash
uv run pytest tests/integration/test_qdrant_index.py::test_zotero_key_indexes
```

---

## Configuration

### Update `citeloom.toml` Schema

Add Zotero configuration section:

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

### Update Settings Class

In `src/infrastructure/config/settings.py`:

```python
class ZoteroSettings(BaseModel):
    mode: Literal["local-first", "web-first", "auto", "local-only", "web-only"] = "web-first"
    db_path: str | None = None
    storage_dir: str | None = None
    include_annotations: bool = False
    prefer_zotero_fulltext: bool = True

class CiteLoomSettings(BaseSettings):
    # ... existing fields ...
    zotero: ZoteroSettings = ZoteroSettings()
```

---

## Testing Strategy

### Unit Tests

- **Domain models**: `ContentFingerprint` validation and comparison
- **Source router**: Strategy logic with doubles for ports (no real I/O)
- **Fulltext resolver**: Quality validation logic (mocked database)
- **Annotation resolver**: Normalization logic (mocked Web API)

### Integration Tests

- **Local DB adapter**: Profile detection, SQL queries, path resolution
- **Full-text reuse**: End-to-end import with fulltext preference
- **Annotation indexing**: Fetch and index annotations
- **Deduplication**: Re-import unchanged collection (skip processing)
- **Source router**: Strategy modes and fallback logic

### Platform Testing

- Windows: Profile path detection (`%APPDATA%\Zotero\...`)
- macOS: Profile path detection (`~/Library/Application Support/Zotero/...`)
- Linux: Profile path detection (`~/.zotero/zotero/...`)

---

## Common Pitfalls

1. **SQLite immutable mode**: Must use URI mode with absolute path
2. **Profile detection**: Handle missing `profiles.ini` gracefully
3. **Path resolution**: Validate file exists before returning path
4. **Fulltext quality**: Don't use corrupted or incomplete fulltext
5. **Annotation indexing**: Handle rate limits with retry logic
6. **Deduplication**: Include policy versions in hash (invalidates on policy changes)
7. **Source routing**: Per-file routing (not collection-level) for flexibility

---

## Next Steps

1. **Start with Phase 1.1**: Local SQLite adapter (foundational)
2. **Implement Phase 1.2**: Source router (enables flexible workflows)
3. **Continue with Phase 2**: Full-text reuse and annotation indexing (high value)
4. **Complete Phase 3**: Governance and UX enhancements (polish)

**Reference Documents**:
- `specs/005-zotero-improvements/spec.md`: Full feature specification
- `specs/005-zotero-improvements/research.md`: Implementation patterns
- `specs/005-zotero-improvements/data-model.md`: Entity definitions
- `specs/005-zotero-improvements/contracts/ports.md`: Port interfaces
- `docs/analysis/zotero-improvement-roadmap.md`: Reference implementation patterns

---

**Quickstart Status**: ✅ Complete - Ready for implementation.

