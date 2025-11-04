# CiteLoom Setup Guide

Complete step-by-step instructions for setting up CiteLoom and Qdrant.

## Prerequisites

- Python 3.12 (managed via `uv`)
- Docker (for running Qdrant locally)
- Git

## Step 1: Clone and Setup Project

```bash
# Clone the repository (if not already cloned)
git clone <repository-url>
cd citeloom

# Install Python dependencies
uv sync
```

## Step 2: Start Qdrant Vector Database

CiteLoom requires Qdrant for persistent storage of chunks and embeddings. You have three options:

### Option A: Local Qdrant with Docker (Recommended for Development)

```bash
# Start Qdrant in a Docker container
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant
```

**Verify Qdrant is running:**
```bash
# Check container status
docker ps | grep qdrant

# Or test the health endpoint
curl http://localhost:6333/health
```

**Stop Qdrant:**
```bash
docker stop qdrant
docker rm qdrant
```

### Option B: Qdrant Cloud (Recommended for Production)

1. Sign up at [Qdrant Cloud](https://cloud.qdrant.io/)
2. Create a cluster and get your URL and API key
3. Update `citeloom.toml`:
   ```toml
   [qdrant]
   url = "https://your-cluster-url.qdrant.io"
   api_key = "your-api-key-here"
   ```

### Option C: Docker Compose (If you have docker-compose.yml)

```bash
docker-compose up -d qdrant
```

## Step 3: Configure CiteLoom

Create or edit `citeloom.toml` in the project root:

```toml
# Project configuration
[project."citeloom/clean-arch"]
collection = "proj-citeloom-clean-arch"
references_json = "references/clean-arch.json"
embedding_model = "fastembed/all-MiniLM-L6-v2"
hybrid_enabled = true

# Chunking settings
[chunking]
max_tokens = 450
overlap_tokens = 60
heading_context = 2
tokenizer = "minilm"

# Qdrant configuration
[qdrant]
url = "http://localhost:6333"  # Use your Qdrant Cloud URL for Option B
api_key = ""  # Only needed for Qdrant Cloud
timeout_ms = 15000
create_fulltext_index = true  # Required for hybrid search

# Paths
[paths]
raw_dir = "assets/raw"
audit_dir = "var/audit"
```

## Step 4: Prepare Document Assets

```bash
# Create directories
mkdir -p assets/raw references var/audit

# Add your PDFs, markdown files, etc. to assets/raw/
# Example:
# cp ~/Documents/my-paper.pdf assets/raw/
```

## Step 5: Ingest Documents

```bash
# Ingest all documents in assets/raw (default)
uv run citeloom ingest run --project citeloom/clean-arch

# Or ingest a specific document
uv run citeloom ingest run --project citeloom/clean-arch ./assets/raw/document.pdf

# Or ingest from a custom directory
uv run citeloom ingest run --project citeloom/clean-arch ./my-documents/
```

**Expected output:**
```
Found 1 document(s) to process
Processing: document.pdf
  [OK] 42 chunks from document.pdf
============================================================
Ingested 42 chunks from 1 document(s)
```

## Step 6: Query Chunks

```bash
# Semantic search
uv run citeloom query run --project citeloom/clean-arch \
  --query "entities vs value objects" \
  --top-k 6

# Hybrid search (full-text + vector)
uv run citeloom query run --project citeloom/clean-arch \
  --query "dependency inversion" \
  --hybrid \
  --top-k 6
```

## Common Use Cases

### Use Case 1: Local PDF Import

Import PDF files from your local file system:

```bash
# 1. Place PDFs in assets/raw directory
cp ~/Documents/papers/*.pdf assets/raw/

# 2. Ingest all documents
uv run citeloom ingest run --project research/papers

# 3. Search the imported content
uv run citeloom query run \
  --project research/papers \
  --query "your search query" \
  --top-k 10
```

### Use Case 2: Zotero Collection Import

Import all PDF attachments from a Zotero collection:

```bash
# 1. Browse your Zotero library
uv run citeloom zotero list-collections

# 2. View items in a specific collection
uv run citeloom zotero browse-collection --collection "Research Papers"

# 3. Import all PDFs from the collection
uv run citeloom ingest run \
  --project research/zotero-papers \
  --zotero-collection "Research Papers"

# 4. Query imported papers
uv run citeloom query run \
  --project research/zotero-papers \
  --query "machine learning" \
  --hybrid \
  --top-k 8
```

### Use Case 3: Tag-Based Selective Import

Import only papers matching specific tags:

```bash
# 1. List available tags
uv run citeloom zotero list-tags

# 2. Import papers with "ML" or "AI" tags, excluding drafts
uv run citeloom ingest run \
  --project research/ml-papers \
  --zotero-collection "Research Papers" \
  --zotero-tags "ML,AI" \
  --exclude-tags "Draft"

# 3. Verify import
uv run citeloom inspect collection --project research/ml-papers
```

### Use Case 4: Large Batch Import with Resumability

For large collections, use checkpointing to enable resumability:

```bash
# Start import (creates checkpoint automatically)
uv run citeloom ingest run \
  --project research/large-collection \
  --zotero-collection "Large Collection"

# If interrupted, resume from checkpoint
uv run citeloom ingest run \
  --project research/large-collection \
  --zotero-collection "Large Collection" \
  --resume

# After completion, cleanup checkpoint files
uv run citeloom ingest run \
  --project research/large-collection \
  --zotero-collection "Large Collection" \
  --cleanup-checkpoints
```

### Use Case 5: Two-Phase Import Workflow

Download first, then process separately:

```bash
# Phase 1: Download attachments only
uv run citeloom ingest download \
  --zotero-collection "Research Papers"

# Phase 2: Process downloaded files
uv run citeloom ingest process-downloads \
  --project research/papers \
  --collection-key ABC12345

# Resume processing if interrupted
uv run citeloom ingest process-downloads \
  --project research/papers \
  --collection-key ABC12345 \
  --resume
```

### Use Case 6: Explore Recent Additions

Quickly see what's new in your Zotero library:

```bash
# View recently added items
uv run citeloom zotero recent-items --limit 20

# Browse a specific collection
uv run citeloom zotero browse-collection \
  --collection "Recent Papers" \
  --subcollections
```

## Step 7: Set Up MCP Integration (Optional)

CiteLoom uses FastMCP for Model Context Protocol (MCP) server integration with AI editors like Cursor and Claude Desktop.

### FastMCP Configuration

CiteLoom includes a `fastmcp.json` configuration file at the project root:

```json
{
  "dependencies": ["python-dotenv"],
  "transport": "stdio",
  "entrypoint": "src.infrastructure.mcp.server:create_mcp_server"
}
```

This declarative configuration enables:
- Automatic dependency management with `uv`
- STDIO transport for editor integration
- Consistent deployment across environments

### Editor Configuration

**For Cursor or Claude Desktop**, add to your MCP settings:

```json
{
  "mcpServers": {
    "citeloom": {
      "command": "uv",
      "args": ["run", "citeloom", "mcp-server"],
      "env": {
        "CITELOOM_CONFIG": "./citeloom.toml",
        "QDRANT_URL": "http://localhost:6333"
      }
    }
  }
}
```

**Available MCP Tools:**

- `list_projects`: List all configured projects (no timeout, fast enumeration)
- `ingest_from_source`: Ingest documents from files or Zotero (15s timeout)
- `query`: Dense-only vector search (8s timeout)
- `query_hybrid`: Hybrid search with RRF fusion (15s timeout)
- `inspect_collection`: Inspect collection stats and model bindings (5s timeout)

All tools include:
- Project filtering (server-side enforcement)
- Correlation IDs for tracing
- Bounded outputs (text trimmed to 1,800 chars)
- Standardized error codes

## Troubleshooting

### Qdrant Connection Issues

**Problem:** `Query failed: Project not found` or connection errors

**Solutions:**
1. **Check Qdrant is running:**
   ```bash
   docker ps | grep qdrant
   curl http://localhost:6333/health
   ```

2. **Verify URL in citeloom.toml matches your Qdrant setup**

3. **Check firewall/network settings** if using remote Qdrant

### In-Memory Fallback Warning

If you see warnings about "in-memory fallback":
- Qdrant isn't running or can't be reached
- Data will not persist between command runs
- Start Qdrant using Step 2 above to enable persistent storage

### No Documents Found

**Problem:** `No supported documents found in assets/raw`

**Solutions:**
1. Check that files have supported extensions: `.pdf`, `.txt`, `.md`
2. Verify `raw_dir` path in `citeloom.toml` is correct
3. Ensure files exist in the directory

### Metadata Not Resolved

**Problem:** Warnings about "Metadata not resolved"

**Solutions:**
1. This is non-blocking - documents will still be ingested
2. Add entries to `references/clean-arch.json` (CSL-JSON format from Zotero)
3. Include DOI, citekey, or matching title for automatic resolution

## Environment Configuration

Create a `.env` file in the project root to configure API keys and settings. Here's a complete example:

```bash
# ============================================================================
# CiteLoom Environment Configuration
# ============================================================================

# ----------------------------------------------------------------------------
# OpenAI Configuration (Optional)
# ----------------------------------------------------------------------------
# Used for OpenAI embeddings. Falls back to FastEmbed if not set.
# OPENAI_API_KEY=your-openai-api-key-here  # Optional: only needed for OpenAI embeddings

# ----------------------------------------------------------------------------
# Qdrant Configuration
# ----------------------------------------------------------------------------
# For local Qdrant (Docker):
QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=  # Not needed for local

# For Qdrant Cloud (uncomment and fill):
# QDRANT_API_KEY=your-qdrant-cloud-api-key-here
# QDRANT_URL=your-qdrant-cloud-url-here

# ----------------------------------------------------------------------------
# Zotero Configuration
# ----------------------------------------------------------------------------
# Option 1: Remote Zotero Access (requires API key)
# ZOTERO_LIBRARY_ID=your-library-id
# ZOTERO_LIBRARY_TYPE=user  # or 'group'
# ZOTERO_API_KEY=your-zotero-api-key
# ZOTERO_LOCAL=false

# Option 2: Local Zotero Access (requires Zotero desktop running)
ZOTERO_LIBRARY_ID=0
ZOTERO_LOCAL=true
```

### Configuration Details

**OpenAI API Key** (Optional):
- Get from: https://platform.openai.com/api-keys
- Only needed if using OpenAI embeddings
- If not set, uses FastEmbed default embeddings

**Qdrant Configuration**:
- **Local**: Use `http://localhost:6333` (no API key)
- **Cloud**: Requires API key and cluster URL from https://cloud.qdrant.io/

**Zotero Configuration**:
- **Remote**: Requires library ID, type, and API key from https://www.zotero.org/settings/keys
- **Local**: Requires `ZOTERO_LOCAL=true` and Zotero desktop app running
- Local library ID is typically `0` or `1` for user library

### Windows-Specific Zotero Local Database Configuration

On Windows, CiteLoom automatically detects your Zotero profile by checking these locations in order:
1. `%APPDATA%\Zotero\Profiles\{profile_id}\zotero.sqlite`
2. `%LOCALAPPDATA%\Zotero\Profiles\{profile_id}\zotero.sqlite`
3. `%USERPROFILE%\Documents\Zotero\Profiles\{profile_id}\zotero.sqlite`

**If auto-detection fails**, you can manually configure the database path in `citeloom.toml`:

```toml
[zotero]
# Windows example: Typical location in AppData\Roaming
db_path = "C:\\Users\\YourName\\AppData\\Roaming\\Zotero\\Profiles\\xxxxx.default\\zotero.sqlite"
storage_dir = "C:\\Users\\YourName\\AppData\\Roaming\\Zotero\\Profiles\\xxxxx.default\\zotero\\storage"
```

**Finding Your Zotero Profile Path on Windows**:

1. **Method 1: Using Zotero Desktop**
   - Open Zotero
   - Go to `Help` → `Show Data Directory`
   - This opens the profile folder in Windows Explorer
   - Note the path (e.g., `C:\Users\YourName\AppData\Roaming\Zotero\Profiles\xxxxx.default`)
   - The database file is `zotero.sqlite` in that folder

2. **Method 2: Using File Explorer**
   - Press `Win + R` to open Run dialog
   - Type `%APPDATA%\Zotero\Profiles` and press Enter
   - Look for a folder with a name like `xxxxx.default` (where `xxxxx` is random characters)
   - Open that folder to find `zotero.sqlite`

3. **Method 3: Check Alternative Locations**
   - If not found in `%APPDATA%`, check `%LOCALAPPDATA%\Zotero\Profiles`
   - Or check `%USERPROFILE%\Documents\Zotero\Profiles`

**Troubleshooting Windows Profile Detection**:

- **"Zotero profile not found" error**:
  - Ensure Zotero desktop has been run at least once (creates the profile)
  - Verify the profile path exists in File Explorer
  - Check if you have multiple Zotero profiles and use the correct one
  - Try manually specifying `db_path` in `citeloom.toml`

- **"Database is locked" error**:
  - Close Zotero desktop application
  - Wait a few seconds for Zotero to release the database lock
  - Try the command again

- **"Database file not found" error**:
  - Verify the path in `citeloom.toml` is correct (use double backslashes `\\` or forward slashes `/`)
  - Check that `zotero.sqlite` exists at the specified path
  - Ensure you have read permissions to the file

- **Storage directory not found**:
  - The storage directory is typically alongside the profile directory
  - Look for `zotero\storage` subdirectory in the profile folder
  - Or specify `storage_dir` explicitly in `citeloom.toml`

**Example Windows Configuration**:

```toml
[zotero]
# Full path to zotero.sqlite database file
db_path = "C:\\Users\\John\\AppData\\Roaming\\Zotero\\Profiles\\a1b2c3d4.default\\zotero.sqlite"

# Storage directory for attachment files (optional, auto-detected if not specified)
storage_dir = "C:\\Users\\John\\AppData\\Roaming\\Zotero\\Profiles\\a1b2c3d4.default\\zotero\\storage"
```

**Important Notes**:
- The `.env` file is automatically excluded from version control
- Environment variables take precedence over `.env` file values
- Never commit API keys to the repository
- Windows paths can use either backslashes (`\\`) or forward slashes (`/`) in `citeloom.toml`

## Next Steps

- Review [Environment Configuration Guide](environment-config.md) for API keys and Zotero setup
- Review [Quickstart Guide](../specs/003-framework-implementation/quickstart.md) for advanced settings
- Explore [MCP Integration](../README.md#mcp-integration) for editor workflows
- Check [Architecture Documentation](../.specify/memory/constitution.md) for design details

