# Docling Conversion & Indexing - Comprehensive Testing Plan

## Testing Plan: Document Conversion & Chunking

This document outlines comprehensive test cases for Docling document conversion and chunking integration, covering edge cases, performance, and correctness validation.

---

## Performance & Correctness Tests

### Test Case 1: Conversion Performance (Small Document)
**Objective**: Measure conversion time and resource usage for small documents

**Test Setup**:
- Document: "Sakai - 2025 - AI Agent Architecture Mapping" (1.5MB PDF)
- Expected: < 60 seconds conversion time

**Commands**:
```bash
# Time the conversion
time uv run citeloom ingest run \
  --project citeloom/test \
  "assets/raw/Sakai - 2025 - AI Agent Architecture Mapping Domain, Agent, and Orchestration to Clean Architecture.pdf"
```

**Metrics to Measure**:
- Total conversion time
- Memory usage during conversion
- CPU usage
- Model loading time (first vs subsequent runs)
- Chunks created

**Expected Results**:
- First run: 30-40s (with model download/initialization)
- Subsequent runs: 25-35s (with cached models)
- Chunks: 10-50 chunks depending on content

**Verify**:
- Progress feedback is shown (if implemented)
- Page map is correct (multiple pages)
- Heading tree contains headings
- Chunks are reasonable size and count

---

### Test Case 2: Conversion Performance (Large Document)
**Objective**: Measure performance with large documents (20+ pages)

**Test Setup**:
- Document: Large PDF (10-20MB, 50-100 pages)
- Test timeout behavior and memory usage

**Commands**:
```bash
uv run citeloom ingest run \
  --project citeloom/test \
  "path/to/large-document.pdf"
```

**Metrics**:
- Conversion time per page
- Memory usage scaling
- Timeout behavior (should not exceed 120s)
- Progress indication

**Edge Cases**:
- Documents approaching 120s timeout limit
- Very high memory usage
- CPU-intensive OCR operations

---

### Test Case 3: Multi-Page Page Map Accuracy
**Objective**: Verify page map correctly identifies page boundaries

**Test Setup**:
- Documents with known page counts (5, 10, 20, 50 pages)
- Documents with mixed content (text, images, tables per page)

**Test Steps**:
1. Convert document
2. Extract page_map from conversion result
3. Verify:
   - Correct number of pages
   - Page offsets are non-overlapping and sequential
   - Each page has (start_offset, end_offset) tuple
   - Offsets match actual text positions

**Expected Results**:
```python
# For 10-page document:
page_map = {
    1: (0, 2543),
    2: (2543, 5124),
    3: (5124, 7890),
    ...
    10: (23456, 26000)
}
# Verify: end_offset of page N == start_offset of page N+1
```

**Commands**:
```bash
# Convert and inspect
uv run python -c "
from src.infrastructure.adapters.docling_converter import DoclingConverterAdapter
converter = DoclingConverterAdapter()
result = converter.convert('test.pdf')
print(f'Pages: {len(result[\"structure\"][\"page_map\"])}')
print(f'Page map: {result[\"structure\"][\"page_map\"]}')
"
```

---

### Test Case 4: Heading Tree Extraction Accuracy
**Objective**: Verify heading tree correctly extracts document structure

**Test Setup**:
- Documents with known heading structure
- Various heading levels (H1, H2, H3, etc.)
- Documents with and without headings

**Test Steps**:
1. Convert document
2. Extract heading_tree
3. Verify:
   - Headings are correctly extracted
   - Hierarchy is preserved (parent-child relationships)
   - Page anchors are correct
   - Heading levels are accurate

**Expected Structure**:
```python
heading_tree = {
    "root": [
        {
            "level": 1,
            "title": "Introduction",
            "page": 1,
            "children": [
                {
                    "level": 2,
                    "title": "Background",
                    "page": 2,
                    "children": []
                }
            ]
        }
    ]
}
```

**Test Documents**:
- Document with clear heading structure
- Document with no headings (should return empty tree)
- Document with deeply nested headings (4+ levels)

---

## Edge Cases: Document Formats

### Test Case 5: PDF Document Varieties
**Objective**: Test conversion with various PDF types

**Test Documents**:
1. **Text-based PDF** (extractable text)
   - Should convert quickly without OCR
   - Verify text quality

2. **Scanned PDF** (image-based, needs OCR)
   - Should trigger OCR automatically
   - Verify OCR language detection
   - Check OCR quality

3. **Mixed PDF** (text + scanned pages)
   - Should use OCR only for scanned pages
   - Verify page-by-page processing

4. **PDF with Forms**
   - Verify form fields are handled
   - Check if form text is extracted

5. **PDF with Tables**
   - Verify table structure is preserved
   - Check table content extraction

6. **PDF with Images**
   - Verify image-only page detection
   - Check if images trigger OCR

**Commands**:
```bash
# Test each PDF type
for pdf in assets/test-pdfs/*.pdf; do
  echo "Testing: $pdf"
  uv run citeloom ingest run --project citeloom/test "$pdf"
done
```

---

### Test Case 6: Other Document Formats
**Objective**: Test conversion with non-PDF formats

**Supported Formats** (from code):
- DOCX (Microsoft Word)
- PPTX (Microsoft PowerPoint)
- HTML
- Images (PNG, JPG, etc.)

**Test Each Format**:
```bash
# DOCX
uv run citeloom ingest run --project citeloom/test "document.docx"

# PPTX
uv run citeloom ingest run --project citeloom/test "presentation.pptx"

# HTML
uv run citeloom ingest run --project citeloom/test "page.html"

# Image
uv run citeloom ingest run --project citeloom/test "diagram.png"
```

**Verify**:
- Conversion succeeds
- Text is extracted correctly
- Structure is preserved where applicable
- Page map (or equivalent) is created

---

## Edge Cases: Chunking

### Test Case 7: Chunking with Different Policies
**Objective**: Test chunking behavior with various policies

**Test Policies**:

**7a. Default Policy**:
```python
ChunkingPolicy(
    max_tokens=450,
    overlap_tokens=60,
    heading_context=2,
    tokenizer_id="minilm"
)
```

**7b. Small Chunks**:
```python
ChunkingPolicy(
    max_tokens=200,
    overlap_tokens=30,
    heading_context=1
)
```

**7c. Large Chunks**:
```python
ChunkingPolicy(
    max_tokens=1000,
    overlap_tokens=100,
    heading_context=3
)
```

**7d. No Overlap**:
```python
ChunkingPolicy(
    max_tokens=450,
    overlap_tokens=0
)
```

**Verify**:
- Chunk count varies appropriately with max_tokens
- Overlap works correctly
- Heading context is included
- Chunk sizes match policy (approximately)

---

### Test Case 8: Chunking Quality Filtering
**Objective**: Test quality filtering thresholds

**Test Scenarios**:

**8a. High Quality Document**:
- Clean text, proper formatting
- Should pass all filters
- Verify signal-to-noise ratio is high

**8b. Low Quality Document**:
- Scanned with OCR errors
- Lots of noise characters
- Some chunks should be filtered

**8c. Mixed Quality Document**:
- Some sections clean, some noisy
- Verify filtering is selective

**8d. Edge Cases**:
- Document with only code (high noise ratio?)
- Document with lots of whitespace
- Very short sections

**Verify**:
- Quality filtering works appropriately
- Not too aggressive (doesn't filter everything)
- Not too lenient (filters obvious noise)
- Diagnostic logging shows why chunks are filtered

---

### Test Case 9: Chunking Deterministic IDs
**Objective**: Verify chunk IDs are deterministic and unique

**Test Steps**:
1. Convert and chunk document twice
2. Compare chunk IDs
3. Verify:
   - Same inputs produce same IDs
   - All IDs are unique (no collisions)
   - IDs are stable across runs

**Commands**:
```python
# Test deterministic IDs
from src.infrastructure.adapters.docling_converter import DoclingConverterAdapter
from src.infrastructure.adapters.docling_chunker import DoclingHybridChunkerAdapter
from src.domain.policy.chunking_policy import ChunkingPolicy

converter = DoclingConverterAdapter()
chunker = DoclingHybridChunkerAdapter()
policy = ChunkingPolicy()

# Convert and chunk twice
result1 = converter.convert("test.pdf")
chunks1 = chunker.chunk(result1, policy)

result2 = converter.convert("test.pdf")
chunks2 = chunker.chunk(result2, policy)

# Verify IDs match
assert len(chunks1) == len(chunks2)
for c1, c2 in zip(chunks1, chunks2):
    assert c1.id == c2.id, f"ID mismatch: {c1.id} != {c2.id}"
```

---

## Edge Cases: OCR

### Test Case 10: OCR Language Detection and Configuration
**Objective**: Test OCR with various languages

**Test Scenarios**:

**10a. Explicit OCR Languages**:
```python
converter.convert(
    "scanned-document.pdf",
    ocr_languages=['en', 'de']
)
```

**10b. Language from Zotero Metadata**:
- Document with `language: "fr"` in Zotero
- Verify OCR uses French

**10c. Multi-language Document**:
- Document with English and German sections
- Test with multiple languages

**10d. Unknown Language**:
- Document with language not in defaults
- Verify fallback behavior

**Verify**:
- OCR languages are correctly selected
- Language normalization works ('en-US' → 'en')
- Default languages used when not specified
- OCR quality is acceptable

---

### Test Case 11: OCR Performance and Quality
**Objective**: Measure OCR performance and verify quality

**Test Documents**:
- Scanned PDF (needs OCR)
- High-resolution scan
- Low-resolution scan
- Mixed text/image document

**Metrics**:
- OCR processing time per page
- OCR accuracy (manual verification)
- Warnings/errors from OCR engine

**Verify**:
- OCR is only used when needed
- OCR quality is acceptable
- Performance is reasonable
- Warnings are informative, not excessive

---

## Edge Cases: Error Handling

### Test Case 12: Invalid/Corrupted Documents
**Objective**: Test error handling for problematic documents

**Test Scenarios**:

**12a. Corrupted PDF**:
- PDF with invalid structure
- Should fail gracefully with clear error

**12b. Non-existent File**:
- File path doesn't exist
- Should raise FileNotFoundError

**12c. Unsupported Format**:
- File with unsupported extension
- Should fail with clear error message

**12d. Empty File**:
- Zero-byte file
- Should handle gracefully

**12e. Very Large File**:
- File approaching memory limits
- Should handle or fail gracefully

**Verify**:
- Errors are clear and actionable
- No crashes or hangs
- Appropriate error messages
- Graceful failure (doesn't corrupt state)

---

### Test Case 13: Timeout Handling
**Objective**: Test timeout behavior for long operations

**Test Scenarios**:

**13a. Document Near Timeout**:
- Document that takes ~110 seconds (just under 120s limit)
- Should complete successfully

**13b. Document Exceeding Timeout**:
- Document that would take >120 seconds
- Should raise TimeoutError
- Should provide helpful diagnostic information

**13c. Page-Level Timeout**:
- Single page that takes >10 seconds
- Should handle page timeout correctly

**Test on Windows**:
- Verify timeout works (currently doesn't due to signal limitations)
- Test thread-based timeout implementation

**Commands**:
```python
# Test timeout with very large/complex document
try:
    converter.convert("very-large-document.pdf")
except TimeoutError as e:
    # Verify error message is helpful
    assert "120s" in str(e)
    assert "diagnostic" in e.__dict__ or "hint" in str(e)
```

---

## Edge Cases: Text Normalization

### Test Case 14: Text Normalization Edge Cases
**Objective**: Verify text normalization handles edge cases correctly

**Test Documents**:

**14a. Hyphenated Words**:
- Document with line breaks at hyphens
- Verify hyphen repair works:
  ```
  "line-\nbreak" → "line-break"
  ```

**14b. Code Blocks**:
- Document with code examples (```code```)
- Verify code blocks are preserved exactly
- Test various code block formats

**14c. Math Formulas**:
- Document with LaTeX math ($$formula$$)
- Verify math is preserved
- Test inline and block math

**14d. Whitespace**:
- Document with excessive whitespace
- Verify normalization:
  - Multiple spaces → single space
  - Multiple newlines → double newline
  - Trailing spaces removed

**14e. Mixed Content**:
- Document with code, math, and normal text
- Verify all are handled correctly

**Verify**:
- Normalization doesn't corrupt content
- Protected blocks (code/math) are preserved
- Whitespace normalization works correctly
- Hyphen repair works

---

## Edge Cases: Structure Extraction

### Test Case 15: Document Structure Extraction
**Objective**: Test structure extraction for various document types

**Test Scenarios**:

**15a. Documents with Clear Structure**:
- Academic papers with sections
- Technical documentation with headings
- Books with chapters

**15b. Documents with Minimal Structure**:
- Plain text documents
- Documents with only paragraphs
- Documents without headings

**15c. Documents with Complex Structure**:
- Multi-column layouts
- Tables and figures
- Footnotes and endnotes
- Appendices

**Verify**:
- Structure is extracted correctly
- Heading hierarchy is preserved
- Page anchors are accurate
- Fallback handling works for unstructured documents

---

## Edge Cases: Image Handling

### Test Case 16: Image-Only Page Detection
**Objective**: Verify image-only pages are detected and handled

**Test Documents**:
- PDF with image-only pages (diagrams, charts)
- PDF with mixed text/image pages
- PDF where all pages are images (scanned document)

**Verify**:
- Image-only pages are detected
- Detection is logged appropriately
- OCR is triggered for image pages
- Pages are not skipped (content is extracted via OCR)

---

## Integration Tests

### Test Case 17: End-to-End Ingestion Workflow
**Objective**: Test complete workflow from file to indexed chunks

**Workflow Steps**:
1. Document conversion (Docling)
2. Chunking (DoclingHybridChunker)
3. Metadata resolution (Zotero)
4. Embedding generation (FastEmbed)
5. Indexing (Qdrant)

**Test Commands**:
```bash
# Complete workflow
uv run citeloom ingest run \
  --project citeloom/test \
  "assets/raw/document.pdf"

# Verify chunks are indexed
uv run citeloom query run \
  --project citeloom/test \
  --query "test query" \
  --top-k 5
```

**Verify**:
- Each step completes successfully
- Chunks are correctly indexed
- Queries return relevant results
- Metadata is attached to chunks
- Citations work correctly

---

### Test Case 18: Batch Processing
**Objective**: Test processing multiple documents in sequence

**Test Setup**:
- Directory with 10-20 PDF documents
- Various sizes and types

**Commands**:
```bash
uv run citeloom ingest run \
  --project citeloom/batch-test \
  "assets/raw/"
```

**Verify**:
- All documents are processed
- Progress is shown for batch
- Converter is reused (not reinitialized per document)
- Errors in one document don't stop batch
- Final summary is accurate

---

### Test Case 19: Resume from Checkpoint
**Objective**: Test checkpoint/resume functionality with Docling

**Test Steps**:
1. Start batch import (many documents)
2. Interrupt mid-process (Ctrl+C)
3. Resume with `--resume` flag
4. Verify:
   - Previously processed documents are skipped
   - Only remaining documents are processed
   - Checkpoint file is correctly read

**Commands**:
```bash
# Start import (interrupt after a few documents)
uv run citeloom ingest run \
  --project citeloom/test \
  --zotero-collection "Large Collection"

# Resume
uv run citeloom ingest run \
  --project citeloom/test \
  --zotero-collection "Large Collection" \
  --resume
```

---

## Platform-Specific Tests

### Test Case 20: Windows Compatibility
**Objective**: Test Docling on Windows (WSL/Docker)

**Test Scenarios**:

**20a. WSL Environment**:
- Run tests in WSL
- Verify converter works
- Verify chunker works (if available)
- Compare performance with Linux

**20b. Docker Environment**:
- Run in Docker container
- Verify all features work
- Test resource limits

**20c. Native Windows (Current Limitations)**:
- Verify converter works (observed: yes)
- Verify chunker fallback works (observed: manual chunking)
- Document limitations clearly

**Verify**:
- Clear error messages for Windows users
- Fallback behavior is documented
- Performance is acceptable
- Features work where available

---

### Test Case 21: Linux/macOS Compatibility
**Objective**: Test on Linux and macOS platforms

**Test Scenarios**:
- Full Docling support should work
- Compare performance with Windows
- Verify timeout enforcement works (signal-based)
- Test all features

---

## Performance Benchmarking

### Test Case 22: Conversion Speed Benchmarks
**Objective**: Establish baseline performance metrics

**Test Documents** (by size):
- Small: <1MB, 5-10 pages
- Medium: 1-5MB, 20-50 pages
- Large: 5-20MB, 50-100 pages
- Very Large: 20+MB, 100+ pages

**Metrics**:
- Time per page
- Time per MB
- Memory usage
- CPU usage

**Expected**:
- Small: <5s per document
- Medium: 10-30s per document
- Large: 30-60s per document
- Very Large: 60-120s per document (may hit timeout)

---

### Test Case 23: Chunking Speed Benchmarks
**Objective**: Measure chunking performance

**Test Setup**:
- Documents of various sizes
- Different chunking policies
- Measure time per chunk created

**Metrics**:
- Chunking time per document
- Time per chunk
- Memory usage during chunking

**Expected**:
- <1s for small documents (10 chunks)
- 1-3s for medium documents (50 chunks)
- 3-10s for large documents (200+ chunks)

---

## Comparison Tests

### Test Case 24: Docling vs Zotero Fulltext
**Objective**: Compare Docling conversion with Zotero fulltext reuse

**Test Setup**:
- Same document available in both:
  - Zotero fulltext (pre-extracted)
  - Docling conversion (on-the-fly)

**Test Scenarios**:

**24a. Speed Comparison**:
- Time for Zotero fulltext reuse
- Time for Docling conversion
- Compare performance

**24b. Quality Comparison**:
- Text quality from Zotero
- Text quality from Docling
- Compare accuracy, formatting

**24c. Feature Comparison**:
- Page map accuracy
- Heading extraction
- Structure preservation

**Expected**:
- Zotero fulltext: 50-80% faster (reuse existing)
- Docling: Better structure extraction, more features
- Both produce usable results

---

### Test Case 25: Manual vs Docling Chunking
**Objective**: Compare manual chunking fallback with Docling HybridChunker

**Test Setup**:
- Same conversion result
- Chunk with:
  - Docling HybridChunker (Linux/macOS)
  - Manual chunking (Windows fallback)

**Compare**:
- Chunk count
- Chunk boundaries
- Heading context inclusion
- Quality filtering results

**Verify**:
- Both produce reasonable chunks
- Manual chunking matches Docling quality as closely as possible
- Differences are documented

---

## Edge Cases: Special Content

### Test Case 26: Documents with Special Characters
**Objective**: Test handling of special characters and Unicode

**Test Documents**:
- Unicode characters (中文, 日本語, العربية)
- Special symbols (©, ®, ™, €, £)
- Mathematical symbols (α, β, ∑, ∫)
- Emoji (if supported)

**Verify**:
- Characters are preserved correctly
- Encoding is handled properly
- No encoding errors in logs
- Text displays correctly in terminal

---

### Test Case 27: Documents with Tables
**Objective**: Test table extraction and preservation

**Test Documents**:
- PDFs with tables
- DOCX with tables
- Verify table structure is preserved or converted appropriately

**Verify**:
- Table content is extracted
- Structure is preserved where possible
- Tables are readable in plain text
- Chunking handles tables correctly

---

### Test Case 28: Documents with Footnotes/Endnotes
**Objective**: Test handling of footnotes and endnotes

**Test Documents**:
- Academic papers with footnotes
- Books with endnotes
- Verify footnotes are extracted and associated correctly

**Verify**:
- Footnotes are extracted
- Association with main text is preserved
- Footnotes are included in chunks appropriately
- Citation references work

---

## Error Recovery Tests

### Test Case 29: Partial Conversion Recovery
**Objective**: Test behavior when conversion fails partway

**Test Scenarios**:

**29a. Conversion Fails Mid-Document**:
- Simulate failure (e.g., corrupt page in middle)
- Verify:
  - Error is reported clearly
  - Partial results are available (if implemented)
  - System state is not corrupted

**29b. Chunking Fails**:
- Conversion succeeds but chunking fails
- Verify:
  - Conversion result is preserved
  - Error is clear
  - Can retry chunking separately

**29c. Embedding Fails**:
- Conversion and chunking succeed, embedding fails
- Verify graceful handling

---

### Test Case 30: Resource Exhaustion Handling
**Objective**: Test behavior when resources are limited

**Test Scenarios**:
- Low memory conditions
- CPU-intensive operations
- Disk space limitations
- Network issues (if models need download)

**Verify**:
- Clear error messages
- No crashes
- Graceful degradation
- Resource cleanup

---

## Automated Test Suite

### Test Case 31: Regression Test Suite
**Objective**: Automated tests for core functionality

**Test Categories**:

**31a. Unit Tests**:
- Converter initialization
- OCR language selection
- Text normalization
- Page map extraction
- Heading tree extraction

**31b. Integration Tests**:
- Full conversion workflow
- Chunking workflow
- End-to-end ingestion

**31c. Smoke Tests**:
- Quick validation of core features
- Fast execution (< 5 minutes)

**Commands**:
```bash
# Run all tests
uv run pytest tests/integration/test_docling*.py -v

# Run smoke tests only
uv run pytest tests/integration/test_docling_smoke.py -v

# Run with coverage
uv run pytest tests/integration/test_docling*.py --cov=src.infrastructure.adapters.docling --cov-report=html
```

---

## Test Execution Priority

### High Priority (Must Test)
- Test Case 1: Conversion Performance (Small)
- Test Case 3: Multi-Page Page Map Accuracy
- Test Case 4: Heading Tree Extraction Accuracy
- Test Case 7: Chunking with Different Policies
- Test Case 17: End-to-End Ingestion Workflow

### Medium Priority (Should Test)
- Test Case 2: Conversion Performance (Large)
- Test Case 5: PDF Document Varieties
- Test Case 8: Chunking Quality Filtering
- Test Case 10: OCR Language Detection
- Test Case 12: Invalid/Corrupted Documents
- Test Case 18: Batch Processing

### Low Priority (Nice to Have)
- Test Case 6: Other Document Formats
- Test Case 11: OCR Performance
- Test Case 13: Timeout Handling
- Test Case 14: Text Normalization Edge Cases
- Test Case 15-16: Structure/Image Handling
- Test Case 19-31: Advanced/Edge Cases

---

## Test Data Requirements

### Sample Documents Needed

1. **Small PDF** (1-2MB, 5-10 pages)
   - Clear headings
   - Mixed content (text, images, tables)
   - ✅ Available: "Sakai - 2025 - AI Agent Architecture..." (1.5MB)

2. **Medium PDF** (5-10MB, 20-50 pages)
   - Academic paper format
   - Multiple sections

3. **Large PDF** (20+MB, 100+ pages)
   - Book or long report
   - Tests timeout behavior

4. **Scanned PDF** (needs OCR)
   - Image-based document
   - Tests OCR functionality

5. **Multi-language PDF**
   - English + other language
   - Tests OCR language detection

6. **DOCX Document**
   - Word document with formatting
   - Tests DOCX conversion

7. **PPTX Presentation**
   - PowerPoint file
   - Tests PPTX conversion

8. **HTML Document**
   - Web page or HTML export
   - Tests HTML conversion

---

## Performance Targets

### Conversion Targets

| Document Size | Pages | Target Time | Acceptable Range |
|---------------|-------|-------------|------------------|
| Small (<2MB) | 5-10 | 20-30s | 15-40s |
| Medium (2-10MB) | 20-50 | 30-60s | 25-90s |
| Large (10-20MB) | 50-100 | 60-120s | 50-150s |
| Very Large (>20MB) | 100+ | 120s+ | May timeout |

### Chunking Targets

| Document Size | Expected Chunks | Target Time | Acceptable Range |
|---------------|----------------|-------------|------------------|
| Small | 5-20 | <1s | <2s |
| Medium | 20-100 | 1-3s | <5s |
| Large | 100-500 | 3-10s | <15s |
| Very Large | 500+ | 10-30s | <60s |

---

## Test Automation Script

### Test Case 32: Automated Test Runner
**Objective**: Create script to run comprehensive tests

**Script Template**:
```python
"""Automated test runner for Docling conversion and chunking."""

import subprocess
import time
import json
from pathlib import Path
from typing import Any

def run_conversion_test(pdf_path: str) -> dict[str, Any]:
    """Run conversion test and return metrics."""
    start = time.time()
    
    try:
        result = subprocess.run(
            ["uv", "run", "citeloom", "ingest", "run",
             "--project", "citeloom/test", pdf_path],
            capture_output=True,
            text=True,
            timeout=180  # 3 minute timeout
        )
        elapsed = time.time() - start
        
        # Parse output for chunks created
        chunks_created = parse_chunk_count(result.stdout)
        
        return {
            "success": result.returncode == 0,
            "time": elapsed,
            "chunks": chunks_created,
            "output": result.stdout,
            "errors": result.stderr if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "time": 180,
            "error": "timeout",
        }

def parse_chunk_count(output: str) -> int:
    """Extract chunk count from output."""
    # Parse "Ingested X chunks from Y document(s)"
    # Implementation depends on actual output format
    pass

# Run test suite
if __name__ == "__main__":
    test_documents = [
        "assets/raw/Sakai - 2025 - AI Agent Architecture Mapping Domain, Agent, and Orchestration to Clean Architecture.pdf",
        # Add more test documents
    ]
    
    results = []
    for doc in test_documents:
        print(f"Testing: {doc}")
        result = run_conversion_test(doc)
        results.append({
            "document": doc,
            **result
        })
        print(f"  Time: {result.get('time', 0):.2f}s, Chunks: {result.get('chunks', 0)}")
    
    # Save results
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
```

---

## Expected Test Outcomes

### Success Criteria

1. **Conversion Success Rate**: >95% for valid documents
2. **Page Map Accuracy**: >90% correct page boundaries
3. **Heading Extraction**: >80% of headings correctly extracted
4. **Chunking Quality**: Reasonable chunk sizes (not too large, not too small)
5. **Performance**: Meets targets for document sizes
6. **Error Handling**: Clear errors for invalid inputs

### Known Limitations

1. **Windows**: DoclingHybridChunker not available (uses manual fallback)
2. **Timeout**: Only works on Unix/Linux (signal-based), not Windows
3. **OCR**: May produce warnings for normal operations
4. **Large Documents**: May hit 120s timeout limit

---

## Comparison Matrix

| Feature | Docling Converter | Docling Chunker | Manual Fallback |
|---------|-------------------|-----------------|-----------------|
| **Availability** | ✅ Works on Windows | ❌ Not on Windows | ✅ Fallback available |
| **Performance** | Fast | Fast (when available) | Slower |
| **Quality** | High | High | Lower (heading awareness) |
| **Platform** | All | Linux/macOS only | All |
| **Features** | Full | Full | Limited |

---

## Summary

This comprehensive testing plan covers:

1. **Performance Testing** (6 test cases)
   - Speed benchmarks
   - Resource usage
   - Scalability

2. **Correctness Testing** (10 test cases)
   - Page map accuracy
   - Heading extraction
   - Chunking quality
   - Structure preservation

3. **Edge Case Testing** (12 test cases)
   - Document formats
   - Special content
   - Error scenarios
   - Platform differences

4. **Integration Testing** (4 test cases)
   - End-to-end workflows
   - Batch processing
   - Error recovery

**Total Test Cases**: 32 comprehensive test cases covering all aspects of Docling integration.

---

## Next Steps

1. **Execute high-priority tests** to validate core functionality
2. **Fix critical issues** identified in use case testing issues document
3. **Run medium-priority tests** to verify edge cases
4. **Establish baseline metrics** for performance targets
5. **Create automated test suite** for regression testing

