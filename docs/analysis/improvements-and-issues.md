# Improvements and Issues Tracking

**Last Updated**: 2025-11-04  
**Status**: Ready for Implementation

## Overview

This document consolidates all identified improvements and issues from testing and analysis. Items are prioritized by impact and implementation effort.

---

## 🔴 High Priority

### 1. Artifact Storage System

**Status**: ⏳ Not Implemented  
**Priority**: High  
**Impact**: Reusability, performance, debugging

**Requirements**:
- Store window cache (per-window JSON files)
- Store merged canonical document
- Store chunk sets as versioned JSONL
- Content hashing for skip logic
- Provenance tracking

**Details**: See [`../conversion-artifact-storage-recommendations.md`](../conversion-artifact-storage-recommendations.md)

**Implementation Effort**: Medium (3-5 days)

---

### 2. Chunking Quality: Token Sequence Length Warning

**Status**: ⚠️ Warning (Non-blocking)  
**Priority**: High  
**Impact**: Embedding quality, retrieval accuracy

**Issue**:
```
Token indices sequence length is longer than the specified maximum sequence length 
for this model (425 > 256). Running this sequence through the model will result 
in indexing errors
```

**Current Behavior**: Chunks are created but may exceed embedding model's max sequence length (256 tokens)

**Recommendation**:
- Adjust `max_tokens` in `ChunkingPolicy` to align with embedding model (256 tokens)
- OR use a different embedding model with longer context window (e.g., 512 tokens)
- Verify chunk token counts don't exceed model limits

**Implementation Effort**: Low (1-2 hours)

**Files Affected**:
- `src/domain/policy/chunking_policy.py`
- `citeloom.toml` (chunking settings)

---

### 3. Qdrant Payload Indexes

**Status**: ⏳ Not Implemented  
**Priority**: High  
**Impact**: Query performance, production readiness

**Requirements**:
- Create payload indexes for filter fields:
  - `project_id`
  - `doc_id`
  - `citekey`
  - `section_path`
  - `page_span`
  - `tags`
  - `collections`

**Benefits**:
- Fast filtered search (avoid full collection scans)
- Efficient range queries (page span, token count)
- Production-ready performance

**Implementation Effort**: Low (2-3 hours)

**Files Affected**:
- `src/infrastructure/adapters/qdrant_index.py`

---

## 🟡 Medium Priority

### 4. Merged Document Chunking

**Status**: ⏳ Partially Implemented (chunks per-window)  
**Priority**: Medium  
**Impact**: Chunk quality, seam artifacts

**Current Behavior**: Chunks created per-window (potential seam artifacts at boundaries)

**Recommendation**:
- Option A: Chunk merged document when possible (best quality, more memory)
- Option B: Keep per-window chunking with cross-window context stitching
- Option C: Hybrid approach (per-window for speed, re-chunk merged for quality)

**Implementation Effort**: Medium (2-3 days)

**Files Affected**:
- `src/application/use_cases/ingest_document.py`
- `src/infrastructure/adapters/docling_windowed.py` (add merge function)

---

### 5. Full Document Windowed Conversion Testing

**Status**: ⏳ Not Tested (limited to first 5 windows)  
**Priority**: Medium  
**Impact**: Confidence in full document processing

**Current Status**: Tested with first 5 windows (50 pages of 1096-page document)

**Recommendation**:
- Test full document windowed conversion (all 110 windows)
- Verify chunk aggregation correctness
- Measure total processing time
- Monitor memory usage

**Implementation Effort**: Low (1-2 hours testing)

**Files Affected**: None (test script only)

---

### 6. Checkpoint/Resume for Windowed Conversion

**Status**: ⏳ Partially Implemented (checkpoint path parameter exists)  
**Priority**: Medium  
**Impact**: Resume capability, fault tolerance

**Current Behavior**: Checkpoint path parameter exists but not fully integrated

**Recommendation**:
- Implement checkpoint saving after each window
- Implement resume from checkpoint on failure/interruption
- Store checkpoint metadata (last processed page, window count)

**Implementation Effort**: Medium (1-2 days)

**Files Affected**:
- `src/infrastructure/adapters/docling_windowed.py`
- `src/application/use_cases/ingest_document.py`

---

### 7. Hybrid Search Enhancement

**Status**: ⏳ Basic Implementation (FastEmbed + payload full-text)  
**Priority**: Medium  
**Impact**: Search quality, retrieval accuracy

**Current Behavior**: FastEmbed (dense) + payload full-text (sparse-like)

**Recommendation**:
- Add explicit sparse vectors (BM25/SPLADE)
- Use Qdrant's `Fusion` query mode for true hybrid search
- Test hybrid search quality vs. dense-only

**Implementation Effort**: Medium (2-3 days)

**Files Affected**:
- `src/infrastructure/adapters/qdrant_index.py`
- `src/infrastructure/adapters/fastembed_embeddings.py` (if adding sparse vectors)

---

## 🟢 Low Priority

### 8. Performance Optimization: Optimal Window Size

**Status**: ⏳ Not Tested  
**Priority**: Low  
**Impact**: Processing speed, memory usage

**Current Behavior**: Fixed window size (10 pages)

**Recommendation**:
- Test different window sizes (10, 15, 20, 25, 30 pages)
- Find optimal window size for CPU-only systems
- Make window size configurable per document type

**Implementation Effort**: Low (1 day testing)

**Files Affected**:
- `citeloom.toml` (already configurable)

---

### 9. Compression for Large Artifacts

**Status**: ⏳ Not Implemented  
**Priority**: Low  
**Impact**: Storage efficiency

**Recommendation**:
- Compress chunk sets (JSONL + gzip)
- Compress merged documents (JSON + zstandard)
- Keep window cache uncompressed (for fast access)

**Implementation Effort**: Low (1 day)

**Files Affected**:
- Artifact storage implementation (when implemented)

---

### 10. Cleanup Policies

**Status**: ⏳ Not Implemented  
**Priority**: Low  
**Impact**: Storage management

**Recommendation**:
- Clean up window cache after merge
- Keep latest 2-3 chunk policy versions
- Optional: Cleanup old embeddings audit logs

**Implementation Effort**: Low (1 day)

**Files Affected**:
- Artifact storage implementation (when implemented)

---

## 📋 Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
1. ✅ Fix token sequence length warning (align chunk size with embedding model)
2. ✅ Create Qdrant payload indexes
3. ✅ Test full document windowed conversion

### Phase 2: Core Features (Week 2-3)
4. ✅ Implement artifact storage system (window cache, merged document, chunk sets)
5. ✅ Implement merged document chunking (or cross-window stitching)
6. ✅ Implement checkpoint/resume for windowed conversion

### Phase 3: Enhancements (Week 4+)
7. ✅ Hybrid search enhancement (sparse vectors, fusion)
8. ✅ Performance optimization (optimal window size)
9. ✅ Compression and cleanup policies

---

## 📝 Notes

### Completed ✅
- Windowed conversion implementation
- Force windowed conversion (manual override)
- Qdrant bulk indexing optimization
- Windowed conversion verification (1096-page document, 5 windows tested)

### Known Limitations
- Chunking per-window (potential seam artifacts)
- Token sequence length warnings (chunks exceed embedding model limits)
- No artifact storage (conversions not cached)
- No checkpoint/resume (must restart on failure)

### Future Considerations
- Subprocess isolation for conversion per window (memory management)
- Skip unchanged windows by hashing text
- OCR backend selection (Tesseract, EasyOCR, RapidOCR, OnnxTR)
- Cross-document analytics (merged canonical documents)

---

## References

- [Conversion Artifact Storage Recommendations](../conversion-artifact-storage-recommendations.md)
- [Windowed Conversion Test Verification](./windowed-conversion-test-verification.md)
- [Windowed Conversion User Guide](../windowed-conversion-user-guide.md)

