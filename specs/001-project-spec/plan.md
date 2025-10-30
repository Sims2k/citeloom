# citeloom — Technical Implementation Plan (Python, Docling, Qdrant, Obsidian/Zotero, MCP)

This plan turns your Constitution into an actionable build: a Python 3.12 project that converts/segments long sources with Docling, indexes project-scoped chunks in Qdrant, and surfaces citable retrieval via MCP for Cursor/Claude and Obsidian.

## Summary

CiteLoom will ingest long-form sources, chunk them into citable snippets enriched with Zotero metadata, embed and store them in Qdrant per project, and expose retrieval via a CLI and MCP tools. Three-layer architecture ensures evolvability and testability.

## Technical Context

**Language/Version**: Python 3.12.x (pyenv pinned)  
**Primary Dependencies**: Docling, Qdrant client, FastEmbed (sentence-transformers/all-MiniLM-L6-v2), optional OpenAI embeddings, pytest, mypy, ruff  
**Storage**: Qdrant (local Docker or remote)  
**Testing**: pytest; coverage gates per constitution (domain ≥90%, prefer 100%)  
**Target Platform**: Developer workstation; MCP-enabled editors; optional server for Qdrant  
**Project Type**: single project (src/ with domain/application/infrastructure)  
**Performance Goals**: Ingest PDF ≤ 2 min; query top-6 in ≤ 1s on local Qdrant  
**Constraints**: CLI-first runtime; strict inward dependencies; uv-only toolchain; trunk-based main  
**Scale/Scope**: Per-project collections; thousands of chunks per project; multiple projects supported

## Constitution Check

- Toolchain policy: pyenv 3.12.x + uv-only commands — COMPLIANT  
- Lint/Type/Test gates: ruff, mypy, pytest with coverage — COMPLIANT  
- Architecture: 3 layers (domain/application/infrastructure), inward deps — COMPLIANT  
- Entry points: CLI primary — COMPLIANT  
- Branching: trunk-based (main) — COMPLIANT  
- Observability: Pareto-minimal logs/tracing — COMPLIANT  
- Security initial posture: low focus; avoid PII — COMPLIANT

## Project Structure

### Documentation (this feature)

```text
specs/001-project-spec/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
```

### Source Code (repository root)

```text
src/
  domain/
    models/
    services/
    policy/
    types.py
  application/
    ports/
    use_cases/
    dto/
  infrastructure/
    adapters/
      docling_converter.py
      docling_chunker.py
      zotero_metadata.py
      qdrant_index.py
      fastembed_embeddings.py
      openai_embeddings.py
    cli/
      main.py
      commands/
    mcp/
      citeloom_mcp.py

tests/
  unit/
  integration/
  architecture/
```

**Structure Decision**: Single project with clean architecture layers; CLI-first interface; tests by type.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Hybrid retrieval | Better accuracy and robustness | Dense-only performs poorly on some queries |

## Key Application Ports & DTOs (contracts)

- TextConverterPort → DoclingConverterAdapter  
- ChunkerPort → DoclingHybridChunkerAdapter  
- MetadataResolverPort → ZoteroCslJsonResolver  
- EmbeddingPort → FastEmbedAdapter (default), OpenAIEmbeddingsAdapter (optional)  
- VectorIndexPort → QdrantIndexAdapter

DTO examples: ConversionResult, Chunk, CitationMeta, StoreItem, SearchResult; request DTOs for Ingest/Query.

## Policies (domain)

- ChunkingPolicy: max_tokens=450, overlap=60, heading_context=2, tokenizer aligned to embedding  
- RetrievalPolicy: top_k=6, hybrid=True, project_filter_required=True

## Adapters (infrastructure)

- Docling converter/chunker; Zotero CSL-JSON resolver; FastEmbed/OpenAI embeddings; Qdrant index with per-project collections and model_id guard.

## End-to-End Ingest Flow

Select project → resolve metadata (CSL-JSON) → convert (Docling) → chunk (Hybrid) → enrich (Zotero) → embed (FastEmbed) → upsert (Qdrant) → log stats → audit JSONL.

## Retrieval Flow (via MCP)

Use qdrant MCP (or wrapper) to perform semantic/hybrid queries with project filter; return chunk text with citation payload.

## CLI Commands

- citeloom ingest/reindex/query/inspect/sync-zotero/validate (run via uv run)

## Configuration (TOML)

Include per-project collection, references JSON path, embedding model, hybrid flag, Qdrant URL, chunking defaults, paths.

## MCP Setup (Cursor)

mcp.json entries for qdrant/docling/obsidian/zotero with sample env.

## Testing Strategy

Domain unit tests (≥90%, prefer 100%), application with doubles, integration adapter smokes, architecture tests, golden chunk tests.

## CI/CD Gates (GitHub Actions)

pyenv 3.12 + uv sync; ruff format/check; mypy; pytest with coverage (domain ≥90%); policy guards for uv.lock and no pip install.

## Observability (Pareto-minimal)

Structured logs in adapters; correlation id per ingest; optional counters/timers.

## Security & Privacy (initial)

Avoid PII logging; secrets in env; local-first; TLS/API key when remote Qdrant.

## Risks & Mitigations

Metadata drift (BBT auto-export); embedding/tokenizer mismatch (persist model, validate); project bleed (filters/collections).

## Roadmap & ADRs

ADR for hybrid retrieval, embeddings selection, citation rendering, optional HTTP adapter, optional summarization.

## Acceptance Criteria (measurable)

- Ingest produces chunks with metadata for ≥95% of pages on two PDFs  
- Query returns ≤6 chunks, ≤700 tokens, with APA-ready metadata  
- Domain tests ≥90% coverage; import-direction tests pass  
- Qdrant shows correct embed_model; data project-scoped  
- Obsidian flow inserts two citations and one chunk from Cursor

## Developer Quickstart

```bash
pyenv install -s 3.12.8 && pyenv local 3.12.8
uv sync
uvx ruff format . && uvx ruff check .
uv run mypy .
uv run pytest -q
uv run citeloom ingest --project citeloom/clean-arch ./assets/raw/clean-arch.pdf
uv run citeloom query --project citeloom/clean-arch --q "aggregates vs entities" --k 6
```
