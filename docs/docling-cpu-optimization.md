# Docling CPU-Only Optimization Guide

This guide explains how to optimize Docling conversion for CPU-only processing on laptops, based on best practices from the [pdf_data_pipeline repository](https://github.com/Sims2k/pdf_data_pipeline) and Docling documentation.

## Overview

For CPU-only processing, we optimize for:
1. **Speed**: Using FAST table extraction mode and disabling expensive features
2. **Security**: Disabling remote services to prevent external API calls
3. **Reliability**: Increasing timeouts to handle large documents
4. **Efficiency**: Using all available CPU cores and local model caching

## Configuration

### Optimized Settings for CPU-Only

Your `citeloom.toml` should include these CPU-optimized settings:

```toml
[docling]
# Timeout limits (increased for CPU-only processing)
document_timeout_seconds = 600  # 10 minutes (increased for large documents)
page_timeout_seconds = 15       # Increased per-page timeout

# CPU acceleration
cpu_threads = null              # Auto-detect (uses all cores)
enable_gpu = false              # CPU-only mode

# CPU optimization settings
use_fast_table_mode = true      # FAST mode for table extraction (faster on CPU)
enable_remote_services = false  # Disable remote services (security + speed)

# Feature toggles (disable expensive features for faster processing)
do_table_structure = true       # Keep enabled (essential for document structure)
do_ocr = true                   # Keep enabled (auto-detected if needed)
do_code_enrichment = false      # Disable (faster)
do_formula_enrichment = false   # Disable (faster)
do_picture_classification = false # Disable (faster)
do_picture_description = false  # Disable (faster)
generate_page_images = false     # Disable (faster)
```

## Key Optimizations

### 1. FAST Table Mode

**Setting**: `use_fast_table_mode = true`

**Benefit**: Uses `TableFormerMode.FAST` instead of `ACCURATE`, providing significant speedup on CPU while maintaining reasonable table extraction quality.

**Trade-off**: Slightly less accurate table extraction, but much faster processing.

**Reference**: Based on [pdf_data_pipeline implementation](https://github.com/Sims2k/pdf_data_pipeline/blob/main/pdf_extraction.py).

### 2. Disable Remote Services

**Setting**: `enable_remote_services = false`

**Benefits**:
- **Security**: Prevents external API calls
- **Speed**: No network latency
- **Reliability**: Works offline

**Reference**: Recommended in [pdf_data_pipeline](https://github.com/Sims2k/pdf_data_pipeline/blob/main/pdf_extraction.py) for security.

### 3. Feature Toggles

**Disabled Features** (for faster processing):
- `do_code_enrichment = false` - Code snippet enrichment
- `do_formula_enrichment = false` - Mathematical formula enrichment
- `do_picture_classification = false` - Image classification
- `do_picture_description = false` - Image caption generation
- `generate_page_images = false` - Page image generation

**Enabled Features** (essential):
- `do_table_structure = true` - Table extraction (essential for document structure)
- `do_ocr = true` - OCR for scanned documents (auto-detected if needed)

**Reference**: Based on [pdf_data_pipeline configuration](https://github.com/Sims2k/pdf_data_pipeline/blob/main/pdf_extraction.py) which only enables essential features.

### 4. Increased Timeouts

**Settings**:
- `document_timeout_seconds = 600` (10 minutes)
- `page_timeout_seconds = 15` (15 seconds per page)

**Rationale**: CPU-only processing takes longer, especially for large documents. Increased timeouts prevent premature failures.

### 5. CPU Thread Configuration

**Setting**: `cpu_threads = null` (auto-detect)

**Benefit**: Automatically uses all available CPU cores for parallel processing, maximizing throughput.

**Note**: Docling's internal parallelization benefits from all cores being available.

## Performance Comparison

### Before Optimization (Default Settings)
- Table extraction: ACCURATE mode (slower)
- Timeout: 300 seconds (may timeout on large docs)
- Features: All enabled (slower processing)
- Remote services: Enabled (security risk + network latency)

### After Optimization (CPU-Only Settings)
- Table extraction: FAST mode (~2-3x faster)
- Timeout: 600 seconds (handles large documents)
- Features: Only essential enabled (~30-50% faster)
- Remote services: Disabled (secure + faster)

## Model Caching

### Default Cache Location

Docling caches models in `~/.cache/docling/models` by default. This provides:
- **Faster startup**: Models are cached locally
- **Offline operation**: No need to download models repeatedly
- **Consistency**: Same models used across runs

### Custom Cache Path

You can specify a custom cache path:

```toml
[docling]
artifacts_path = "/path/to/custom/models"  # Custom model cache location
```

**Note**: Leave as `null` to use default location unless you have specific requirements.

## Security Considerations

### Remote Services Disabled

With `enable_remote_services = false`:
- ✅ No external API calls
- ✅ Works offline
- ✅ No data sent to third-party services
- ✅ Faster processing (no network latency)

### Recommended Security Settings

```toml
[docling]
enable_remote_services = false  # Always disable for security
```

## Troubleshooting

### Still Hitting Timeouts

If you still encounter timeouts:

1. **Increase document timeout**:
   ```toml
   document_timeout_seconds = 900  # 15 minutes
   ```

2. **Check document size**: Very large documents (>500 pages) may need even longer timeouts

3. **Monitor CPU usage**: Ensure all cores are being utilized (should see 100% CPU usage)

### Slow Processing

If processing is still slow:

1. **Verify CPU thread configuration**:
   ```toml
   cpu_threads = null  # Should use all cores
   ```

2. **Check if FAST mode is enabled**:
   ```toml
   use_fast_table_mode = true
   ```

3. **Verify expensive features are disabled**:
   - `do_code_enrichment = false`
   - `do_formula_enrichment = false`
   - `do_picture_classification = false`
   - etc.

### Memory Issues

If you encounter memory errors:

1. **Reduce CPU threads** (if auto-detected uses too many):
   ```toml
   cpu_threads = 4  # Use fewer cores
   ```

2. **Process smaller documents first**: Test with smaller PDFs before processing large ones

3. **Close other applications**: Free up memory for Docling

## Example Configuration

### Maximum Speed Configuration (CPU-Only)

```toml
[docling]
# Timeouts
document_timeout_seconds = 600
page_timeout_seconds = 15

# CPU optimization
cpu_threads = null              # Use all cores
enable_gpu = false
use_fast_table_mode = true      # FAST mode
enable_remote_services = false  # Disable for security

# Essential features only
do_table_structure = true
do_ocr = true
do_code_enrichment = false
do_formula_enrichment = false
do_picture_classification = false
do_picture_description = false
generate_page_images = false
```

### Balanced Configuration (CPU-Only)

If you need more features but still want good performance:

```toml
[docling]
document_timeout_seconds = 600
page_timeout_seconds = 15
cpu_threads = null
enable_gpu = false
use_fast_table_mode = true
enable_remote_services = false

# Keep more features enabled
do_table_structure = true
do_ocr = true
do_code_enrichment = true        # Enable if you have code-heavy documents
do_formula_enrichment = true     # Enable if you have math-heavy documents
do_picture_classification = false
do_picture_description = false
generate_page_images = false
```

## References

- [pdf_data_pipeline repository](https://github.com/Sims2k/pdf_data_pipeline) - Example implementation
- [pdf_extraction.py](https://github.com/Sims2k/pdf_data_pipeline/blob/main/pdf_extraction.py) - Configuration example
- [Docling Performance Optimization](./docling-performance-optimization.md) - General performance guide
- [Docling Documentation](https://github.com/DS4SD/docling) - Official Docling docs

## Related Documentation

- [Docling Performance Optimization](./docling-performance-optimization.md) - General performance tuning
- [Zotero Fulltext Reuse](./zotero-fulltext-reuse.md) - Skip conversion for indexed documents

