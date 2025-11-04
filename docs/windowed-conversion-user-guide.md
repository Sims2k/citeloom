# Windowed Conversion User Guide

## Overview

Windowed conversion allows processing very large documents (>1000 pages) in smaller page windows to avoid timeouts and provide better progress visibility. You can also force windowed conversion for any document size, which is useful for medium documents (300-500 pages) that are slow to convert.

## Configuration

### Basic Configuration

```toml
[docling]
# Windowed conversion settings
enable_windowed_conversion = true   # Enable automatic detection for documents >1000 pages
force_windowed_conversion = false   # Force windowed conversion for ALL documents (manual override)
window_size = 10                     # Pages per window (10-30 recommended)
checkpoint_enabled = true             # Enable checkpoint/resume support
```

### Configuration Options

- **`enable_windowed_conversion`**: Enable automatic windowed conversion for documents >1000 pages (default: `true`)
- **`force_windowed_conversion`**: Force windowed conversion for ALL documents regardless of page count (default: `false`)
- **`window_size`**: Number of pages per window (default: `10`, recommended: `10-30`)
- **`checkpoint_enabled`**: Enable checkpoint/resume support (default: `true`)

## Use Cases

### Use Case 1: Automatic Detection (Default)

**Configuration**:
```toml
[docling]
enable_windowed_conversion = true
force_windowed_conversion = false
```

**Behavior**:
- Documents <1000 pages: Standard conversion
- Documents >=1000 pages: Automatic windowed conversion

**Use When**: You want automatic optimization for very large documents only.

### Use Case 2: Force for Medium Documents

**Configuration**:
```toml
[docling]
enable_windowed_conversion = true
force_windowed_conversion = true    # Force windowed for all documents
window_size = 15                     # Larger windows for medium docs
```

**Behavior**:
- ALL documents use windowed conversion
- Useful for medium documents (300-500 pages) that are slow to convert
- Better progress visibility (window-by-window progress)

**Use When**: 
- You have documents with 300-500 pages that take >60s to convert
- You want consistent windowed conversion workflow for all documents
- Example: 340-page document that benefits from windowed conversion

### Use Case 3: Large Windows for Speed

**Configuration**:
```toml
[docling]
enable_windowed_conversion = true
force_windowed_conversion = false
window_size = 25                     # Larger windows for faster processing
```

**Behavior**:
- Automatic detection for large documents
- Larger windows (25 pages) for faster processing
- Requires more memory but processes faster

**Use When**: 
- You have sufficient memory
- You want faster processing for large documents
- You can tolerate larger memory usage

## How It Works

### Standard Conversion Flow

```
Document
  ↓
Convert entire document
  ↓
Chunk document
  ↓
Embed chunks
  ↓
Index in Qdrant
```

### Windowed Conversion Flow

```
Document (>1000 pages or forced)
  ↓
Detect page count
  ↓
Split into windows (10 pages each)
  ↓
For each window:
  ├─ Convert window (pages 1-10)
  ├─ Chunk window immediately
  ├─ Aggregate chunks
  └─ Report progress
  ↓
All windows complete
  ↓
Embed all chunks (FastEmbed, batched)
  ↓
Index in Qdrant (with bulk optimization)
```

### Qdrant Bulk Indexing Optimization

During batch imports:
1. **Start**: Disable indexing (`indexing_threshold=0`)
2. **Process**: Upload all chunks (fast, no indexing overhead)
3. **Complete**: Re-enable indexing (`indexing_threshold=20000`)
4. **Result**: Qdrant builds index in single pass (much faster)

## Examples

### Example 1: Small Document (5 pages)

**Configuration**: Default (auto-detect)

**Result**: Standard conversion (14.1s)

**Why**: Document is too small to benefit from windowed conversion.

### Example 2: Medium Document (340 pages)

**Configuration**: `force_windowed_conversion = true`

**Result**: Windowed conversion with ~34 windows (10 pages each)

**Benefits**:
- Better progress visibility
- Avoids timeout issues
- Coherent processing workflow

### Example 3: Large Document (1096 pages)

**Configuration**: Default (auto-detect)

**Result**: Automatic windowed conversion with ~110 windows

**Benefits**:
- Avoids 600s timeout
- Processes in manageable chunks
- Clear progress reporting

## Performance

### Windowed Conversion Performance

**Test Results** (from actual testing):
- **Time per window**: ~20.5s per 10-page window
- **Estimated full document** (475 pages): ~16 minutes
- **Standard conversion** (same document): Would timeout at 600s

**Performance Comparison**:
- Standard conversion: Single 600s timeout attempt
- Windowed conversion: Multiple smaller windows (20-30s each)
- **Result**: Windowed conversion avoids timeouts and provides progress visibility

### Qdrant Bulk Indexing Performance

**Optimization Benefits**:
- **Without optimization**: Indexing happens during upload (slower)
- **With optimization**: Indexing disabled during upload, enabled after (much faster)
- **Result**: Faster bulk uploads, especially for large batches

## Troubleshooting

### Issue: Windowed conversion not working for medium documents

**Solution**: Set `force_windowed_conversion = true` in `citeloom.toml`

### Issue: Windowed conversion too slow

**Solution**: Increase `window_size` to 20-30 pages (requires more memory)

### Issue: Windowed conversion using too much memory

**Solution**: Decrease `window_size` to 5-10 pages

### Issue: Qdrant indexing errors during bulk upload

**Solution**: This is handled automatically - indexing is disabled during bulk upload and re-enabled after

## Best Practices

1. **For Medium Documents (300-500 pages)**: Use `force_windowed_conversion = true` for better progress visibility
2. **For Large Documents (>1000 pages)**: Use default auto-detect (windowed conversion automatic)
3. **Window Size**: Start with 10 pages, adjust based on memory and performance
4. **Bulk Imports**: Qdrant optimization is automatic - no configuration needed

## References

- [Windowed Conversion Test Report](../docs/analysis/windowed-conversion-test-report.md)
- [Windowed Conversion Final Report](../docs/analysis/windowed-conversion-final-report.md)
- [Windowed Conversion Implementation Summary](../docs/analysis/docling-windowed-implementation-summary.md)

