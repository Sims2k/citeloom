# Zotero Full-Text Reuse

This guide explains how CiteLoom reuses text that Zotero has already extracted to speed up imports by 50-80% while maintaining proper chunking and embedding for all documents.

## Overview

When Zotero indexes PDFs, it extracts and stores full-text content in its SQLite database. CiteLoom can reuse this extracted text to skip the time-consuming Docling conversion/OCR step, significantly speeding up imports for documents Zotero has already processed.

**Important**: Full-text reuse only skips the conversion/OCR step. All documents (with or without fulltext) must still be:
- **Chunked** into appropriately sized pieces (required for LLM context windows)
- **Embedded** with the selected embedding model
- **Indexed** in the vector database

Large books would exceed context limits if indexed as single units, so chunking is mandatory regardless of text source.

## Performance Benefits

Full-text reuse provides **50-80% speedup** for collections where 70% or more documents have Zotero fulltext available. This is measured by comparing total import time (download + conversion + chunking + embedding + storage) before and after full-text reuse.

### Example Timeline

**Without full-text reuse** (20 documents, 15 with Zotero fulltext):
- Docling conversion: 30 minutes (all 20 documents)
- Chunking: 2 minutes
- Embedding: 3 minutes
- Indexing: 2 minutes
- **Total: 37 minutes**

**With full-text reuse** (same collection):
- Fulltext extraction: 1 minute (15 documents with fulltext)
- Docling conversion: 7.5 minutes (5 documents without fulltext)
- Chunking: 2 minutes (all 20 documents)
- Embedding: 3 minutes (all 20 documents)
- Indexing: 2 minutes (all 20 documents)
- **Total: 15.5 minutes** (58% speedup)

## Enabling Full-Text Reuse

Full-text reuse is **enabled by default** (`prefer_zotero_fulltext=true`) for performance benefits.

### Configuration

Enable/disable in `citeloom.toml`:

```toml
[zotero]
prefer_zotero_fulltext = true  # Default: true
```

Or via environment variable:
```bash
export ZOTERO_PREFER_FULLTEXT=true
```

### CLI Option

Override for a single import:

```bash
citeloom ingest run --project my-project --zotero-collection "Research" --prefer-zotero-fulltext
```

## How Full-Text Reuse Works

1. **Check Zotero fulltext table**: CiteLoom queries the Zotero `fulltext` table for each attachment
2. **Validate quality**: Check that fulltext is:
   - Non-empty
   - Minimum length (default: 100 characters, configurable via `zotero.fulltext.min_length`)
   - Reasonable structure (sentences, paragraphs)
3. **Use fulltext if valid**: If quality checks pass, use Zotero fulltext and skip Docling conversion
4. **Fallback to Docling**: If fulltext is unavailable, missing, or fails quality checks, automatically fall back to Docling conversion pipeline
5. **Process normally**: All documents (with or without fulltext) proceed through chunking, embedding, and indexing steps

## Quality Validation

CiteLoom validates Zotero fulltext quality before reuse:

### Validation Checks
- **Non-empty**: Fulltext must contain text
- **Minimum length**: Default 100 characters (configurable)
- **Structure**: Should contain sentence/paragraph patterns (basic validation)

### Quality Configuration

Adjust minimum length threshold in `citeloom.toml`:

```toml
[zotero.fulltext]
min_length = 100  # Minimum text length for quality validation
```

### Fallback Behavior

If fulltext fails quality validation, CiteLoom:
- Logs a warning indicating why fulltext was rejected
- Automatically falls back to Docling conversion
- Processes the document normally (no errors, no user intervention)

## Mixed Provenance (Page-Level Fallback)

CiteLoom supports **page-level mixed provenance** where some pages come from Zotero fulltext and others from Docling conversion:

### When Mixed Provenance Occurs
- Document has partial Zotero fulltext (some pages indexed, others missing)
- Fulltext quality check fails for specific pages
- Zotero indexing was incomplete or failed for some pages

### How Mixed Provenance Works
1. **Extract Zotero pages**: Use fulltext for pages available in Zotero
2. **Extract Docling pages**: Use Docling conversion for missing/invalid pages
3. **Sequential concatenation**: Combine pages in order (fulltext pages followed by Docling pages) into a single continuous text stream
4. **Maintain provenance**: Track which pages came from which source in audit trail
5. **Process normally**: Chunk, embed, and index the complete concatenated text

### Audit Trail

Mixed provenance metadata is logged in audit trail:

```json
{
  "source": "mixed",
  "pages_from_zotero": [1, 2, 3, 4, 5],
  "pages_from_docling": [6, 7, 8, 9, 10],
  "total_pages": 10,
  "zotero_coverage": 0.5
}
```

## Documents Without Fulltext

Many documents may not have Zotero fulltext available:
- **Not indexed**: Zotero never attempted indexing
- **Indexing failed**: Zotero indexing encountered errors
- **Unsupported types**: Document types Zotero doesn't index (images, Office documents, etc.)
- **Incomplete indexing**: Zotero indexing was partial or interrupted

**This is normal and expected**. CiteLoom automatically falls back to Docling conversion for all documents without fulltext, treating this as seamless normal processing flow (no errors, warnings, or user intervention).

## Chunking Still Required

**Critical**: Full-text reuse only optimizes the conversion step. Chunking is always required because:
- **LLM context limits**: Large books would exceed context windows if indexed as single units
- **Embedding model limits**: Embedding models have token limits per chunk
- **Retrieval quality**: Smaller chunks improve retrieval precision

All documents (with or without fulltext) are:
- **Chunked** into appropriately sized pieces (`max_tokens`, `overlap_tokens` settings)
- **Embedded** with the selected embedding model
- **Indexed** as separate vector points

## Configuration Options

### Full-Text Preference
```toml
[zotero]
prefer_zotero_fulltext = true  # Default: true (enabled for performance)
```

### Quality Threshold
```toml
[zotero.fulltext]
min_length = 100  # Minimum text length for quality validation (default: 100)
```

## Best Practices

1. **Keep fulltext enabled**: Default `prefer_zotero_fulltext=true` provides best performance
2. **Let Zotero index**: Ensure Zotero has indexed documents for fulltext availability
3. **Monitor fallback**: Review audit logs to see which documents used fulltext vs Docling
4. **Quality thresholds**: Adjust `min_length` if needed for your document types
5. **Expect fallback**: Many documents won't have fulltext - Docling fallback is normal

## Troubleshooting

### Fulltext Not Being Used
- **Check Zotero**: Verify Zotero has indexed the documents (view in Zotero desktop)
- **Check quality**: Review logs for quality validation failures
- **Check configuration**: Verify `prefer_zotero_fulltext=true`
- **Check database**: Ensure local database access is working

### Quality Validation Failures
- **Too short**: Increase `min_length` threshold if documents are short but valid
- **Structure issues**: Check Zotero fulltext quality in Zotero database
- **Expected fallback**: Quality validation failures trigger automatic Docling fallback (normal behavior)

### Performance Not Improved
- **Fulltext availability**: Check how many documents actually have Zotero fulltext
- **Conversion time**: Measure Docling conversion time vs fulltext extraction time
- **Network latency**: Web API downloads may dominate timing for remote imports

## Audit Logging

CiteLoom maintains audit trails showing fulltext usage:

```json
{
  "document": "document.pdf",
  "fulltext_source": "zotero",
  "pages_from_zotero": [1, 2, 3, 4, 5],
  "pages_from_docling": [],
  "total_pages": 5,
  "zotero_coverage": 1.0
}
```

Review audit logs to verify fulltext reuse is working correctly.

## See Also

- [Zotero Configuration](../docs/environment-config.md#zotero)
- [Local Database Access](./zotero-local-access.md)
- [Source Selection Strategies](./zotero-local-access.md#source-selection-strategies)


