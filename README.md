# CiteLoom
Weave long-form sources into small, citable context for your AI work.

## Intro

Short description and goals for CiteLoom will go here.

- Sources: ingest long-form PDFs and documents
- Chunking: heading-aware hybrid chunks for retrieval
- Citations: enrich chunks with Zotero CSL-JSON metadata
- Projects: per-project collections and isolation in Qdrant
- Tools: CLI-first; MCP integrations for editors/agents
- Architecture: Clean Architecture (domain/application/infrastructure)
- Flow: convert → chunk → enrich → embed → index → query

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

Command reference and examples will go here.

## Config

Document `citeloom.toml` fields and examples here.