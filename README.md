# CiteLoom
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![uv](https://img.shields.io/badge/uv-managed-brightgreen)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/lint-Ruff-informational)](https://docs.astral.sh/ruff/)
[![CI](https://github.com/your-org/citeloom/actions/workflows/ci.yml/badge.svg)](.github/workflows/ci.yml)
Weave long-form sources into small, citable context for your AI work.

## Intro

Turn big, hard-to-skim documents into small, trustworthy snippets you can search, quote,
and reuse in your work. CiteLoom keeps the link to the original source so every answer
is easy to verify and simple to cite.

- Bring your PDFs and notes; we prepare them for search
- Split into clear, readable snippets with helpful context
- Attach citation details so you can reference with confidence
- Keep projects separate to avoid mixing unrelated material
- Use from the command line and your favorite AI tools (MCP integration for Cursor, Claude Desktop)
- Search and get concise answers with links back to the source

## Quick Setup

### 1. Install Dependencies

```bash
# Project setup
uv sync
```

### 2. Start Qdrant Vector Database

```bash
# Option A: Local Docker (recommended)
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant

# Option B: Qdrant Cloud (production)
# Sign up at https://cloud.qdrant.io/ and configure in citeloom.toml
```

### 3. Configure Project

Create `citeloom.toml` (see [Config](#config) section below).

### 4. Ingest Documents

```bash
# Process all documents in assets/raw
uv run citeloom ingest run --project citeloom/clean-arch
```

### 5. Query Chunks

```bash
uv run citeloom query run --project citeloom/clean-arch --query "your query" --top-k 6
```

**Full setup guide:** See [docs/setup-guide.md](docs/setup-guide.md) for detailed instructions.

## Developer Quickstart

```bash
# One-time
pyenv install -s 3.12.8
pyenv local 3.12.8

# Project setup
uv sync

# Quality
uvx ruff format .
uvx ruff check .
uv run mypy .
uv run pytest -q
```

Branching: trunk-based (`main` only). Use short-lived feature branches if needed; merge only when green.

## CLI

### Basic Commands

**Ingest documents**:
```bash
# Process all documents in assets/raw directory (default)
uv run citeloom ingest run --project citeloom/clean-arch

# Process a specific document
uv run citeloom ingest run --project citeloom/clean-arch ./assets/raw/document.pdf

# Process all documents in a custom directory
uv run citeloom ingest run --project citeloom/clean-arch ./path/to/documents/
```

**Query chunks**:
```bash
uv run citeloom query run --project citeloom/clean-arch --query "entities vs value objects" --top-k 6
uv run citeloom query run --project citeloom/clean-arch --query "dependency inversion" --hybrid --top-k 6
```

**MCP Server** (for AI editor integration):
```bash
uv run citeloom mcp-server
```

See also: [Naming alternatives](docs/branding/naming-alternatives.md)

## Use Cases & Examples

### Use Case 1: Import from Local PDF Files

**Scenario**: You have a collection of PDF papers in a local directory and want to make them searchable.

```bash
# 1. Copy PDFs to the default directory
cp ~/Documents/papers/*.pdf assets/raw/

# 2. Ingest all documents
uv run citeloom ingest run --project research/papers

# 3. Query the indexed content
uv run citeloom query run --project research/papers \
  --query "neural network architecture" \
  --top-k 10
```

### Use Case 2: Import from Zotero Collection

**Scenario**: You have a Zotero library with a collection of research papers and want to import all PDF attachments.

```bash
# 1. Browse your Zotero library to find collections
uv run citeloom zotero list-collections

# 2. Browse a specific collection to see what's available
uv run citeloom zotero browse-collection --collection "Machine Learning Papers"

# 3. Import all PDFs from a Zotero collection
uv run citeloom ingest run \
  --project research/ml-papers \
  --zotero-collection "Machine Learning Papers"

# 4. Query the imported papers
uv run citeloom query run \
  --project research/ml-papers \
  --query "transformer architecture" \
  --hybrid \
  --top-k 8
```

### Use Case 3: Selective Import with Tag Filtering

**Scenario**: You only want to import papers with specific tags from a Zotero collection.

```bash
# 1. List available tags in your Zotero library
uv run citeloom zotero list-tags

# 2. Import only papers tagged with "ML" or "AI" but exclude drafts
uv run citeloom ingest run \
  --project research/published-papers \
  --zotero-collection "Research Papers" \
  --zotero-tags "ML,AI" \
  --exclude-tags "Draft"

# 3. Verify what was imported
uv run citeloom inspect collection --project research/published-papers
```

### Use Case 4: Resumable Batch Import with Checkpointing

**Scenario**: You're importing a large collection (100+ documents) and want to be able to resume if interrupted.

```bash
# 1. Start import (creates checkpoint automatically)
uv run citeloom ingest run \
  --project research/large-collection \
  --zotero-collection "Large Collection"

# 2. If interrupted, resume from checkpoint
uv run citeloom ingest run \
  --project research/large-collection \
  --zotero-collection "Large Collection" \
  --resume

# 3. After successful completion, cleanup checkpoint files
uv run citeloom ingest run \
  --project research/large-collection \
  --zotero-collection "Large Collection" \
  --cleanup-checkpoints
```

### Use Case 5: Two-Phase Import (Download Then Process)

**Scenario**: You want to download all attachments first, then process them separately.

```bash
# Phase 1: Download all attachments without processing
uv run citeloom ingest download \
  --zotero-collection "Research Papers" \
  --zotero-tags "Published"

# Phase 2: Process the downloaded files
uv run citeloom ingest process-downloads \
  --project research/papers \
  --collection-key ABC12345

# If processing is interrupted, resume
uv run citeloom ingest process-downloads \
  --project research/papers \
  --collection-key ABC12345 \
  --resume
```

### Use Case 6: Hybrid Search for Technical Content

**Scenario**: You need to find both exact term matches and semantically similar content.

```bash
# Search using hybrid search (combines full-text and vector search)
uv run citeloom query run \
  --project research/papers \
  --query "dependency inversion principle SOLID" \
  --hybrid \
  --top-k 10

# Compare with vector-only search
uv run citeloom query run \
  --project research/papers \
  --query "dependency inversion principle SOLID" \
  --top-k 10
```

### Use Case 7: Project Management and Validation

**Scenario**: You have multiple projects and want to verify their configuration.

```bash
# List all projects
uv run citeloom inspect collection --project research/papers

# Validate project configuration
uv run citeloom validate --project research/papers

# Inspect collection statistics
uv run citeloom inspect collection \
  --project research/papers \
  --sample 5
```

### Minimal `citeloom.toml`

```toml
[project]
id = "citeloom/clean-arch"
collection = "proj-citeloom-clean-arch"
embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
hybrid_enabled = true

[paths]
references = "references/clean-arch.json"
raw_assets = "assets/raw/"
audit_dir = "var/audit/"

[qdrant]
url = "http://localhost:6333"  # Or your Qdrant Cloud URL
api_key = ""  # Only if using Qdrant Cloud
create_fulltext_index = true  # Required for hybrid search
```

**Note**: Qdrant is required for persistent storage. Without it, CiteLoom uses an in-memory fallback that doesn't persist data between commands.
```

### Sample commands

```bash
# Ingest all documents in assets/raw (default directory)
uv run citeloom ingest run --project citeloom/clean-arch

# Ingest a specific document
uv run citeloom ingest run --project citeloom/clean-arch ./assets/raw/clean-arch.pdf

# Ingest all documents in a directory
uv run citeloom ingest run --project citeloom/clean-arch ./documents/

# Query chunks (semantic search)
uv run citeloom query run --project citeloom/clean-arch --query "entities vs value objects" --top-k 6

# Query with hybrid search (full-text + vector)
uv run citeloom query run --project citeloom/clean-arch --query "dependency inversion" --hybrid --top-k 6

# Run MCP server for AI editor integration
uv run citeloom mcp-server
```

## MCP Integration

CiteLoom provides MCP (Model Context Protocol) server integration for AI development environments like Cursor and Claude Desktop.

### Setup MCP Server

1. **Configure MCP server** in your editor settings (e.g., Cursor/Claude Desktop):

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

2. **Restart your editor** to load the MCP server

### Available MCP Tools

- **`list_projects`**: List all configured projects with metadata
- **`find_chunks`**: Vector search for chunks in a project (8s timeout)
- **`query_hybrid`**: Hybrid search combining full-text and vector search (15s timeout)
- **`inspect_collection`**: Inspect collection metadata and sample payloads (5s timeout)
- **`store_chunks`**: Batched upsert of chunks (100-500 chunks, 15s timeout)

All tools enforce strict project filtering and return citation-ready metadata with trimmed text output.

## Environment Configuration

CiteLoom supports environment-based configuration for API keys and sensitive settings. This keeps secrets out of version-controlled files and enables per-environment configuration.

### Setup `.env` File

Create a `.env` file in the project root with your API keys. Here's a complete example with all available options:

```bash
# ============================================================================
# CiteLoom Environment Configuration
# ============================================================================
# This file contains API keys and configuration for CiteLoom.
# Never commit this file to version control - it's automatically ignored.
# ============================================================================

# ----------------------------------------------------------------------------
# OpenAI Configuration (Optional)
# ----------------------------------------------------------------------------
# Used for OpenAI embeddings. If not set, CiteLoom falls back to FastEmbed
# default embeddings (BAAI/bge-small-en-v1.5).
# Get your API key from: https://platform.openai.com/api-keys
# OPENAI_API_KEY=your-openai-api-key-here  # Optional: only needed for OpenAI embeddings

# ----------------------------------------------------------------------------
# Qdrant Configuration
# ----------------------------------------------------------------------------
# For local Qdrant (Docker): Leave these commented or use defaults
# QDRANT_URL=http://localhost:6333
# QDRANT_API_KEY=  # Not needed for local Qdrant

# For Qdrant Cloud: Uncomment and fill in your credentials
# Get your API key from: https://cloud.qdrant.io/
# QDRANT_API_KEY=your-qdrant-cloud-api-key-here
# QDRANT_URL=your-qdrant-cloud-url-here

# ----------------------------------------------------------------------------
# Zotero Configuration
# ----------------------------------------------------------------------------
# CiteLoom supports two modes of Zotero access:
# 1. Remote API access (requires API key) - for synced libraries
# 2. Local API access (requires Zotero desktop running) - for local libraries

# Option 1: Remote Zotero Access (Recommended for Production)
# Get your credentials from: https://www.zotero.org/settings/keys
# ZOTERO_LIBRARY_ID=your-library-id
# ZOTERO_LIBRARY_TYPE=user  # or 'group' for group libraries
# ZOTERO_API_KEY=your-zotero-api-key
# ZOTERO_LOCAL=false  # Explicitly set to false for remote access

# Option 2: Local Zotero Access (Recommended for Development)
# Requires Zotero desktop app running with local API enabled
# ZOTERO_LIBRARY_ID=1  # Typically '1' for user library, '0' also works
# ZOTERO_LOCAL=true  # Enable local API access

# Example: Local Zotero access (current configuration)
ZOTERO_LIBRARY_ID=0
ZOTERO_LOCAL=true

# ----------------------------------------------------------------------------
# Configuration File Override (Optional)
# ----------------------------------------------------------------------------
# Override the default config file path (default: citeloom.toml)
# CITELOOM_CONFIG=./citeloom.toml
```

**Configuration Notes:**

1. **OpenAI API Key**: Optional. Only needed if you want to use OpenAI embeddings instead of the default FastEmbed models. Leave commented if using default embeddings.

2. **Qdrant Configuration**:
   - **Local Docker**: Use `http://localhost:6333` (no API key needed)
   - **Qdrant Cloud**: Requires both `QDRANT_URL` and `QDRANT_API_KEY`
   - The URL format for Qdrant Cloud is: `https://{cluster-id}.{region}.{cloud-provider}.cloud.qdrant.io:6333`

3. **Zotero Configuration**:
   - **Remote Access**: Requires `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE`, and `ZOTERO_API_KEY`
   - **Local Access**: Requires `ZOTERO_LIBRARY_ID` (typically `0` or `1`) and `ZOTERO_LOCAL=true`
   - Local access requires the Zotero desktop app to be running
   - You cannot use both remote and local access simultaneously - choose one mode

4. **Getting Your Zotero API Key**:
   - Go to [Zotero Settings → Feeds/API](https://www.zotero.org/settings/keys)
   - Create a new API key with library access permissions
   - Copy the API key and your user/library ID

5. **Library ID Discovery**:
   - **User library**: Your user ID is shown on the [Zotero Settings page](https://www.zotero.org/settings/keys)
   - **Group library**: Found in the group's URL: `https://www.zotero.org/groups/{library_id}`

**Security Best Practices**:
- Never commit `.env` files to version control (automatically ignored via `.gitignore`)
- Use environment-specific `.env` files for different environments (e.g., `.env.local`, `.env.production`)
- Rotate API keys regularly
- Use Qdrant Cloud API keys with appropriate permissions (read/write only, not admin)

**Note**: The `.env` file is automatically excluded from version control via `.gitignore`. Never commit API keys to the repository.

### Environment Variable Precedence

Environment variables follow this precedence order (highest to lowest):
1. **System/shell environment variables** (explicitly set in your shell)
2. **`.env` file values** (from project root or parent directories)
3. **Default values** (from configuration files or code defaults)

This allows per-session overrides: you can set `QDRANT_API_KEY` in your shell to temporarily use a different key without modifying the `.env` file.

### Zotero Configuration

CiteLoom integrates with Zotero via the pyzotero API for citation metadata resolution. Configure Zotero using environment variables:

#### Remote Zotero Access

For remote Zotero access (synced library):

```bash
ZOTERO_LIBRARY_ID=your-library-id
ZOTERO_LIBRARY_TYPE=user  # or 'group' for group libraries
ZOTERO_API_KEY=your-api-key
```

**Getting your Zotero API key:**
1. Go to [Zotero Settings → Feeds/API](https://www.zotero.org/settings/keys)
2. Create a new API key with library access permissions
3. Copy the API key and your user/library ID

**Getting your Library ID:**
- User library: Your user ID is shown on the [Zotero Settings page](https://www.zotero.org/settings/keys)
- Group library: Found in the group's URL: `https://www.zotero.org/groups/{library_id}`

#### Local Zotero Access

For local Zotero access (requires Zotero desktop app running):

```bash
ZOTERO_LIBRARY_ID=1  # Typically '1' for user library in local mode
ZOTERO_LOCAL=true
```

**Note**: Local access requires Zotero desktop app to be running with the local API enabled. This is useful for development or when you prefer not to use the remote API.

### Optional vs Required Keys

**Optional API Keys** (gracefully degrade when missing):
- `OPENAI_API_KEY`: Falls back to FastEmbed default embeddings if not set
- `CITELOOM_CONFIG`: Defaults to `citeloom.toml` if not set

**Required API Keys** (context-dependent):
- `QDRANT_API_KEY`: Required when using Qdrant Cloud (detected automatically)
- `ZOTERO_LIBRARY_ID`: Required for Zotero metadata resolution
- `ZOTERO_API_KEY`: Required for remote Zotero access (not required when `ZOTERO_LOCAL=true`)

When required keys are missing, CiteLoom provides clear error messages indicating which environment variable is needed and how to configure it.