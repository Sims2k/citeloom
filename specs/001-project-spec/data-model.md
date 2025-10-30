# Data Model — CiteLoom (Conceptual)

**Feature**: 001-project-spec  
**Date**: 2025-10-30

## Entities

### Project
- id (string, e.g., "citeloom/clean-arch")
- collection (string, e.g., "proj-citeloom-clean-arch")
- embeddingModel (string)
- hybridEnabled (bool)

### SourceDocument
- docId (string)
- projectId (string)
- path (string)
- doi (string | null)
- url (string | null)
- title (string | null)

### Chunk
- id (string)
- docId (string)
- projectId (string)
- text (string)
- pageSpan ([int,int] | null)
- sectionHeading (string | null)
- sectionPath (string[])
- chunkIndex (int)

### CitationMeta
- citekey (string | null)
- authors (string[])
- year (int | null)
- doi (string | null)
- url (string | null)
- tags (string[])
- collections (string[])

## Relationships
- Project 1..* SourceDocument
- SourceDocument 1..* Chunk
- Chunk 0..1 CitationMeta (applied during enrichment)

## Constraints
- Project collection name unique per project
- Embedding model consistent per project; writes blocked on mismatch
- Project filter required for query (prevent bleed)

## Derived Data
- embedModel persisted with each chunk payload
- sectionPath used for breadcrumb rendering and filtering
