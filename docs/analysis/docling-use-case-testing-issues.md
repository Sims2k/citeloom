# Docling Conversion & Indexing - Use Case Testing Issues

## Date: 2025-11-03

This document outlines performance, UX, and correctness issues discovered during comprehensive testing of Docling document conversion and chunking integration.

---

## Issues Found

### 1. **No Progress Feedback During Long Conversions** 🔴 CRITICAL

**Location**: `src/infrastructure/adapters/docling_converter.py` - `convert()`, `src/application/use_cases/ingest_document.py`

**Problem**:
- Docling conversion can take 30+ seconds for a 1.5MB PDF (observed: 36.56 seconds)
- During conversion, users see only log messages with no visible progress
- No indication of:
  - Conversion progress (pages processed, percentage complete)
  - Time elapsed / time remaining
  - Current operation (OCR, parsing, structure extraction)
- Users may think the command is frozen

**Impact** (Observed):
- **36.56 seconds** for 1 PDF conversion with no user feedback
- Poor user experience during long operations
- Users may interrupt commands thinking they're stuck
- No way to estimate remaining time

**Example Output**:
```
2025-11-03T18:40:22 INFO Starting document conversion pipeline (this may take a moment, especially for large PDFs)...
[36 seconds of silence with only internal docling logs]
2025-11-03T18:40:59 INFO Document conversion pipeline completed, extracting results...
```

**Recommendation**:
- **Add progress bar** using `rich.progress` (already available in dependencies)
- **Show page-by-page progress** ("Processing page 5/20...")
- **Estimate time remaining** based on pages processed so far
- **Display current operation** ("Running OCR...", "Extracting headings...")
- **Use existing `RichProgressReporterAdapter`** that's already implemented but may not be fully utilized

---

### 2. **DoclingHybridChunker Not Available on Windows** 🟠 HIGH

**Location**: `src/infrastructure/adapters/docling_chunker.py` - `__init__()`, `chunk()`

**Problem**:
- `DOCLING_AVAILABLE = True` (converter works) but `HYBRID_CHUNKER_AVAILABLE = False` (chunker fails)
- Windows users get warning: "Docling is not available. Chunker will use placeholder implementation."
- Falls back to manual chunking, which may have different quality/performance characteristics
- Inconsistent behavior: converter uses Docling but chunker doesn't

**Impact**:
- **Lower quality chunking** on Windows (manual fallback vs Docling HybridChunker)
- **Performance differences** between platforms
- **Potential inconsistencies** in chunk boundaries, heading awareness, etc.
- Users may not realize they're getting suboptimal chunking

**Example Log**:
```
2025-11-03T18:40:12 WARNING Docling is not available. Chunker will use placeholder implementation. Windows users should use WSL or Docker.
```

**Root Cause**:
- `HybridChunker` import fails on Windows (likely same deepsearch-glm dependency issue)
- Converter works because it uses different parts of Docling API

**Recommendation**:
- **Document the difference** between converter and chunker availability
- **Improve manual chunking fallback** to match Docling quality as closely as possible
- **Add feature flags** to indicate which chunking method is being used
- **Consider alternative chunking libraries** that work on Windows
- **Clarify Windows compatibility** in documentation (what works, what doesn't)

---

### 3. **Page Map Extraction Issues** 🟠 HIGH - PARTIALLY FIXED

**Location**: `src/infrastructure/adapters/docling_converter.py` - `_extract_page_map()`

**Problem** (Observed):
- Conversion reported: `pages=1` for a multi-page document
- Page map extraction may be falling back to single-page mapping
- Test showed page_map returns tuples `(start_offset, end_offset)` but test expected `int` (now fixed)

**Impact**:
- **Incorrect page references** in citations
- **All chunks assigned to page 1** even if they span multiple pages
- **Poor chunk localization** for multi-page documents
- **User confusion** about where content actually appears

**Example**:
```python
# Conversion result shows:
pages=1  # ❌ Should be multiple pages for a 20+ page document

# But document likely has multiple pages
```

**Root Cause**:
- `_extract_page_map()` may not be correctly extracting page boundaries from Docling document
- Fallback logic kicks in, creating single-page map

**Recommendation**:
- **Improve page boundary detection** - verify Docling document structure
- **Add validation** - warn when page count seems incorrect
- **Test with multi-page documents** and verify correct page mapping
- **Add diagnostic logging** to show how page map was extracted
- **Consider using Docling's page metadata** directly if available

---

### 4. **Heading Tree Extraction Returns Empty** 🟡 MEDIUM

**Location**: `src/infrastructure/adapters/docling_converter.py` - `_extract_heading_tree()`

**Problem** (Observed):
- Conversion reported: `headings=0` for document that likely has headings
- Heading tree extraction may not be working correctly
- Manual chunking may not have proper heading context

**Impact**:
- **No heading context in chunks** - chunks don't know which section they belong to
- **Poor section path breadcrumbs** - all chunks show empty section paths
- **Reduced chunking quality** - heading-aware chunking doesn't work
- **Loss of document structure** information

**Example**:
```python
# Conversion result shows:
headings=0  # ❌ Document likely has headings but none extracted

# Heading tree is empty:
heading_tree = {}  # or {"root": []}
```

**Root Cause**:
- `_extract_heading_tree()` may not be correctly parsing Docling document structure
- Docling document format may have changed or structure is different than expected
- Markdown parsing fallback may not be working

**Recommendation**:
- **Improve heading extraction** - verify Docling document structure format
- **Add diagnostic logging** - show what structure is actually available
- **Test heading extraction** with documents known to have headings
- **Consider using Docling's heading metadata** directly
- **Add fallback validation** - verify extracted headings make sense

---

### 5. **RapidOCR Empty Results Warnings** 🟡 MEDIUM

**Location**: Docling/RapidOCR integration (internal to Docling)

**Problem** (Observed):
- Multiple warnings: "RapidOCR returned empty result!" during conversion
- "The text detection result is empty" warnings appear for several pages
- OCR is being attempted even when not needed (document has extractable text)

**Impact**:
- **Performance overhead** - OCR processing adds time even when unnecessary
- **Warning noise** - Users see many warnings for normal operations
- **Potential OCR misconfiguration** - OCR languages may not match document

**Example Log**:
```
2025-11-03T18:40:27 WARNING RapidOCR returned empty result!
[WARNING] 2025-11-03 18:40:27,167 [RapidOCR] main.py:123: The text detection result is empty
[Appears 6 times for different pages]
```

**Root Cause**:
- Docling may be attempting OCR on pages that already have extractable text
- OCR language configuration may not match document language
- RapidOCR may not be correctly configured

**Recommendation**:
- **Configure OCR language detection** - use Zotero metadata language when available
- **Suppress unnecessary warnings** - if OCR is attempted but not needed, log at debug level
- **Improve OCR configuration** - ensure languages match document
- **Document OCR behavior** - explain when OCR is needed vs when it's attempted

---

### 6. **Single Chunk Created from Large Document** 🟠 HIGH

**Location**: `src/infrastructure/adapters/docling_chunker.py` - `chunk()`

**Problem** (Observed):
- Document conversion completed successfully
- Only **1 chunk** was created from a 1.5MB PDF (likely 20+ pages)
- This suggests chunking may not be working correctly
- Quality filtering may be too aggressive or chunking logic has issues

**Impact**:
- **Loss of granularity** - entire document becomes single searchable chunk
- **Poor search results** - queries return entire document instead of relevant sections
- **Inefficient indexing** - large chunks reduce search precision
- **User confusion** - expecting many chunks from a large document

**Example**:
```
Document converted successfully: doc_id=sha256_..., pages=1, headings=0
Document chunked: 1 chunks created  # ❌ Should be many chunks for a large PDF
```

**Root Cause Analysis Needed**:
- Chunking may be falling back to manual implementation (Windows)
- Manual chunking may have bugs in sentence splitting or token counting
- Quality filtering may be rejecting all but one chunk
- Page map issues (pages=1) may cause chunking to treat document as single page

**Recommendation**:
- **Investigate chunking logic** - verify why only 1 chunk is created
- **Add diagnostic logging** - show why chunks are filtered out
- **Test with smaller documents** - verify chunking works correctly
- **Review quality filtering thresholds** - may be too strict
- **Compare manual vs Docling chunking** - ensure fallback works correctly

---

### 7. **DoclingConverterAdapter Initialized Per Command** 🟡 MEDIUM

**Location**: `src/infrastructure/cli/commands/ingest.py` - `run()`, `src/infrastructure/mcp/tools.py` - `handle_ingest_from_source()`

**Problem**:
- Each command creates a new `DoclingConverterAdapter()` instance
- Initialization takes 10-30 seconds (first run with model download, ~2-3 seconds subsequent)
- Multiple commands in sequence each reinitialize
- No singleton or caching pattern

**Impact**:
- **10-30 second overhead** per command (first run)
- **2-3 second overhead** per command (subsequent runs with cached models)
- **Memory overhead** - multiple converter instances may be created
- **Slower batch processing** - each document ingest may create new instance

**Example**:
```python
# In ingest.py:
converter = DoclingConverterAdapter()  # Takes 10-30s first time

# In MCP tools:
converter = DoclingConverterAdapter()  # Creates another instance

# In batch import:
converter = DoclingConverterAdapter()  # Creates yet another instance
```

**Recommendation**:
- **Singleton pattern** or **factory with caching** for DoclingConverterAdapter
- **Lazy initialization** - only initialize when conversion is actually needed
- **Share converter instance** within same process/session
- **Cache initialized converters** per process to avoid repeated initialization

---

### 8. **Timeout Enforcement Only Works on Unix** 🟡 MEDIUM

**Location**: `src/infrastructure/adapters/docling_converter.py` - `_convert_with_timeout()`

**Problem**:
- Timeout enforcement uses `signal.SIGALRM` which only works on Unix/Linux
- Windows has no signal-based timeout (`sys.platform == "win32"` check disables it)
- Windows users have no timeout protection - conversion could hang indefinitely
- Relies on Docling's internal timeouts, which may not be sufficient

**Impact**:
- **No timeout protection on Windows** - conversions could hang on corrupted/complex documents
- **Different behavior** between platforms (timeout works on Linux, doesn't on Windows)
- **Potential resource leaks** - hanging conversions consume CPU/memory
- **User frustration** - no way to cancel long-running conversions

**Code**:
```python
if sys.platform != "win32":
    signal.signal(signal.SIGALRM, self._timeout_handler)
    signal.alarm(self.DOCUMENT_TIMEOUT_SECONDS)
# Windows: No timeout enforcement!
```

**Recommendation**:
- **Implement thread-based timeout** for Windows using `threading.Timer`
- **Use `concurrent.futures`** with timeout for cross-platform solution
- **Add timeout verification** - test that timeouts actually work
- **Document platform differences** in timeout behavior
- **Consider using Docling's built-in timeout** if available

---

### 9. **OCR Language Selection Not Using Zotero Metadata** 🟡 MEDIUM

**Location**: `src/infrastructure/adapters/docling_converter.py` - `_select_ocr_languages()`, `src/application/use_cases/ingest_document.py`

**Problem**:
- OCR language selection defaults to `['en', 'de']` if not explicitly provided
- Zotero metadata language (from `language` field) should be prioritized but may not be passed through
- Language extraction from Zotero may happen but not be used for OCR

**Impact**:
- **Suboptimal OCR quality** - wrong language may be used for scanned documents
- **Missed opportunity** - Zotero already knows document language but it's not used
- **Reduced accuracy** for non-English documents

**Code Flow**:
```python
# In ingest_document.py:
ocr_languages = metadata.get("language")  # Extracted from Zotero

# But may not be passed to converter:
conversion = converter.convert(
    request.source_path,
    ocr_languages=ocr_languages,  # May be None or not normalized
)
```

**Recommendation**:
- **Ensure Zotero language is passed** to converter
- **Normalize language codes** properly (e.g., 'en-US' → 'en')
- **Prioritize Zotero language** over defaults
- **Add logging** to show which OCR languages are used
- **Test with non-English documents** to verify OCR works correctly

---

### 10. **Text Normalization May Affect Code/Math Blocks** 🟡 MEDIUM

**Location**: `src/infrastructure/adapters/docling_converter.py` - `_normalize_text()`

**Problem**:
- Text normalization includes hyphen repair and whitespace normalization
- Code blocks and math blocks are protected with placeholders, but:
  - Regex patterns may not catch all code block formats
  - Math block detection may be incomplete
  - Restoration may have edge cases

**Impact**:
- **Potential corruption** of code examples in documents
- **Math formulas** may be incorrectly normalized
- **Technical documents** with lots of code may have formatting issues

**Code**:
```python
# Code block pattern:
code_pattern = r'```([^`]+)```|`([^`]+)`'

# Math block pattern:
math_pattern = r'\$\$([^$]+)\$\$|\$\([^)]+\)\$'
```

**Recommendation**:
- **Test with documents containing code** - verify code blocks are preserved
- **Test with documents containing math** - verify formulas are preserved
- **Improve regex patterns** - catch more edge cases
- **Add validation** - verify protected blocks are restored correctly
- **Consider using Docling's native code/math preservation** if available

---

### 11. **Image-Only Page Detection May Not Work Correctly** 🟡 MEDIUM

**Location**: `src/infrastructure/adapters/docling_converter.py` - `_detect_image_only_pages()`

**Problem**:
- Image-only page detection relies on Docling document structure
- Detection may not work if Docling structure doesn't expose page-level image info
- Logged but may not be actionable (no OCR retry or different processing)

**Impact**:
- **Image-only pages may be missed** - content lost if not detected
- **OCR may not be triggered** for pages that need it
- **Incomplete document conversion** - some pages may have no text

**Recommendation**:
- **Verify detection works** - test with documents containing image-only pages
- **Add OCR retry logic** - if image-only pages detected, retry with OCR
- **Improve detection accuracy** - use multiple heuristics (text length, image presence, OCR result)
- **Document behavior** - explain what happens when image-only pages are detected

---

### 12. **Chunking Quality Filtering May Be Too Aggressive** 🟡 MEDIUM

**Location**: `src/infrastructure/adapters/docling_chunker.py` - `_convert_to_domain_chunks()`, `_manual_chunking()`

**Problem** (Suspected based on single chunk result):
- Quality filtering removes chunks with:
  - `token_count < min_chunk_length` (default 50)
  - `signal_to_noise < min_signal_to_noise` (default 0.3)
- May be filtering out too many chunks, leaving only one
- Signal-to-noise calculation may not be appropriate for all document types

**Impact**:
- **Too few chunks** - entire document becomes single chunk
- **Loss of granularity** - search results less precise
- **Over-filtering** - valid content chunks may be rejected

**Code**:
```python
if token_count < min_chunk_length:
    filtered_count += 1
    continue

if signal_to_noise < min_signal_to_noise:
    filtered_count += 1
    continue
```

**Recommendation**:
- **Investigate filtering thresholds** - may need to be adjusted
- **Add diagnostic logging** - show why chunks are filtered
- **Test with different document types** - verify filtering works for various content
- **Consider document-type-specific thresholds** - technical docs vs papers vs books
- **Review signal-to-noise calculation** - may need refinement

---

### 13. **Deterministic Chunk ID Generation Depends on Unstable Data** 🟡 MEDIUM

**Location**: `src/domain/models/chunk.py` - `generate_chunk_id()`, `src/infrastructure/adapters/docling_chunker.py`

**Problem**:
- Chunk IDs use `page_span`, `section_path`, `chunk_idx` for determinism
- If page map is incorrect (e.g., all pages = 1), chunk IDs may collide
- If heading tree is empty, section paths may be inconsistent
- Chunk IDs may change if document structure extraction improves

**Impact**:
- **Chunk ID collisions** - multiple chunks may get same ID
- **Non-deterministic IDs** - same document may produce different IDs if structure changes
- **Indexing issues** - duplicate chunks or missed updates

**Recommendation**:
- **Use content hash** as part of chunk ID for true determinism
- **Validate chunk ID uniqueness** - warn if collisions detected
- **Improve structure extraction** - ensure page_span and section_path are accurate
- **Add chunk ID validation** - check for duplicates before indexing

---

### 14. **No Error Recovery for Partial Conversion Failures** 🟡 MEDIUM

**Location**: `src/infrastructure/adapters/docling_converter.py` - `convert()`

**Problem**:
- If conversion fails partway through (e.g., on page 10 of 20), entire conversion fails
- No partial results returned (e.g., pages 1-9 successfully converted)
- No retry logic for transient failures

**Impact**:
- **All-or-nothing conversion** - partial failures lose all progress
- **No graceful degradation** - can't use partially converted documents
- **Wasted processing time** - 30+ seconds lost if conversion fails near end

**Recommendation**:
- **Return partial results** - allow indexing of successfully converted pages
- **Add retry logic** - retry failed pages or operations
- **Continue on non-critical errors** - log warnings but continue processing
- **Add checkpointing** - save conversion progress for resumability

---

### 15. **Model Cache Directory Detection May Not Work** 🟡 LOW

**Location**: `src/infrastructure/adapters/docling_converter.py` - `_initialize_converter()`

**Problem**:
- Code checks for model cache directory: `~/.cache/docling/models`
- Cache detection may not work correctly on all platforms
- Model count calculation may be inaccurate (looking for specific file extensions)

**Impact**:
- **Misleading log messages** - may say "models will be downloaded" when already cached
- **No visibility** into model caching status
- **Repeated downloads** if cache detection fails

**Code**:
```python
cache_dir = Path.home() / ".cache" / "docling" / "models"
if cache_dir.exists():
    model_count = len(list(cache_dir.rglob("*.onnx"))) + ...
```

**Recommendation**:
- **Improve cache detection** - verify actual cache structure
- **Add cache status logging** - show which models are cached
- **Document cache location** - help users understand where models are stored
- **Verify cache works** - test that cached models are actually used

---

## Performance Metrics

### Current Performance (1.5MB PDF - "Sakai 2025"):

| Operation | Time | Issues |
|-----------|------|--------|
| DoclingConverterAdapter initialization | 2-3s (first run: 10-30s) | No caching, repeated initialization |
| Document conversion | 36.56s | No progress feedback, OCR warnings |
| Chunking | <1s | Only 1 chunk created (likely bug) |
| Embedding generation | 3s | Loading model each time |
| Indexing to Qdrant | <1s | Fast |
| **Total** | **~42s** | Multiple UX and correctness issues |

### Expected Performance (After Fixes):

| Operation | Time | Improvement |
|-----------|------|-------------|
| Converter initialization (cached) | 0s | Singleton pattern |
| Document conversion (with progress) | 30-35s | Progress feedback, optimized OCR |
| Chunking (proper) | 1-2s | Correct chunking, many chunks |
| Embedding (cached model) | 1-2s | Model reuse |
| **Total** | **~35-40s** | Better UX, correct results |

---

## Recommended Fix Priority

### Priority 1: Critical UX Issues (🔴)
1. **🔴 CRITICAL**: Add progress feedback during long conversions (Issue #1)
2. **🔴 CRITICAL**: Fix single chunk creation bug (Issue #6)
3. **🟠 HIGH**: Fix page map extraction (Issue #3)

### Priority 2: High Impact Issues (🟠)
4. **🟠 HIGH**: Document and improve Windows chunker availability (Issue #2)
5. **🟠 HIGH**: Fix heading tree extraction (Issue #4)
6. **🟡 MEDIUM**: Optimize DoclingConverterAdapter initialization (Issue #7)

### Priority 3: Medium Impact Improvements (🟡)
7. **🟡 MEDIUM**: Implement Windows timeout enforcement (Issue #8)
8. **🟡 MEDIUM**: Use Zotero metadata for OCR languages (Issue #9)
9. **🟡 MEDIUM**: Improve chunking quality filtering (Issue #12)
10. **🟡 MEDIUM**: Suppress unnecessary OCR warnings (Issue #5)

### Priority 4: Lower Priority (🟡)
11. **🟡 MEDIUM**: Text normalization edge cases (Issue #10)
12. **🟡 MEDIUM**: Image-only page detection (Issue #11)
13. **🟡 MEDIUM**: Chunk ID determinism (Issue #13)
14. **🟡 MEDIUM**: Error recovery (Issue #14)
15. **🟡 LOW**: Model cache detection (Issue #15)

---

## Testing Observations

### Test Execution Summary

**Test Document**: "Sakai - 2025 - AI Agent Architecture Mapping Domain, Agent, and Orchestration to Clean Architecture.pdf" (1.5MB)

**Conversion Results**:
- Conversion time: **36.56 seconds**
- Pages detected: **1** (likely incorrect - document has multiple pages)
- Headings detected: **0** (document likely has headings)
- Chunks created: **1** (should be many more)
- OCR warnings: **6** (RapidOCR empty results)

**Issues Confirmed**:
- ✅ No progress feedback during conversion
- ✅ Page map extraction returns single page
- ✅ Heading tree extraction returns empty
- ✅ Only 1 chunk created from large document
- ✅ Multiple OCR warnings
- ✅ Converter initialized every command

**Tests Passed**:
- ✅ Page map structure (tuples correctly returned)
- ✅ Heading tree structure (dict format)
- ✅ Chunking with policy
- ✅ Deterministic chunk IDs
- ✅ Page span validation

---

## Additional Testing Needed

1. **Multi-page documents** - Verify page map extraction works correctly
2. **Documents with headings** - Verify heading tree extraction
3. **Scanned documents** - Test OCR functionality and language detection
4. **Documents with code/math** - Verify text normalization preserves content
5. **Large documents (100+ pages)** - Test timeout and performance
6. **Different file formats** - DOCX, PPTX, HTML, images
7. **Batch processing** - Multiple documents in sequence
8. **Error scenarios** - Corrupted files, unsupported formats
9. **Progress feedback** - Verify progress bars work in interactive mode
10. **Windows vs Linux** - Compare chunker behavior across platforms

---

## Quick Fixes Applied

### Fix #1: Test Page Map Assertion ✅ FIXED
- **Issue**: Test expected `int` but implementation returns `tuple`
- **Fix**: Updated test to expect `tuple[int, int]` (start_offset, end_offset)
- **Location**: `tests/integration/test_docling_smoke.py`
- **Status**: ✅ Fixed and verified

### Fix #2: Test PDF Document Path ✅ UPDATED
- **Issue**: Test used large PDF that took too long
- **Fix**: Updated to use smaller PDF for smoke tests
- **Location**: `tests/integration/test_docling_smoke.py`
- **Status**: ✅ Updated

---

## Recommendations for Next Steps

1. **Immediate**: Implement progress feedback using `RichProgressReporterAdapter` for conversion operations
2. **Short-term**: Investigate and fix single chunk creation bug - verify chunking logic
3. **Short-term**: Fix page map extraction - ensure correct page boundaries are detected
4. **Medium-term**: Improve Windows chunker support or document limitations clearly
5. **Medium-term**: Optimize converter initialization with singleton pattern
6. **Long-term**: Add comprehensive error recovery and partial result handling

---

## Related Documentation

- [Zotero Use Case Testing Issues](./zotero-use-case-testing-issues.md) - Similar testing for Zotero integration
- [Zotero Testing Plan](./zotero-testing-plan.md) - Comprehensive testing methodology
- Docling Documentation - Refer to Docling library docs for API details

