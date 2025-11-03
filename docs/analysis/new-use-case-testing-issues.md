# New Use Case Testing Issues - Zotero & Docling Integration

## Date: 2025-11-03

This document outlines issues discovered during additional use case testing of Zotero ingestion, Docling conversion, and indexing workflows using various CLI commands.

---

## Testing Performed

### Use Case 1: Zotero Collection Listing
**Command**: `uv run citeloom zotero list-collections`

**Results**:
- ✅ Successfully listed 9 collections with hierarchy
- ⚠️ Performance: ~18 seconds to list 9 collections
- ⚠️ Makes item count API calls for every collection sequentially

**Observations**:
- Each collection requires a separate API call to count items: `GET /api/users/0/collections/{key}/items`
- For 9 collections: 10 API calls (1 for collections list + 9 for item counts)
- No progress indication during long operations
- Local adapter unavailable warning (falls back to web API which uses localhost)

---

### Use Case 2: Browsing Specific Collection
**Command**: `uv run citeloom zotero browse-collection --collection "Clean Code" --limit 5`

**Results**:
- ✅ Successfully displayed 5 items with metadata
- ⚠️ Performance: ~35 seconds for 5 items
- 🔴 **CRITICAL**: Redundant collection API calls observed

**Detailed API Call Analysis** (from logs):
```
GET /api/users/0/collections?format=json                    # Find collection by name
GET /api/users/0/collections/6EAXG8AV/items?format=json   # Get collection items
GET /api/users/0/items/V3A4DNVB?format=json                # Item 1 metadata
GET /api/users/0/collections/6EAXG8AV?format=json          # ❌ Redundant collection lookup
GET /api/users/0/items/V3A4DNVB/children?format=json        # Item 1 attachments
GET /api/users/0/items/3HBT29U8?format=json                 # Item 2 metadata
GET /api/users/0/collections/6EAXG8AV?format=json          # ❌ Same collection again!
GET /api/users/0/items/3HBT29U8/children?format=json        # Item 2 attachments
[... repeats for each item ...]
```

**Issues Identified**:
1. **Redundant Collection Lookups**: Same collection (6EAXG8AV) fetched 5+ times
   - Each `get_item_metadata()` call internally fetches collection info
   - We already know the collection key in `browse_collection()`
   - No caching of collection metadata

2. **API Call Overhead**:
   - 5 items × 3 calls each = 15 API calls minimum
   - Plus redundant collection lookups = 20+ total API calls
   - ~2 seconds per API call = 35+ seconds total

---

### Use Case 3: Download from Zotero Collection
**Command**: `uv run citeloom ingest download --zotero-collection "Clean Code" --include-subcollections`

**Results**:
- ✅ Successfully detected existing downloads (4 items)
- ✅ Fast execution (skipped download since files exist)
- ✅ Manifest correctly created/updated

**Observations**:
- Download phase works correctly with manifest tracking
- Fingerprint-based deduplication prevents duplicate downloads
- No issues observed (files already existed from previous download)

---

### Use Case 4: Docling Document Conversion
**Command**: `uv run citeloom ingest run --project citeloom/clean-arch "assets\zotero_downloads\6EAXG8AV\Sakai - 2025 - AI Agent Architecture Part 3 Governance, Monitoring, and Cost Control.pdf"`

**Results**:
- ✅ Document converted successfully
- ✅ Indexed to Qdrant (1 chunk)
- ⚠️ Performance: ~33 seconds for conversion
- 🔴 **CRITICAL**: Only 1 chunk created from multi-page document
- 🔴 **CRITICAL**: Page count reported as 1 (incorrect)
- 🔴 **CRITICAL**: Heading count reported as 0

**Detailed Metrics**:
```
Conversion time: 33.69 seconds
Pages detected: 1 (❌ incorrect - document has multiple pages)
Headings detected: 0 (❌ document likely has headings)
Chunks created: 1 (❌ should be many more for a multi-page document)
```

**Issues Identified**:

1. **Single Chunk Creation Bug** 🔴 CRITICAL
   - Multi-page document (20+ pages) produces only 1 chunk
   - This is a regression/confirmation of existing issue #6
   - Likely related to page map extraction issues
   - Manual chunking fallback on Windows may have bugs

2. **Page Map Extraction** 🔴 CRITICAL
   - Reports `pages=1` for clearly multi-page document
   - Confirms existing issue #3
   - Page boundaries not correctly detected
   - All content assigned to page 1

3. **Heading Tree Extraction** 🔴 CRITICAL
   - Reports `headings=0` despite document structure
   - Confirms existing issue #4
   - Heading-aware chunking cannot work without headings
   - Section paths will be empty

4. **No Progress Feedback** 🟠 HIGH
   - 33 seconds of conversion with no user feedback
   - Only log messages, no progress bar
   - User cannot tell if command is stuck or working
   - Confirms existing issue #1

5. **RapidOCR Warnings** 🟡 MEDIUM
   - Multiple "RapidOCR returned empty result!" warnings
   - OCR attempted even when not needed (document has extractable text)
   - Warning noise makes logs harder to read

6. **DoclingConverterAdapter Initialization** 🟡 MEDIUM
   - Initialized on every command (not singleton)
   - Takes ~2-3 seconds even with cached models
   - Could be shared across operations in same process

7. **Windows Chunker Limitation** 🟡 MEDIUM
   - Warning: "Docling is not available. Chunker will use placeholder implementation."
   - Falls back to manual chunking on Windows
   - May contribute to single chunk issue

---

### Use Case 5: Query After Ingestion
**Command**: `uv run citeloom query run --project citeloom/clean-arch --query "governance" --top-k 2`

**Results**:
- ❌ **Query Failed**: "Hybrid search not supported: dense model not bound to collection"

**Error Details**:
```
Query failed: Hybrid search not supported for project 'citeloom/clean-arch': 
dense model not bound to collection (call set_model() first)
```

**Root Cause**:
- Project configuration may require model binding step
- Collection exists in Qdrant but model not properly initialized
- May be a configuration issue rather than code bug

**Workaround Needed**:
- May need to set model explicitly or check project configuration
- Hybrid search requires model binding before use

---

## New Issues Discovered

### Issue 19: Redundant Collection Metadata Lookups in Browse Collection 🔴 CRITICAL

**Location**: `src/infrastructure/cli/commands/zotero.py` - `browse_collection()`, `src/infrastructure/adapters/zotero_importer.py` - `get_item_metadata()`

**Problem** (Observed during testing):
- `browse_collection()` already knows the collection key (e.g., `6EAXG8AV`)
- When fetching metadata for each item, `get_item_metadata()` internally calls `self.zot.collection(coll_key)` for each collection the item belongs to
- For items in the same collection, this causes the same collection to be looked up multiple times
- **Observed**: Collection `6EAXG8AV` was fetched **5 times** for 5 items in the same collection

**Impact**:
- **5+ redundant API calls** per collection when browsing
- **~2 seconds overhead** per redundant lookup
- **Poor performance**: 35+ seconds to browse 5 items
- **Wasteful API quota usage**

**Example from Test**:
```
# Browsing "Clean Code" collection (key: 6EAXG8AV) with 5 items:
GET /api/users/0/items/V3A4DNVB          # Item 1 metadata
GET /api/users/0/collections/6EAXG8AV      # ❌ Redundant - we're already browsing this collection!
GET /api/users/0/items/3HBT29U8            # Item 2 metadata  
GET /api/users/0/collections/6EAXG8AV      # ❌ Same collection again!
GET /api/users/0/items/827PZH35            # Item 3 metadata
GET /api/users/0/collections/6EAXG8AV      # ❌ And again!
[... 2 more redundant calls ...]
```

**Root Cause**:
- `get_item_metadata()` in `ZoteroImporterAdapter` (line 465) fetches collection names by calling `self.zot.collection(coll_key)` for each collection
- No mechanism to pass known collection info or cache collection metadata
- Collection lookup happens even when collection info is already known

**Recommendation**:
1. **Cache collection metadata** at the start of `browse_collection()`
2. **Modify `get_item_metadata()` to accept optional collection cache** parameter
3. **Or skip collection lookup** in `get_item_metadata()` when browsing (collection info already known)
4. **Add collection_cache parameter** to adapter methods or use a context/request-scoped cache

---

### Issue 20: Query Fails with Model Binding Error 🟡 MEDIUM

**Location**: `src/infrastructure/cli/commands/query.py` or query use case

**Problem** (Observed during testing):
- After successful ingestion, query command fails with: "dense model not bound to collection"
- Collection exists in Qdrant (chunks were upserted successfully)
- Model binding step may be missing or not persisted

**Impact**:
- **Cannot query ingested documents** immediately after ingestion
- **Confusing error message** - doesn't explain how to fix
- **Workflow interruption** - user must investigate configuration

**Example Error**:
```
Query failed: Hybrid search not supported for project 'citeloom/clean-arch': 
dense model not bound to collection (call set_model() first)
```

**Possible Causes**:
1. Model binding not persisted to Qdrant collection
2. Query command doesn't bind model before querying
3. Project configuration missing model information
4. Collection created but model binding step skipped

**Recommendation**:
1. **Auto-bind model** during query if not already bound
2. **Verify model binding** after ingestion completes
3. **Improve error message** with actionable guidance
4. **Check project configuration** for required model settings

---

### Issue 21: Verbose HTTP Logging Clutters Output 🟡 MEDIUM

**Location**: HTTP client logging (httpx or similar)

**Problem** (Observed during testing):
- Every HTTP request/response is logged at INFO level
- Logs show: `HTTP Request: GET http://localhost:23119/api/users/0/items/{key} "HTTP/1.0 200 OK"`
- For commands with many API calls, logs become very verbose
- Progress information gets buried in HTTP logs

**Impact**:
- **Hard to see important information** (progress, results, errors)
- **Log files become large** quickly
- **Poor user experience** in interactive mode
- **Difficult to debug** actual issues vs normal API traffic

**Example Output**:
```
2025-11-03 18:59:39,483 - INFO - HTTP Request: GET http://localhost:23119/api/users/0/collections/6EAXG8AV/items?format=json&limit=100&locale=en-US "HTTP/1.0 200 OK"
2025-11-03 18:59:41,537 - INFO - HTTP Request: GET http://localhost:23119/api/users/0/items/V3A4DNVB?format=json&limit=100&locale=en-US "HTTP/1.0 200 OK"
2025-11-03 18:59:43,592 - INFO - HTTP Request: GET http://localhost:23119/api/users/0/collections/6EAXG8AV?format=json&limit=100&locale=en-US "HTTP/1.0 200 OK"
[... 15+ more similar lines ...]
```

**Recommendation**:
1. **Suppress HTTP logs in non-verbose mode** (only show in `--verbose` flag)
2. **Log HTTP requests at DEBUG level** instead of INFO
3. **Add summary logging** (e.g., "Made 20 API calls in 35 seconds")
4. **Use structured logging** to filter by log level in interactive mode

---

### Issue 22: Local Adapter Detection Fails Despite Zotero Running 🟡 MEDIUM

**Location**: `src/infrastructure/cli/commands/zotero.py` - `_get_zotero_adapter()`

**Problem** (Observed during testing):
- Zotero desktop is running (localhost:23119 responds)
- Warning shown: "Local adapter unavailable: Zotero profile not found"
- Falls back to web adapter (which actually uses localhost API)
- Direct SQLite access would be faster but not available

**Impact**:
- **Slower performance** (API overhead vs direct DB access)
- **Confusing warning message** (local API works, but "local adapter" unavailable)
- **Users don't know** they can configure `db_path` explicitly

**Example Warning**:
```
2025-11-03 18:58:56,879 - WARNING - Local adapter unavailable: Zotero profile not found: 
Zotero profile directory. Ensure Zotero is installed and has been run at least once. 
Or provide db_path explicitly via configuration., falling back to web adapter
Note: Local database unavailable (Zotero profile not found...), using web API
2025-11-03 18:58:57,408 - INFO - Zotero client initialized for local access
```

**Note**: Despite the warning, it still works using localhost API (which is fine, but message is confusing)

**Recommendation**:
1. **Improve Windows profile detection** - check more common paths
2. **Clarify warning message** - distinguish between "local DB" and "local API"
3. **Document `db_path` configuration** in setup guide with Windows examples
4. **Add troubleshooting command** to help users find their Zotero profile

---

## Performance Metrics Summary

### Zotero Operations

| Operation | Items/Collections | API Calls | Time | Issues |
|-----------|------------------|-----------|------|--------|
| `list-collections` | 9 collections | ~10 | 18s | Item counting per collection |
| `browse-collection --limit 5` | 5 items | ~20+ | 35s | Redundant collection lookups (5x same collection) |
| `ingest download` | 4 items | ~5 | <1s | Fast (files already exist) |

### Docling Conversion

| Operation | Document | Time | Chunks | Issues |
|-----------|----------|------|--------|--------|
| Conversion | 20+ page PDF | 33.69s | 1 (❌ bug) | Single chunk, pages=1, headings=0 |
| Indexing | 1 chunk | <1s | 1 | Successful |

### Query

| Operation | Result | Issues |
|-----------|--------|--------|
| Query | ❌ Failed | Model binding error |

---

## Quick Fixes Applied

### None Yet
- Issues identified require more investigation or interface changes
- Collection caching fix would require modifying adapter interface
- Will prioritize in next iteration

---

## Recommendations for Next Steps

### Immediate Priority (🔴 CRITICAL)

1. **Fix single chunk creation bug**
   - Investigate why only 1 chunk created from multi-page document
   - Check manual chunking fallback logic on Windows
   - Verify page map extraction is working correctly

2. **Fix page map extraction**
   - Ensure correct page boundaries are detected
   - Validate page count matches actual document pages
   - Add diagnostic logging for page extraction

3. **Fix redundant collection lookups**
   - Add collection metadata caching in `browse_collection()`
   - Modify `get_item_metadata()` to accept optional collection cache
   - Reduce API calls by 50%+ for browsing operations

### High Priority (🟠)

4. **Add progress feedback during conversion**
   - Use `RichProgressReporterAdapter` for conversion operations
   - Show page-by-page progress during Docling conversion
   - Display time remaining estimates

5. **Fix query model binding**
   - Auto-bind model if not already bound
   - Verify model binding after ingestion
   - Improve error message with guidance

### Medium Priority (🟡)

6. **Suppress verbose HTTP logging**
   - Move HTTP logs to DEBUG level
   - Only show in `--verbose` mode
   - Add summary logging instead

7. **Improve local adapter detection**
   - Better Windows profile path detection
   - Clearer warning messages
   - Document configuration options

---

## Test Commands Used

```bash
# Use Case 1: List collections
uv run citeloom zotero list-collections

# Use Case 2: Browse collection
uv run citeloom zotero browse-collection --collection "Clean Code" --limit 5

# Use Case 3: Download from collection
uv run citeloom ingest download --zotero-collection "Clean Code" --include-subcollections

# Use Case 4: Convert and ingest document
uv run citeloom ingest run --project citeloom/clean-arch \
  "assets\zotero_downloads\6EAXG8AV\Sakai - 2025 - AI Agent Architecture Part 3 Governance, Monitoring, and Cost Control.pdf"

# Use Case 5: Query indexed documents
uv run citeloom query run --project citeloom/clean-arch --query "governance" --top-k 2
```

---

## Related Documents

- [Critical Issues Summary](./CRITICAL_ISSUES_SUMMARY.md) - High-level overview of critical issues
- [Zotero Use Case Testing Issues](./zotero-use-case-testing-issues.md) - Previous Zotero testing results
- [Docling Use Case Testing Issues](./docling-use-case-testing-issues.md) - Previous Docling testing results
- [Zotero Testing Plan](./zotero-testing-plan.md) - Comprehensive testing methodology
- [Docling Testing Plan](./docling-testing-plan.md) - Comprehensive testing methodology

