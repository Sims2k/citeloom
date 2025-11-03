# Windows Compatibility Guide

This document explains Windows-specific limitations and workarounds for CiteLoom's document processing features (T066a).

## Overview

CiteLoom supports Windows, but some features have platform-specific limitations due to dependency availability. This guide explains what works, what doesn't, and how to work around limitations.

## Document Conversion (Docling)

### ✅ Works on Windows

- **Docling DocumentConverter**: Full document conversion works on Windows
- **Supported formats**: PDF, DOCX, PPTX, HTML, images
- **OCR support**: Tesseract/RapidOCR OCR works on Windows
- **Page map extraction**: Works on Windows
- **Heading tree extraction**: Works on Windows
- **Timeout enforcement**: Cross-platform timeout works on Windows (ThreadPoolExecutor-based)

### ⚠️ Limitations

- **Initial model download**: First-time conversion may download models (~500MB-1GB), which can take time
- **Performance**: May be slightly slower than Linux/macOS due to Windows I/O characteristics

### Workarounds

- Use WSL (Windows Subsystem for Linux) for native Linux performance if needed
- Use Docker for containerized execution
- Ensure sufficient disk space for model cache (~1GB)

## Document Chunking

### ❌ Docling HybridChunker Not Available on Windows

**What doesn't work:**
- `DoclingHybridChunker` is not available on Windows due to missing `deepsearch-glm` dependency
- Windows lacks Python 3.12 wheels for `deepsearch-glm`, which is required by Docling's HybridChunker

**Impact:**
- Falls back to manual chunking algorithm
- Manual chunking may have different quality characteristics:
  - May produce fewer chunks than HybridChunker for large documents
  - Heading awareness may be less sophisticated
  - Chunk boundaries may differ from Linux/macOS results

**What works:**
- Manual chunking fallback is fully functional
- Produces reasonable chunks for most documents
- Supports heading-aware chunking (simplified algorithm)
- Quality filtering still applies
- Token-based chunking with overlap works correctly

### ✅ Manual Chunking Fallback

**What works:**
- Sentence-based chunking
- Heading-aware chunking (simplified)
- Token count estimation
- Overlap between chunks
- Quality filtering (minimum length, signal-to-noise ratio)

**What may differ:**
- Chunk boundaries may not exactly match HybridChunker output
- Heading context inclusion may be less sophisticated
- Performance may be slightly slower for very large documents

### Workarounds

1. **Use WSL (Recommended)**: Run CiteLoom in WSL2 for full Docling HybridChunker support
   ```bash
   # In WSL terminal
   cd /mnt/c/Dev/Python-Projects/citeloom
   uv run citeloom ingest run --project my-project
   ```

2. **Use Docker**: Run CiteLoom in a Docker container with Linux
   ```bash
   docker run -v C:\Dev\Python-Projects\citeloom:/workspace python:3.12-slim
   ```

3. **Accept manual chunking**: Manual chunking works well for most use cases
   - Test with your documents to verify chunk quality
   - Manual chunking is sufficient for many academic/research documents
   - If chunk quality is acceptable, no action needed

## Platform Comparison

| Feature | Windows | Linux/macOS | Notes |
|---------|---------|-------------|-------|
| Document Conversion | ✅ Full | ✅ Full | Works identically |
| OCR Support | ✅ Full | ✅ Full | Tesseract/RapidOCR |
| Page Map Extraction | ✅ Full | ✅ Full | Same algorithms |
| Heading Extraction | ✅ Full | ✅ Full | Same algorithms |
| Timeout Enforcement | ✅ Full | ✅ Full | ThreadPoolExecutor (cross-platform) |
| HybridChunker | ❌ Manual fallback | ✅ Full | deepsearch-glm dependency |
| Manual Chunking | ✅ Full | ✅ Full | Available on all platforms |

## Testing on Windows

### Verify Conversion Works

```bash
# Test document conversion
uv run citeloom ingest run --project test/project ./test-document.pdf

# Check logs for:
# - "Document conversion pipeline completed"
# - "Extracted page map with N pages"
# - No timeout errors
```

### Verify Chunking Works

```bash
# After ingestion, check chunk count
uv run citeloom inspect collection --project test/project

# Expected:
# - Multiple chunks for multi-page documents
# - Reasonable chunk sizes (not all in one chunk)
# - Warning: "Docling is not available. Chunker will use placeholder implementation." (normal on Windows)
```

### Check for Issues

**If you see:**
- Only 1 chunk for multi-page documents → Manual chunking may need adjustment
- Timeout errors → Document may be too large, consider splitting
- "Docling not available" errors → Check Python version (must be 3.12)

**If chunk quality is poor:**
- Try using WSL for HybridChunker
- Check if manual chunking parameters need adjustment
- Verify document structure is well-formed

## Recommendations

### For Windows Users

1. **Accept manual chunking** if quality is acceptable (recommended for most users)
2. **Use WSL** if you need exact HybridChunker behavior
3. **Test your documents** to verify chunk quality meets your needs
4. **Report issues** if manual chunking produces unacceptable results

### For Development

1. **Test on both platforms** to verify cross-platform compatibility
2. **Document platform differences** in test results
3. **Consider manual chunking improvements** to match HybridChunker quality more closely

## Future Improvements

- **Manual chunking enhancement**: Ongoing improvements to match HybridChunker quality
- **Windows wheels**: If deepsearch-glm adds Windows support, HybridChunker will work automatically
- **Alternative chunkers**: Consider alternative chunking libraries that work on Windows

## Troubleshooting

### "Docling is not available" Warning

**This is normal on Windows** if you see this warning for chunking. It means:
- ✅ Document conversion works (DoclingConverter is available)
- ⚠️ Chunking uses manual fallback (HybridChunker not available)
- ✅ System continues to work with manual chunking

### "Chunker will use placeholder implementation"

This means manual chunking is active. Check:
- Chunk count is reasonable (not just 1 chunk for large documents)
- Chunk quality meets your needs
- If quality is poor, consider WSL or report the issue

### Performance Issues

If conversion is slow:
- First-time model download (normal, one-time)
- Large documents take longer (normal)
- Consider increasing timeout if needed
- Check system resources (CPU, memory, disk)

## Summary

**Windows is fully supported** for document conversion and processing. The main limitation is that Docling's HybridChunker is not available, but the manual chunking fallback works well for most use cases. If you need exact HybridChunker behavior, use WSL or Docker.

