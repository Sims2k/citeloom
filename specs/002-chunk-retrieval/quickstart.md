# Quickstart: Project-Scoped Citable Chunk Retrieval

**Date**: 2025-01-27  
**Feature**: 002-chunk-retrieval

This guide helps you get started with ingesting documents, querying chunks, and using MCP tools for AI editor integration.

## Prerequisites

1. **Python 3.12.x** installed (via pyenv, pinned in `.python-version`)
2. **uv** installed for package management
3. **Qdrant** running (local or cloud)
4. **Zotero** with Better BibTeX (optional, for citation metadata)

## Setup

### 1. Install Dependencies

```bash
# Ensure Python 3.12.x is active
pyenv install -s 3.12.8 && pyenv local 3.12.8

# Sync environment and dependencies
uv sync
```

### 2. Configure Qdrant

**Option A: Local Qdrant (Docker)**

```bash
# Start Qdrant via docker-compose
docker-compose up -d qdrant

# Verify Qdrant is running
curl http://localhost:6333/health
```

**Option B: Qdrant Cloud**

1. Create account at [cloud.qdrant.io](https://cloud.qdrant.io)
2. Create a cluster and get API key
3. Use cluster URL and API key in configuration

### 3. Configure Project

Create `citeloom.toml` in project root:

```toml
[project."citeloom/clean-arch"]
collection = "proj-citeloom-clean-arch"
references_json = "references/clean-arch.json"
embedding_model = "fastembed/all-MiniLM-L6-v2"
hybrid_enabled = true

[chunking]
max_tokens = 450
overlap_tokens = 60
heading_context = 2
tokenizer = "minilm"  # Must match embedding model tokenizer

[qdrant]
url = "http://localhost:6333"  # Or your Qdrant Cloud URL
api_key = ""  # Only if using Qdrant Cloud
timeout_ms = 15000
create_fulltext_index = true  # Required for hybrid search

[paths]
raw_dir = "assets/raw"
audit_dir = "var/audit"
```

### 4. Prepare Reference Metadata (Optional)

Export from Zotero with Better BibTeX:

1. In Zotero, select your collection
2. Right-click → Better BibTeX → Export Collection
3. Choose format: **CSL JSON**
4. Save to `references/<project-name>.json`
5. Enable "Keep updated" for auto-sync

**Example CSL-JSON entry**:
```json
{
  "id": "cleanArchitecture2023",
  "type": "book",
  "title": "Clean Architecture: A Craftsman's Guide to Software Structure and Design",
  "author": [
    {"family": "Martin", "given": "Robert C."}
  ],
  "issued": {"date-parts": [[2017]]},
  "DOI": "10.1000/xyz123"
}
```

## Usage

### Ingest Documents

**Single document**:
```bash
uv run citeloom ingest \
  --project citeloom/clean-arch \
  --references references/clean-arch.json \
  ./assets/raw/clean-arch.pdf
```

**Directory of documents**:
```bash
uv run citeloom ingest \
  --project citeloom/clean-arch \
  --references references/clean-arch.json \
  ./assets/raw/
```

**What happens**:
1. Document converted with Docling (OCR enabled if scanned)
2. Heading-aware chunking with overlap
3. Citation metadata matched from CSL-JSON
4. Embeddings generated (FastEmbed by default)
5. Chunks upserted into Qdrant collection
6. Audit log written to `var/audit/`

**Output**:
```
Starting ingestion for project 'citeloom/clean-arch' correlation_id=abc123...
Ingestion complete! 1250 chunks written.

Next steps:
  uv run citeloom query --project citeloom/clean-arch --q "your query here" --k 6
```

### Query Chunks

**Semantic search**:
```bash
uv run citeloom query \
  --project citeloom/clean-arch \
  --q "entities vs value objects" \
  --k 6
```

**With tag filter**:
```bash
uv run citeloom query \
  --project citeloom/clean-arch \
  --q "dependency inversion" \
  --k 6 \
  --tags architecture design
```

**Output format**:
```
Results (6 chunks):

1. [Score: 0.87] (cleanArchitecture2023, pp. 45-46, "Entities and Value Objects")
   Entities and value objects are distinct patterns in domain modeling...
   Section: Part I > Chapter 3

2. [Score: 0.82] (cleanArchitecture2023, pp. 78-79, "Dependency Inversion")
   The Dependency Inversion Principle states that...
   Section: Part II > Chapter 11
```

### Inspect Collection

```bash
uv run citeloom inspect --project citeloom/clean-arch --sample 3
```

**Output**:
```
Project: citeloom/clean-arch
Collection: proj-citeloom-clean-arch
Size: 1,250 chunks
Embedding Model: fastembed/all-MiniLM-L6-v2
Hybrid Enabled: true

Payload Keys: project, source, zotero, doc, embed_model, version, fulltext
Indexes: keyword (project, zotero.tags), fulltext (fulltext)

Sample payloads:
1. chunk-abc123: clean-arch.pdf, pp. 45-46, citekey=cleanArchitecture2023
2. chunk-def456: clean-arch.pdf, pp. 78-79, citekey=cleanArchitecture2023
3. chunk-ghi789: ddd.pdf, pp. 12-13, citekey=dddEvans2003
```

### Validate Configuration

```bash
uv run citeloom validate --project citeloom/clean-arch
```

**Checks performed**:
- ✅ Tokenizer matches embedding model family
- ✅ Qdrant is reachable
- ✅ Collection exists
- ✅ Embedding model matches configuration
- ✅ Payload indexes present
- ✅ References JSON file exists

### Reindex Project

**Safe reindex (idempotent)**:
```bash
uv run citeloom reindex --project citeloom/clean-arch ./assets/raw/
```

**Force rebuild (migration)**:
```bash
uv run citeloom reindex \
  --project citeloom/clean-arch \
  --force-rebuild \
  ./assets/raw/
```

## MCP Integration

### Setup MCP Server

1. **Configure MCP server** (e.g., in Cursor/Claude Desktop settings):

```json
{
  "mcpServers": {
    "citeloom": {
      "command": "uv",
      "args": ["run", "citeloom", "mcp-server"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "CITELOOM_CONFIG": "./citeloom.toml"
      }
    }
  }
}
```

2. **Restart editor** to load MCP server

### Use MCP Tools in Editor

**Example prompts**:

```
@citeloom find_chunks project="citeloom/clean-arch" query="dependency inversion" top_k=3

@citeloom query_hybrid project="citeloom/clean-arch" query="entities value objects" top_k=6

@citeloom inspect_collection project="citeloom/clean-arch" sample=2
```

**Tool responses** return trimmed text with citation metadata:
- `render_text`: Trimmed chunk text (≤1800 chars)
- `citekey`: Citation key for bibliography
- `page_span`: Page numbers `(start, end)`
- `section`: Section heading
- `doi`/`url`: Document identifiers

## Troubleshooting

### "Embedding model mismatch" Error

**Problem**: Trying to ingest with different embedding model than existing collection.

**Solution**:
```bash
# Use force rebuild to create new collection
uv run citeloom reindex --project citeloom/clean-arch --force-rebuild ./assets/raw/
```

### "Metadata not found" Warning

**Problem**: Document doesn't match entries in CSL-JSON file.

**Solutions**:
1. Add document to Zotero collection and re-export CSL-JSON
2. Verify DOI matches in both document and CSL-JSON
3. Check title normalization (case-insensitive, punctuation removed)
4. Proceed anyway (chunks will be created without full metadata)

### "Timeout" Error in MCP Tools

**Problem**: Query takes too long (>15s).

**Solutions**:
1. Reduce `top_k` (try `top_k=3` instead of 6)
2. Check Qdrant performance (local vs cloud latency)
3. Disable hybrid search if not needed (`hybrid_enabled=false`)

### "Tokenizer mismatch" Validation Error

**Problem**: Tokenizer family doesn't match embedding model.

**Solution**:
```toml
# In citeloom.toml
[chunking]
tokenizer = "minilm"  # Must match FastEmbed MiniLM tokenizer

[project."citeloom/clean-arch"]
embedding_model = "fastembed/all-MiniLM-L6-v2"  # MiniLM tokenizer
```

## Next Steps

1. **Fine-tune chunking**: Adjust `max_tokens`, `overlap_tokens`, `heading_context` in config
2. **Enable hybrid search**: Set `hybrid_enabled=true` for better keyword matching
3. **Add more projects**: Create additional `[project."..."]` blocks in `citeloom.toml`
4. **Use MCP tools**: Integrate with your AI editor workflows
5. **Review audit logs**: Check `var/audit/*.jsonl` for ingest statistics

## Performance Tips

- **Batch size**: Process directories in batches (system processes all by default)
- **Hybrid search**: Enable only if keyword relevance is important
- **Embedding model**: FastEmbed (local) is faster than OpenAI (API calls)
- **Qdrant location**: Local is faster than cloud (consider latency)

## References

- **Specification**: [spec.md](./spec.md)
- **Data Model**: [data-model.md](./data-model.md)
- **Port Contracts**: [contracts/ports.md](./contracts/ports.md)
- **MCP Tool Contracts**: [contracts/mcp-tools.md](./contracts/mcp-tools.md)
- **Implementation Plan**: [plan.md](./plan.md)

