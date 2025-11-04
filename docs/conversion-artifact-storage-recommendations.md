# Conversion Artifact Storage & Chunking Quality Recommendations

**Date**: 2025-11-04  
**Status**: Recommendations for Implementation

## Executive Summary

This document provides best practices for storing windowed conversion artifacts and optimizing chunking quality for hybrid/semantic search. The recommendations balance computational efficiency, storage costs, and retrieval quality.

## Key Principles

1. **Store both window cache and merged canonical document** - Enable incremental processing and whole-document operations
2. **Persist chunk sets as versioned artifacts** - Enable re-chunking and re-embedding without re-conversion
3. **Optimize Qdrant for production** - Payload indexes, bulk ingest patterns, hybrid search setup
4. **Maintain provenance and reproducibility** - Track source, policy versions, and embedding models

---

## 1. Artifact Storage Strategy

### 1.1 Dual Storage Approach

**Store both windowed and merged artifacts** for maximum flexibility:

#### Window Cache (Per-Window JSON)
- **Purpose**: Incremental checkpoint, resume capability, per-window chunking
- **Format**: JSON (one file per window)
- **Location**: `var/artifacts/<doc_id>/windows/`
- **Content**: Full `ConversionResult` dict for each window

#### Merged Canonical Document
- **Purpose**: Whole-document context, cross-window chunking, re-chunking with new policies
- **Format**: JSON (single file) or JSONL (line-delimited)
- **Location**: `var/artifacts/<doc_id>/merged/`
- **Content**: Stitched document with unified structure

### 1.2 Recommended Disk Layout

```
var/artifacts/
  <doc_id>/                    # Stable ID (content hash or file path hash)
    original/
      file.pdf                  # Copy of source PDF (optional, for reference)
    windows/
      window_0001.json         # Pages 1-10
      window_0002.json          # Pages 11-20
      ...
      manifest.json             # Window metadata, page ranges, hashes
    merged/
      document.json             # Canonical stitched document
      manifest.json             # Document metadata, policy version, provenance
    chunks/
      v1_h400_o40.jsonl        # Chunk set v1 (max 400 tokens, 40 overlap)
      v2_h600_o20.jsonl        # Chunk set v2 (different policy)
      policy_manifest.json      # Policy versions and metadata
    embeddings/
      v1_h400_o40.jsonl        # Embedding audit log (optional)
      model_manifest.json       # Embedding model IDs per chunk set
```

### 1.3 Artifact Naming Conventions

- **Document ID**: Stable hash (content hash or path hash) - matches `doc_id` from conversion
- **Window files**: `window_<num>.json` (zero-padded, e.g., `window_0001.json`)
- **Chunk sets**: `v<version>_h<max_tokens>_o<overlap>.jsonl` (e.g., `v1_h400_o40.jsonl`)
- **Manifests**: `manifest.json` (describes the artifact set)

---

## 2. Window Cache Implementation

### 2.1 Window Cache Structure

Each window JSON file should contain:

```json
{
  "window_num": 1,
  "start_page": 1,
  "end_page": 10,
  "doc_id": "path_abc123...",
  "conversion_result": {
    "doc_id": "path_abc123...",
    "structure": {
      "heading_tree": {...},
      "page_map": {...}
    },
    "plain_text": "...",
    "document": "<docling_document_dict>"
  },
  "metadata": {
    "source_path": "/path/to/file.pdf",
    "conversion_time": "2025-11-04T20:42:21Z",
    "window_size": 10,
    "content_hash": "sha256:abc123..."
  }
}
```

### 2.2 Window Cache Benefits

1. **Resume capability**: Skip already-converted windows on re-run
2. **Incremental updates**: Re-chunk only changed windows
3. **Memory efficiency**: Process windows independently
4. **Debugging**: Inspect individual windows for quality issues

### 2.3 Implementation Recommendations

**Add to `src/infrastructure/adapters/docling_windowed.py`**:

```python
def save_window_cache(
    window_result: WindowedConversionResult,
    artifacts_dir: Path,
    doc_id: str,
) -> Path:
    """Save window conversion result to cache."""
    window_dir = artifacts_dir / doc_id / "windows"
    window_dir.mkdir(parents=True, exist_ok=True)
    
    window_file = window_dir / f"window_{window_result.window_num:04d}.json"
    
    cache_data = {
        "window_num": window_result.window_num,
        "start_page": window_result.start_page,
        "end_page": window_result.end_page,
        "doc_id": doc_id,
        "conversion_result": window_result.conversion_result,
        "metadata": {
            "source_path": str(source_path),
            "conversion_time": datetime.utcnow().isoformat() + "Z",
            "window_size": window_result.end_page - window_result.start_page + 1,
            "content_hash": _compute_content_hash(window_result.conversion_result),
        }
    }
    
    with open(window_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    return window_file
```

---

## 3. Merged Canonical Document

### 3.1 Merging Strategy

**Key consideration**: Merge windows **after** conversion, **before** chunking for optimal quality.

#### Option A: Merge Structure Only (Recommended)
- Merge `heading_tree` and `page_map` across windows
- Concatenate `plain_text` with proper page boundaries
- Keep `document` structures separate (or merge as needed)

#### Option B: Full Merge
- Merge entire Docling document structures
- More complex but preserves full document context
- Useful for cross-window operations (e.g., table extraction)

### 3.2 Merged Document Structure

```json
{
  "doc_id": "path_abc123...",
  "structure": {
    "heading_tree": {
      // Merged heading tree across all windows
      "Introduction": {
        "level": 1,
        "page": 1,
        "children": {...}
      }
    },
    "page_map": {
      // Unified page map (1-N)
      1: (0, 5000),
      2: (5000, 10000),
      ...
    }
  },
  "plain_text": "Full document text...",
  "windows": [
    {"window_num": 1, "start_page": 1, "end_page": 10},
    {"window_num": 2, "start_page": 11, "end_page": 20},
    ...
  ],
  "metadata": {
    "source_path": "/path/to/file.pdf",
    "total_pages": 1096,
    "window_count": 110,
    "merge_time": "2025-11-04T20:45:00Z",
    "content_hash": "sha256:def456..."
  }
}
```

### 3.3 Implementation Recommendations

**Add to `src/infrastructure/adapters/docling_windowed.py`**:

```python
def merge_windowed_conversions(
    window_results: list[WindowedConversionResult],
    artifacts_dir: Path,
    doc_id: str,
) -> dict[str, Any]:
    """Merge windowed conversion results into canonical document."""
    merged_dir = artifacts_dir / doc_id / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    
    # Merge heading trees
    merged_heading_tree = {}
    merged_page_map = {}
    merged_text_parts = []
    
    current_offset = 0
    for window_result in window_results:
        conversion = window_result.conversion_result
        structure = conversion.get("structure", {})
        
        # Merge heading tree (with page offsets)
        heading_tree = structure.get("heading_tree", {})
        _merge_heading_tree(merged_heading_tree, heading_tree, window_result.start_page)
        
        # Merge page map (with text offsets)
        page_map = structure.get("page_map", {})
        _merge_page_map(merged_page_map, page_map, window_result.start_page, current_offset)
        
        # Merge text
        plain_text = conversion.get("plain_text", "")
        merged_text_parts.append(plain_text)
        current_offset += len(plain_text)
    
    # Create merged document
    merged_document = {
        "doc_id": doc_id,
        "structure": {
            "heading_tree": merged_heading_tree,
            "page_map": merged_page_map,
        },
        "plain_text": "\n\n".join(merged_text_parts),
        "windows": [
            {
                "window_num": w.window_num,
                "start_page": w.start_page,
                "end_page": w.end_page,
            }
            for w in window_results
        ],
        "metadata": {
            "total_pages": window_results[0].total_pages if window_results else 0,
            "window_count": len(window_results),
            "merge_time": datetime.utcnow().isoformat() + "Z",
        }
    }
    
    # Save merged document
    merged_file = merged_dir / "document.json"
    with open(merged_file, 'w', encoding='utf-8') as f:
        json.dump(merged_document, f, indent=2, ensure_ascii=False)
    
    return merged_document
```

---

## 4. Chunk Set Storage

### 4.1 Chunk Set Format (JSONL)

Store chunks as **versioned JSONL files** (one chunk per line):

```jsonl
{"id": "chunk_abc123", "doc_id": "path_abc123...", "text": "...", "page_span": (1, 1), "section_heading": "Introduction", "section_path": ["Introduction"], "chunk_idx": 0, "token_count": 450, "signal_to_noise": 0.85}
{"id": "chunk_def456", "doc_id": "path_abc123...", "text": "...", "page_span": (1, 2), "section_heading": "Introduction", "section_path": ["Introduction"], "chunk_idx": 1, "token_count": 420, "signal_to_noise": 0.82}
...
```

### 4.2 Chunk Set Benefits

1. **Re-embedding**: Change embedding models without re-chunking
2. **Policy comparison**: Test different chunking policies on same document
3. **Debugging**: Inspect chunks for quality issues
4. **Reproducibility**: Track which policy produced which chunks

### 4.3 Policy Manifest

Store chunking policy metadata:

```json
{
  "policy_version": "v1",
  "max_tokens": 400,
  "overlap_tokens": 40,
  "heading_context": 2,
  "tokenizer_id": "sentence-transformers/all-MiniLM-L6-v2",
  "min_chunk_length": 50,
  "min_signal_to_noise": 0.3,
  "chunk_count": 1250,
  "created_at": "2025-11-04T20:45:00Z"
}
```

### 4.4 Implementation Recommendations

**Add to `src/infrastructure/adapters/docling_chunker.py`**:

```python
def save_chunk_set(
    chunks: list[Any],
    artifacts_dir: Path,
    doc_id: str,
    policy: ChunkingPolicy,
    policy_version: str = "v1",
) -> Path:
    """Save chunk set to JSONL file."""
    chunks_dir = artifacts_dir / doc_id / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename from policy
    filename = f"{policy_version}_h{policy.max_tokens}_o{policy.overlap_tokens}.jsonl"
    chunk_file = chunks_dir / filename
    
    # Write chunks as JSONL
    with open(chunk_file, 'w', encoding='utf-8') as f:
        for chunk in chunks:
            chunk_dict = {
                "id": chunk.id,
                "doc_id": chunk.doc_id,
                "text": chunk.text,
                "page_span": chunk.page_span,
                "section_heading": chunk.section_heading,
                "section_path": chunk.section_path,
                "chunk_idx": chunk.chunk_idx,
                "token_count": getattr(chunk, "token_count", None),
                "signal_to_noise": getattr(chunk, "signal_to_noise_ratio", None),
            }
            f.write(json.dumps(chunk_dict, ensure_ascii=False) + "\n")
    
    # Save policy manifest
    manifest_file = chunks_dir / "policy_manifest.json"
    manifest = {
        "policy_version": policy_version,
        "max_tokens": policy.max_tokens,
        "overlap_tokens": policy.overlap_tokens,
        "heading_context": policy.heading_context,
        "tokenizer_id": policy.tokenizer_id,
        "min_chunk_length": policy.min_chunk_length,
        "min_signal_to_noise": policy.min_signal_to_noise,
        "chunk_count": len(chunks),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(manifest_file, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    return chunk_file
```

---

## 5. Chunking Quality for Hybrid Search

### 5.1 Chunking Strategy: Windowed vs. Merged

**Recommendation**: **Chunk across merged document** when possible, but **keep window boundaries for caching**.

#### Option A: Chunk Merged Document (Best Quality)
- **Pros**: No seam artifacts at window boundaries, preserves paragraph context
- **Cons**: Requires merging all windows first (more memory)
- **Use when**: Document fits in memory, quality is critical

#### Option B: Chunk Per-Window (Memory Efficient)
- **Pros**: Lower memory, can process incrementally
- **Cons**: Potential seam artifacts at window boundaries
- **Use when**: Very large documents, memory constraints

#### Option C: Hybrid Approach (Recommended)
- Chunk per-window during initial ingest (for speed)
- Optionally re-chunk merged document later (for quality)
- Store both chunk sets for comparison

### 5.2 Cross-Window Stitching

If chunking per-window, add **cross-window context** at boundaries:

```python
def chunk_with_cross_window_context(
    window_result: WindowedConversionResult,
    previous_window_last_chunks: list[Any],
    context_sentences: int = 3,
) -> list[Any]:
    """Chunk window with context from previous window."""
    # Prepend last N sentences from previous window for context
    if previous_window_last_chunks:
        context_text = _extract_last_sentences(
            previous_window_last_chunks[-1].text,
            context_sentences
        )
        # Use context for boundary detection only (not stored in final chunk)
        # ...
    
    # Chunk window normally
    chunks = chunker.chunk(window_result.conversion_result, policy)
    return chunks
```

### 5.3 Optimal Chunk Size for Hybrid Search

**Recommendations**:
- **Target size**: 400-600 tokens (Docling guidance: limiting chunk length preserves meaning)
- **Overlap**: 0-40 tokens (minimal, only if needed for context)
- **Heading context**: Include 2-3 levels of ancestor headings in chunk payload
- **Page span**: Store accurate page ranges for filtering

**Rationale**:
- Too large chunks: Hurt dense embedding quality, reduce precision
- Too small chunks: Lose context, increase chunk count (storage cost)
- Optimal range: Balances meaning preservation with embedding quality

### 5.4 Chunk Payload Fields for Hybrid Search

Store these fields in Qdrant payload for efficient filtering:

```python
chunk_payload = {
    "doc_id": "...",
    "project_id": "...",
    "citekey": "...",  # From Zotero metadata
    "section_heading": "...",  # Current heading
    "section_path": ["Introduction", "Background"],  # Full path
    "page_span": (1, 2),  # (start_page, end_page)
    "chunk_idx": 0,
    "token_count": 450,
    "signal_to_noise": 0.85,
    "tags": ["ai", "engineering"],  # From Zotero
    "collections": ["Research/ML"],  # From Zotero
    "window_num": 1,  # For debugging
}
```

**Create payload indexes** for these fields in Qdrant (see Section 6.3).

---

## 6. Qdrant Optimization

### 6.1 Payload Indexes

**Create indexes** for fields you filter/sort on:

```python
# In QdrantIndexAdapter._ensure_collection()
payload_indexes = [
    PayloadSchemaType.KEYWORD,  # For project_id, doc_id, citekey
    PayloadSchemaType.KEYWORD,  # For section_path (array)
    PayloadSchemaType.INTEGER,   # For page_span (range queries)
    PayloadSchemaType.FLOAT,     # For signal_to_noise (range queries)
]

# Create indexes
for field_name in ["project_id", "doc_id", "citekey", "section_path", "tags"]:
    collection.create_payload_index(
        field_name=field_name,
        field_schema=PayloadSchemaType.KEYWORD,
    )
```

**Benefits**:
- **Fast filtered search**: Avoid full collection scans
- **Efficient range queries**: Page span, token count filters
- **Production-ready**: Required for large collections

### 6.2 Bulk Ingest Optimization

**Current implementation** (from `batch_import_from_zotero.py`):
- ✅ Disable indexing during bulk upload (`indexing_threshold=0`)
- ✅ Re-enable after ingest (`indexing_threshold=20000`)

**Additional optimizations**:

```python
# Option 1: Disable HNSW during bulk ingest
collection.update_collection(
    hnsw_config=HnswConfigDiff(m=0)  # Disable HNSW
)

# Bulk upload
# ...

# Re-enable HNSW
collection.update_collection(
    hnsw_config=HnswConfigDiff(m=16)  # Standard HNSW
)

# Trigger optimization
collection.update_collection(
    optimizer_config=OptimizersConfigDiff(
        indexing_threshold=20000,
    )
)
```

### 6.3 Hybrid Search Setup

**Current support**: FastEmbed (dense) + payload full-text (sparse)

**Recommended enhancements**:

1. **Explicit sparse vectors**: Add BM25/SPLADE vectors for true hybrid search
2. **Fusion at query time**: Use Qdrant's `Fusion` query mode
3. **Payload full-text index**: Already supported (if `create_fulltext_index=True`)

**Example query**:
```python
from qdrant_client.models import Query, Fusion

# Hybrid search with fusion
results = client.query_points(
    collection_name=collection_name,
    query=Query(
        fusion=Fusion.RRF,  # Reciprocal Rank Fusion
        queries=[
            Query(vector=dense_vector, top=10),  # Dense search
            Query(sparse_vector=sparse_vector, top=10),  # Sparse search
        ]
    ),
    limit=10,
)
```

---

## 7. Provenance & Reproducibility

### 7.1 Provenance Tracking

Store in every artifact:

```json
{
  "provenance": {
    "source_uri": "/path/to/file.pdf",
    "zotero_item_key": "ABC123XYZ",
    "zotero_attachment_key": "DEF456UVW",
    "citekey": "Author2025",
    "doc_hash": "sha256:abc123...",
    "conversion_time": "2025-11-04T20:42:21Z",
    "converter_version": "docling-2.0.0",
    "policy_version": "v1",
    "embedding_model_id": "fastembed/all-MiniLM-L6-v2",
    "window_idx": 1,
    "page_range": (1, 10),
  }
}
```

### 7.2 Reproducibility Features

1. **Content hashing**: Skip unchanged windows (compare `content_hash`)
2. **Policy versioning**: Track chunking policy changes
3. **Model binding**: Store embedding model ID in collection payload
4. **Audit logs**: Track which chunks were indexed (optional)

### 7.3 Implementation Recommendations

**Add to `src/infrastructure/adapters/docling_windowed.py`**:

```python
def should_reconvert_window(
    window_file: Path,
    source_path: str,
    current_hash: str,
) -> bool:
    """Check if window needs re-conversion."""
    if not window_file.exists():
        return True
    
    try:
        with open(window_file, 'r') as f:
            cached = json.load(f)
        cached_hash = cached.get("metadata", {}).get("content_hash")
        return cached_hash != current_hash
    except Exception:
        return True
```

---

## 8. Storage Size Considerations

### 8.1 Compression Options

**For large artifacts**:
- **JSONL + gzip**: Compress chunk sets (e.g., `v1_h400_o40.jsonl.gz`)
- **JSON + zstandard**: Compress merged documents (better compression than gzip)
- **Window cache**: Keep uncompressed JSON (for fast access)

### 8.2 Cleanup Policies

**Recommendations**:
- **Keep window cache**: Until merged document is created
- **Keep merged document**: Indefinitely (source of truth)
- **Keep chunk sets**: Keep latest 2-3 policy versions
- **Keep embeddings**: Only if audit is required

**Implementation**:
```python
def cleanup_old_artifacts(
    artifacts_dir: Path,
    doc_id: str,
    keep_windows: bool = False,
    keep_chunk_versions: int = 3,
) -> None:
    """Clean up old artifacts."""
    doc_dir = artifacts_dir / doc_id
    
    # Remove window cache if merged exists
    if not keep_windows and (doc_dir / "merged" / "document.json").exists():
        shutil.rmtree(doc_dir / "windows")
    
    # Keep only latest N chunk versions
    chunks_dir = doc_dir / "chunks"
    if chunks_dir.exists():
        chunk_files = sorted(chunks_dir.glob("*.jsonl"))
        for old_file in chunk_files[:-keep_chunk_versions]:
            old_file.unlink()
```

---

## 9. Integration with Current Architecture

### 9.1 Modified Workflow

**Current** (from `ingest_document.py`):
1. Convert document (windowed or standard)
2. Chunk immediately
3. Embed chunks
4. Index in Qdrant

**Enhanced** (with artifact storage):
1. Convert document (windowed or standard)
2. **Save window cache** (if windowed)
3. **Merge windows** (if windowed)
4. **Save merged document**
5. Chunk (from merged or per-window)
6. **Save chunk set**
7. Embed chunks
8. **Save embedding manifest**
9. Index in Qdrant

### 9.2 Configuration

**Add to `citeloom.toml`**:

```toml
[artifacts]
# Artifact storage settings
enabled = true
base_dir = "var/artifacts"
save_windows = true          # Save window cache
save_merged = true           # Save merged document
save_chunks = true           # Save chunk sets
save_embeddings = false      # Save embedding audit (optional)
compress = false             # Compress large files (gzip/zstd)
cleanup_windows_after_merge = true
keep_chunk_versions = 3
```

### 9.3 Implementation Priority

**Phase 1** (High Priority):
1. ✅ Window cache saving (already has checkpoint support)
2. ✅ Merged document creation
3. ✅ Chunk set storage (JSONL)

**Phase 2** (Medium Priority):
4. Payload indexes in Qdrant
5. Provenance tracking
6. Content hashing for skip logic

**Phase 3** (Low Priority):
7. Compression
8. Cleanup policies
9. Embedding audit logs

---

## 10. Quality Impact Analysis

### 10.1 Windowed Chunking vs. Merged Chunking

**Windowed chunking** (current):
- ✅ Memory efficient
- ✅ Fast processing
- ⚠️ Potential seam artifacts at boundaries
- ⚠️ May split paragraphs across windows

**Merged chunking** (recommended):
- ✅ No seam artifacts
- ✅ Preserves paragraph context
- ✅ Better heading context
- ⚠️ Requires more memory
- ⚠️ Requires merging step

**Recommendation**: Use **merged chunking** for documents <10,000 pages, **windowed chunking** for larger documents.

### 10.2 Hybrid Search Quality

**With proper chunking**:
- **Dense embeddings**: Capture semantic meaning (400-600 tokens optimal)
- **Sparse vectors**: Capture exact keyword matches (BM25/SPLADE)
- **Fusion**: Combine both signals for best results

**Payload fields**:
- **Section filtering**: Filter by heading/section
- **Page filtering**: Filter by page range
- **Metadata filtering**: Filter by tags, collections, authors

**Quality metrics to track**:
- Chunk signal-to-noise ratio (already implemented)
- Chunk token count distribution
- Retrieval precision/recall (if ground truth available)

---

## 11. Implementation Checklist

### 11.1 Artifact Storage

- [ ] Create `src/infrastructure/adapters/artifact_storage.py`
- [ ] Implement `save_window_cache()`
- [ ] Implement `merge_windowed_conversions()`
- [ ] Implement `save_chunk_set()`
- [ ] Add artifact storage to `ingest_document.py`

### 11.2 Chunking Quality

- [ ] Add option to chunk merged document vs. per-window
- [ ] Implement cross-window context stitching
- [ ] Validate chunk size (400-600 tokens)
- [ ] Ensure heading context in payload

### 11.3 Qdrant Optimization

- [ ] Create payload indexes for filter fields
- [ ] Verify bulk ingest optimization works
- [ ] Test hybrid search queries
- [ ] Document payload schema

### 11.4 Provenance

- [ ] Add provenance tracking to artifacts
- [ ] Implement content hashing
- [ ] Store policy versions
- [ ] Store embedding model IDs

---

## 12. References

- [Docling Retrieval with Qdrant](https://docling-project.github.io/docling/examples/retrieval_qdrant/)
- [Qdrant Vector Search in Production](https://qdrant.tech/articles/vector-search-production/)
- [Qdrant Bulk Upload Optimization](https://qdrant.tech/documentation/database-tutorials/bulk-upload/)
- [Qdrant Hybrid Search with FastEmbed](https://qdrant.tech/documentation/beginner-tutorials/hybrid-search-fastembed/)
- [Docling Chunking Guide](https://docling-project.github.io/docling/concepts/chunking/)

---

## 13. Next Steps

1. **Review recommendations** with team
2. **Prioritize implementation** (Phase 1 → Phase 2 → Phase 3)
3. **Create implementation tickets** for each phase
4. **Test with sample documents** before full rollout
5. **Monitor storage usage** and adjust cleanup policies

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-04

