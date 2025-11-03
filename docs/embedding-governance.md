# Embedding Model Governance

This guide explains how CiteLoom manages embedding model consistency across collections and provides friendly diagnostics when model mismatches occur.

## Overview

Each CiteLoom collection is **bound to a specific embedding model** at creation time. This ensures consistency across all chunks in the collection, maintaining retrieval quality and preventing embedding mismatches that would degrade search results.

CiteLoom includes **write guards** that prevent accidentally mixing embedding models within a collection, with friendly error messages that guide you to resolve mismatches.

## Why Model Governance Matters

Embedding models produce **incompatible embeddings** - embeddings from different models cannot be meaningfully compared. Mixing models within a collection would:
- Degrade retrieval quality (semantic similarity broken)
- Create inconsistent results (some chunks use model A, others use model B)
- Waste storage (duplicate chunks with different embeddings)
- Confuse queries (filtering and ranking become unreliable)

## Bound Model Tracking

When a collection is created, CiteLoom stores the embedding model identifier:
- **Model name**: e.g., `"fastembed/all-MiniLM-L6-v2"`
- **Provider**: e.g., `"fastembed"`
- **Collection metadata**: Stored in Qdrant collection metadata

This bound model is checked on every write operation to prevent accidental mixing.

## Model Mismatch Detection

When you attempt to write chunks with a different embedding model than the bound model, CiteLoom:
1. **Detects the mismatch**: Compares requested model vs bound model
2. **Blocks the write**: Prevents mixing incompatible embeddings
3. **Provides friendly error**: Clear guidance on resolution

### Example Error Message

```
Collection 'my-project' is bound to embedding model 'BAAI/bge-small-en-v1.5'.
You requested 'sentence-transformers/all-MiniLM-L6-v2'.

Resolution options:
1. Switch back to the bound model: Use 'BAAI/bge-small-en-v1.5' for this collection
2. Migrate to the new model: Run 'citeloom reindex --force-rebuild' to migrate the collection

The --force-rebuild flag bypasses the write guard when migration is intended.
```

## Inspecting Bound Model

Check which embedding model is bound to a collection:

### Via CLI
```bash
citeloom inspect project my-project --show-embedding-model
```

### Via MCP
The `inspect` tool response includes embedding model information in collection metadata.

### Expected Output
```
Collection: my-project
Embedding Model: BAAI/bge-small-en-v1.5
Provider: fastembed
Collection ID: proj-my-project
```

## Resolving Model Mismatches

### Option 1: Switch Back to Bound Model

Use the bound model for new imports:

```bash
# Verify bound model
citeloom inspect project my-project --show-embedding-model

# Use bound model in project configuration
# Edit citeloom.toml:
[project."my-project"]
embedding_model = "BAAI/bge-small-en-v1.5"  # Use bound model
```

### Option 2: Migrate to New Model

If you intentionally want to switch models, migrate the collection:

```bash
# Migrate collection to new model (reprocesses all documents)
citeloom reindex --project my-project --force-rebuild --embedding-model "sentence-transformers/all-MiniLM-L6-v2"
```

The `--force-rebuild` flag:
- Bypasses the write guard
- Allows writes with the new model
- Updates the bound model in collection metadata
- **Re-processes all documents** (full re-embedding and re-indexing)

**Warning**: Migration is **expensive** - it re-processes all documents in the collection. Use only when necessary.

## Creating Collections with Specific Models

Set the embedding model when creating a collection:

```toml
[project."my-project"]
collection = "proj-my-project"
references_json = "references/my-project.json"
embedding_model = "fastembed/all-MiniLM-L6-v2"  # Model bound at creation
hybrid_enabled = true
```

The model specified here becomes the bound model for the collection.

## Model Compatibility

### Same Model, Different Formats
Models with the same identifier are compatible:
- `"fastembed/all-MiniLM-L6-v2"` == `"fastembed/all-MiniLM-L6-v2"` ✓
- `"BAAI/bge-small-en-v1.5"` == `"BAAI/bge-small-en-v1.5"` ✓

### Different Models
Different model identifiers are incompatible:
- `"fastembed/all-MiniLM-L6-v2"` ≠ `"sentence-transformers/all-MiniLM-L6-v2"` ✗
- `"BAAI/bge-small-en-v1.5"` ≠ `"BAAI/bge-base-en-v1.5"` ✗

### Version Differences
Model versions are part of the identifier:
- `"all-MiniLM-L6-v2"` ≠ `"all-MiniLM-L6-v1"` ✗ (different versions)
- Models are identified by full path/name, including version

## Best Practices

1. **Choose model carefully**: Select embedding model at collection creation time
2. **Document model choice**: Note which model you're using for each collection
3. **Consistent models**: Use the same model for related collections when possible
4. **Avoid migration**: Don't migrate unless necessary (expensive operation)
5. **Check before import**: Verify bound model before importing new documents

## Troubleshooting

### Write Guard Errors
- **Check bound model**: Use `citeloom inspect --show-embedding-model`
- **Verify configuration**: Ensure project config matches bound model
- **Use force-rebuild**: If intentional migration, use `--force-rebuild` flag

### Model Not Found
- **Check model name**: Verify model identifier is correct
- **Check provider**: Ensure provider (fastembed, sentence-transformers, etc.) is available
- **Check dependencies**: Verify required packages are installed

### Migration Issues
- **Backup first**: Consider backing up collection before migration
- **Time intensive**: Migration re-processes all documents (may take hours)
- **Verify results**: Check query results after migration to ensure quality

## Configuration

### Project-Level Model
```toml
[project."my-project"]
embedding_model = "fastembed/all-MiniLM-L6-v2"  # Bound at collection creation
```

### Environment Variable Override
```bash
export ZOTERO_EMBEDDING_MODEL="fastembed/all-MiniLM-L6-v2"
```

Note: Environment variables may override project configuration, but write guards still enforce consistency within collections.

## See Also

- [Project Configuration](../README.md#config)
- [Inspecting Collections](#inspecting-bound-model)
- [Model Migration](#option-2-migrate-to-new-model)

