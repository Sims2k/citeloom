# Research — CiteLoom Implementation Decisions

**Feature**: 001-project-spec  
**Date**: 2025-10-30

## Decision: Docling for conversion/chunking
- Rationale: High-quality PDF/long-doc structure with HybridChunker; heading-aware chunks.
- Alternatives: GROBID (metadata only), unstructured.io (paid), pdftotext (loses structure).

## Decision: Qdrant as vector store
- Rationale: Local-first, lightweight, solid hybrid support, MCP ecosystem.
- Alternatives: Weaviate (heavier), Chroma (simpler, but hybrid less mature), Pinecone (SaaS).

## Decision: FastEmbed (all-MiniLM-L6-v2)
- Rationale: Fast, free, local; adequate quality for research notes.
- Alternatives: E5/MTEB models (slower/larger), OpenAI text-embedding-3-small (paid/API).

## Decision: Hybrid retrieval (dense + sparse)
- Rationale: Better recall/precision across phrasing; robust for academic text.
- Alternatives: Dense-only (fast but brittle), BM25-only (misses paraphrase).

## Decision: Zotero CSL-JSON (Better BibTeX)
- Rationale: Deterministic export; DOI-first matching; works offline.
- Alternatives: Live Zotero API (online), manual bib files (error-prone).

## Decision: CLI-first runtime + MCP integration
- Rationale: Simplicity, agent ergonomics, clean boundaries.
- Alternatives: Early HTTP API (more infra, no immediate need).

## Decision: Clean Architecture (3-layer)
- Rationale: Evolvability and testability; isolates frameworks.
- Alternatives: Flat modules (faster initially, but technical debt risk).

## Open Items (to be tracked in ADRs)
- Hybrid mode implementation detail (ingest vs query-time sparse).
- Embedding model migration policy.
- Citation rendering pipeline (Pandoc/CSL styles).
