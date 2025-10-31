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

## Requirements

- **Qdrant**: Vector database for storing and querying chunks
  - Local: Run `docker run -p 6333:6333 qdrant/qdrant` or use Docker Compose
  - Cloud: Use Qdrant Cloud with API key
  - Without Qdrant: In-memory fallback works for ingestion but data doesn't persist between commands

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

### Starting Qdrant (Local)

For local development, start Qdrant using Docker:

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Or with Docker Compose (if you have a `docker-compose.yml`):

```bash
docker-compose up -d qdrant
```

**Note**: Without Qdrant running, CiteLoom uses an in-memory fallback. Data ingested will not persist between command runs.
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