# Docling Performance Optimization

This guide explains how to optimize Docling conversion performance for CPU-only processing and large documents.

**For CPU-only laptop processing, see [CPU Optimization Guide](./docling-cpu-optimization.md) for maximum efficiency settings.**

## Overview

Docling conversion can be time-consuming for large documents, especially when using CPU-only processing. This guide covers configuration options to:

1. **Increase timeout limits** for large documents
2. **Accelerate processing** with CPU thread configuration
3. **Enable GPU acceleration** (if available)
4. **Monitor progress** during conversion

## Timeout Configuration

### Default Timeouts

- **Document timeout**: 300 seconds (5 minutes) - increased from 120s for CPU-only processing
- **Page timeout**: 10 seconds per page

### Configuration

Adjust timeouts in `citeloom.toml`:

```toml
[docling]
document_timeout_seconds = 300  # 5 minutes (increase for very large documents)
page_timeout_seconds = 10       # 10 seconds per page
```

### When to Increase Timeouts

- **Large documents** (>100 pages): Consider 600-900 seconds (10-15 minutes)
- **Complex documents** (many images, tables, formulas): May need 450-600 seconds
- **CPU-only processing**: Allow more time (5-10 minutes for typical documents)
- **GPU-accelerated**: Can use shorter timeouts (2-3 minutes)

### Example Configurations

```toml
# For large research papers (50-100 pages)
[docling]
document_timeout_seconds = 600  # 10 minutes

# For books or very large documents (100+ pages)
[docling]
document_timeout_seconds = 900  # 15 minutes

# For typical documents (10-50 pages)
[docling]
document_timeout_seconds = 300  # 5 minutes (default)
```

## CPU Acceleration

### Auto-Detection (Recommended)

By default, Docling uses all available CPU cores for parallel processing:

```toml
[docling]
cpu_threads = null  # null = auto-detect (use all cores)
```

This is the **recommended setting** for CPU-only processing as it maximizes parallelization.

### Manual Configuration

If you want to limit CPU usage or have specific requirements:

```toml
[docling]
cpu_threads = 8  # Use 8 threads (adjust based on your CPU)
```

### Performance Impact

- **All cores**: Maximum speed, uses full CPU
- **Fewer cores**: Slower but leaves CPU free for other tasks
- **Single core**: Slowest, but minimal CPU usage

**Recommendation**: Use `cpu_threads = null` (auto-detect) unless you have specific resource constraints.

## GPU Acceleration

### Requirements

- CUDA-capable GPU (NVIDIA)
- CUDA toolkit installed
- Docling with GPU support

### Configuration

```toml
[docling]
enable_gpu = true  # Enable GPU acceleration
```

### Performance Benefits

GPU acceleration can provide **2-5x speedup** for document conversion, especially for:
- Image-heavy documents
- OCR processing
- Large documents with complex layouts

### When to Use GPU

- **Large batch processing**: Converting many documents
- **Image-heavy documents**: Scanned PDFs, presentations
- **Time-sensitive**: Need faster processing
- **Available GPU**: Have CUDA-capable GPU with sufficient VRAM

### CPU-Only Processing

For CPU-only processing (no GPU):

```toml
[docling]
enable_gpu = false  # Use CPU only (default)
cpu_threads = null   # Use all CPU cores
```

This is the **default configuration** and works on all systems.

## Progress Reporting

### Progress Indicators

CiteLoom provides progress updates during conversion:

- **Stage updates**: "Converting document...", "Extracting structure..."
- **Timeout information**: Shows configured timeout limits
- **Time tracking**: Logs elapsed conversion time

### Monitoring Progress

Progress is shown in:
- CLI output (Rich progress bars if available)
- Log files (with timestamps)
- Console output (stage updates)

### Example Output

```
[INFO] Starting document conversion pipeline (timeout: 300s, this may take a moment, especially for large PDFs)...
[INFO] Document conversion pipeline completed in 145.3s, extracting results...
[INFO] Extracted page map with 67 pages
[INFO] Document converted successfully: doc_id=..., pages=67, headings=23
```

## Performance Tips

### 1. Use Zotero Fulltext When Available

Enable Zotero fulltext reuse to skip conversion for documents Zotero has already indexed:

```toml
[zotero]
prefer_zotero_fulltext = true  # Default: true
```

This provides **50-80% speedup** for documents with Zotero fulltext.

### 2. Increase Timeout for Large Documents

For documents >100 pages, increase timeout:

```toml
[docling]
document_timeout_seconds = 600  # 10 minutes
```

### 3. Use All CPU Cores

Ensure CPU thread auto-detection is enabled:

```toml
[docling]
cpu_threads = null  # Use all available cores
```

### 4. Monitor System Resources

- **CPU usage**: Should be high during conversion (all cores utilized)
- **Memory**: Large documents may use significant RAM
- **Disk I/O**: Temporary files may be created during processing

### 5. Process Documents in Batches

For large collections, process documents in smaller batches to:
- Monitor progress more easily
- Avoid resource exhaustion
- Handle failures gracefully

## Troubleshooting

### Timeout Errors

**Symptom**: `Document conversion exceeded 300s timeout`

**Solutions**:
1. Increase timeout for large documents
2. Check if document is corrupted or unusually complex
3. Consider splitting very large documents (>500 pages)

### Slow Processing

**Symptom**: Conversion takes very long even with timeout increase

**Solutions**:
1. Verify CPU thread configuration (should be auto-detected)
2. Check system resources (CPU, memory, disk)
3. Consider GPU acceleration if available
4. Use Zotero fulltext for documents already indexed

### GPU Not Working

**Symptom**: GPU enabled but no speedup

**Solutions**:
1. Verify CUDA installation
2. Check GPU availability: `nvidia-smi`
3. Verify Docling GPU support
4. Check logs for GPU-related errors

### Memory Issues

**Symptom**: Out of memory errors during conversion

**Solutions**:
1. Reduce CPU threads (fewer parallel processes)
2. Process smaller documents first
3. Increase system RAM if possible
4. Close other applications

## Configuration Examples

### Minimal Configuration (CPU-Only, Default)

```toml
[docling]
# Uses defaults: 300s timeout, auto CPU threads, no GPU
```

### Optimized for Large Documents

```toml
[docling]
document_timeout_seconds = 600  # 10 minutes
cpu_threads = null              # All cores
enable_gpu = false              # CPU only
```

### GPU-Accelerated Setup

```toml
[docling]
document_timeout_seconds = 180  # 3 minutes (GPU is faster)
cpu_threads = null              # All cores (for CPU fallback)
enable_gpu = true               # GPU acceleration
```

### Resource-Constrained Setup

```toml
[docling]
document_timeout_seconds = 450  # 7.5 minutes
cpu_threads = 4                 # Limit to 4 cores
enable_gpu = false              # CPU only
```

## Related Documentation

- [Zotero Fulltext Reuse](./zotero-fulltext-reuse.md) - Skip conversion for indexed documents
- [Docling Integration](./docling-integration.md) - Docling setup and configuration
- [Performance Tuning](./performance-tuning.md) - General performance optimization

