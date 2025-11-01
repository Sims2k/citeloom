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

### Windows PyTorch DLL Loading Error

**Problem:** `OSError: [WinError 1114] Eine DLL-Initialisierungsroutine ist fehlgeschlagen` when running ingest/query commands

**Root Cause:** PyTorch (required by Docling for PDF conversion) has known DLL loading issues on Windows.

**Solutions:**

1. **Use WSL (Windows Subsystem for Linux)** - ✅ **CONFIRMED TO WORK**:
   ```bash
   # Install WSL if not already installed
   wsl --install
   
   # In WSL, install uv and sync dependencies
   wsl
   curl -LsSf https://astral.sh/uv/install.sh | sh
   export PATH="$HOME/.local/bin:$PATH"
   
   # Navigate to project (Windows paths are in /mnt/c/)
   cd /mnt/c/Dev/Python-Projects/citeloom
   
   # Set venv to Linux filesystem to avoid permission issues
   export UV_PROJECT_ENVIRONMENT="$HOME/.citeloom-venv"
   
   # Sync dependencies
   uv sync --python python3.12
   
   # Run commands
   uv run citeloom ingest run --project citeloom/clean-arch
   ```
   
   **Note:** The Windows DLL error is completely resolved in WSL. PyTorch and Docling work correctly.

2. **Downgrade PyTorch to 2.8.0** - ✅ **RECOMMENDED FIX**:
   
   According to [PyTorch issue #166628](https://github.com/pytorch/pytorch/issues/166628), PyTorch 2.9.0 has a known bug causing DLL initialization failures on Windows. The fix is to use PyTorch 2.8.0 instead.
   
   The `pyproject.toml` already pins torch to `<2.9.0`. To apply the fix:
   
   ```bash
   # Remove the virtual environment (if locked by processes, close Python/IDE first)
   Remove-Item -Recurse -Force .venv
   
   # Re-sync dependencies with the torch version constraint
   uv sync
   ```
   
   This will install PyTorch 2.8.0 which works correctly on Windows.

3. **Fix PyTorch Installation (Alternative)**:
   - Manually reinstall PyTorch 2.8.0: `uv pip uninstall torch && uv pip install "torch>=2.8.0,<2.9.0"`
   - Install Visual C++ Redistributables: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - See [PyTorch Windows installation guide](https://pytorch.org/get-started/locally/)

4. **Use Docker for Full Stack** (if available):
   - Run CiteLoom in a Linux container where PyTorch works correctly

**Note:** 
- This is a Windows-specific issue with PyTorch 2.9.0. Linux and macOS users should not experience this problem.
- ✅ **Solution confirmed**: Downgrading to PyTorch 2.8.0 resolves the DLL error completely. The `pyproject.toml` now pins torch to `<2.9.0` to prevent this issue.

## Environment Configuration

For detailed environment variable configuration including Zotero setup, see [Environment Configuration Guide](environment-config.md).

Key points:
- Create `.env` file in project root for API keys
- Environment variables take precedence over `.env` file
- Zotero can be configured for remote or local access
- Better BibTeX integration is automatic when available

## Next Steps

- Review [Environment Configuration Guide](environment-config.md) for API keys and Zotero setup
- Review [Quickstart Guide](../specs/003-framework-implementation/quickstart.md) for advanced settings
- Explore [MCP Integration](../README.md#mcp-integration) for editor workflows
- Check [Architecture Documentation](../.specify/memory/constitution.md) for design details

