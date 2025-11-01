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

Create a `.env` file in the project root with your API keys:

```bash
# Optional: OpenAI API key (for OpenAI embeddings, falls back to FastEmbed if not set)
OPENAI_API_KEY=sk-...

# Optional: Qdrant API key (required for Qdrant Cloud, optional for local)
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_URL=http://localhost:6333  # Optional: Override Qdrant URL

# Zotero Configuration (for citation metadata resolution)
# Option 1: Remote Zotero access (requires API key)
ZOTERO_LIBRARY_ID=your-library-id
ZOTERO_LIBRARY_TYPE=user  # or 'group'
ZOTERO_API_KEY=your-zotero-api-key
ZOTERO_LOCAL=false  # or omit (defaults to false)

# Option 2: Local Zotero access (requires Zotero running locally)
ZOTERO_LIBRARY_ID=1  # Typically '1' for user library
ZOTERO_LOCAL=true
```

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