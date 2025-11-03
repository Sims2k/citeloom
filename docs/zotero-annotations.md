# Zotero Annotation Indexing

This guide explains how CiteLoom indexes PDF annotations (highlights, comments, notes) from your Zotero library as separate searchable vector points.

## Overview

CiteLoom can extract and index PDF annotations from Zotero, creating separate vector points for each annotation. This enables focused queries like "show me only annotations" or "find annotations about machine learning", dramatically improving retrieval quality.

**Annotations contain high-signal content** - researchers highlight and comment on the most important passages, making annotation indexing a powerful feature for finding key insights.

## Enabling Annotation Indexing

Annotation indexing is **opt-in** (disabled by default) to avoid storage bloat until explicitly enabled.

### Configuration

Enable annotation indexing in `citeloom.toml`:

```toml
[zotero]
include_annotations = true
```

Or via environment variable:
```bash
export ZOTERO_INCLUDE_ANNOTATIONS=true
```

### CLI Option

Enable for a single import:

```bash
citeloom ingest run --project my-project --zotero-collection "Research" --include-annotations
```

## How Annotation Indexing Works

1. **Fetch annotations**: CiteLoom fetches annotation items via Zotero Web API (`itemType=annotation`, filtered by parent attachment)
2. **Normalize data**: Convert Zotero annotation format to CiteLoom format:
   - `pageIndex` (0-indexed) → `page` (1-indexed)
   - Extract `text` as `quote` (highlighted text)
   - Extract `comment` (user annotation)
   - Extract `color` (highlight color)
   - Extract `tags[]` (annotation tags)
3. **Create annotation points**: Each annotation becomes a separate vector point with:
   - `type: "annotation"` tag for filtering
   - `zotero.item_key` and `zotero.attachment_key` for traceability
   - Annotation metadata (`page`, `quote`, `comment`, `color`, `tags`)
4. **Index separately**: Annotation points are indexed in the same collection but as separate points (not merged with document chunks)

## Annotation Payload Structure

Each annotation is indexed with the following payload:

```python
{
    "type": "annotation",
    "project_id": "my-project",
    "doc_id": "document-123",
    "chunk_text": "Highlighted quote\n\nUser comment",
    
    # Zotero traceability
    "zotero": {
        "item_key": "ABC123",
        "attachment_key": "XYZ789",
        "annotation": {
            "page": 5,                    # 1-indexed page number
            "quote": "Highlighted text",
            "comment": "This is important!",
            "color": "#FF0000",           # Hex color code
            "tags": ["important", "ml"]   # Annotation tags
        }
    },
    
    # Citation metadata
    "citekey": "author2024",
    "page_start": 5,
    "page_end": 5,
    "title": "Document Title",
    "authors": ["Author Name"],
    "year": 2024,
    
    # Embedding model
    "embed_model": "fastembed/all-MiniLM-L6-v2"
}
```

## Querying Annotations

After indexing, you can query annotations specifically:

### Via CLI
```bash
# Query with annotation filter (hypothetical - depends on query implementation)
citeloom query run --project my-project --query "machine learning" --filter "type:annotation"
```

### Via MCP
Annotation points appear in query results and can be filtered by `type:annotation` tag.

## Rate Limiting and Error Handling

Annotation extraction uses **exponential backoff retry logic**:
- **3 retries** with increasing delays (base 1s, max 30s)
- **Jitter** added to prevent thundering herd
- **Graceful skipping**: If annotation extraction fails after all retries, CiteLoom:
  - Logs a warning indicating which attachments had failures
  - Continues importing remaining documents
  - Does not fail the entire import

This ensures annotation indexing doesn't block imports even when Web API rate limits are encountered.

## Storage Considerations

Annotation indexing increases storage requirements:
- **Separate vector points**: Each annotation creates a new point in the vector index
- **Average annotations**: Expect ~5 annotations per document on average
- **Collection size**: 100 documents × 5 annotations = 500 additional points

For large collections (1000+ documents), annotation indexing can significantly increase storage usage. Consider enabling only for specific collections or projects.

## Best Practices

1. **Enable selectively**: Enable annotation indexing for collections with valuable annotations
2. **Monitor storage**: Track storage growth when enabling annotation indexing
3. **Query with filters**: Use `type:annotation` filters to query only annotations when needed
4. **Combine with documents**: Query both annotations and document chunks for comprehensive results
5. **Review quality**: Verify annotation extraction quality for your specific Zotero setup

## Troubleshooting

### Annotations Not Indexed
- **Check configuration**: Verify `include_annotations=true` in `citeloom.toml` or CLI flag
- **Check Web API**: Ensure Web API credentials are configured (`ZOTERO_API_KEY`)
- **Check Zotero**: Verify annotations exist in Zotero (view in Zotero desktop)
- **Check logs**: Review import logs for annotation extraction warnings

### Annotation Extraction Failures
- **Rate limits**: If Web API rate limits are encountered, annotations are skipped gracefully
- **Network issues**: Annotation extraction requires internet connection (Web API)
- **Missing attachments**: Annotations are only extracted for PDF attachments that exist
- **Check logs**: Review import logs for specific error messages

### Storage Growth
- **Expected behavior**: Annotation indexing increases storage (separate points per annotation)
- **Disable if needed**: Set `include_annotations=false` to disable for future imports
- **Selective indexing**: Consider enabling only for specific collections

## See Also

- [Zotero Configuration](../docs/environment-config.md#zotero)
- [Querying Chunks](../README.md#query-chunks)
- [Full-Text Reuse](./zotero-fulltext-reuse.md)

