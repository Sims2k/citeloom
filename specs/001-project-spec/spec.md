# Feature Specification: CiteLoom naming and positioning

**Feature Branch**: `001-project-spec`  
**Created**: 2025-10-30  
**Status**: Draft  
**Input**: User description: "CiteLoom — Weave long-form sources into small, citable context for your AI work. Other name options provided. High-level description: a personal research and writing stack that converts large sources into small, citable chunks with clean metadata, organized per project, integrates with Obsidian and Zotero, and exposes MCP endpoints to editors."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Choose and publish project name and tagline (Priority: P1)

As a maintainer, I want a clear project name and one-sentence, non-technical tagline so new users can instantly grasp value.

**Why this priority**: Naming and positioning are prerequisites for discovery, docs, and CI metadata.

**Independent Test**: The repository exposes the chosen name and tagline in visible entry points (README title and tagline) without relying on any other feature.

**Acceptance Scenarios**:

1. **Given** the repo is open, **When** a user visits the README, **Then** they see the name "CiteLoom" and a concise tagline.
2. **Given** project metadata is reviewed, **When** checking primary docs, **Then** the name/tagline are consistent across surfaced docs.

---

### User Story 2 - Provide high-level description for prospective users (Priority: P2)

As a prospective user, I want a short, clear description of what the project does and how it fits my workflow so I can decide to try it.

**Why this priority**: Helps adoption and sets expectations; enables planning without deep technical docs.

**Independent Test**: The README contains a brief description explaining sources, chunking, citations, per-project organization, and tool integration.

**Acceptance Scenarios**:

1. **Given** the README intro, **When** reading the bullets, **Then** the user understands sources, chunking, citations, per-project organization, and tool/editor integration.

---

### User Story 3 - Alternate names recorded for future branding (Priority: P3)

As a maintainer, I want alternate name options recorded so that future branding changes are easy and deliberate.

**Why this priority**: Avoids re-litigating discovery and preserves optionality.

**Independent Test**: A section in the spec or docs lists vetted alternatives without impacting current name.

**Acceptance Scenarios**:

1. **Given** this spec, **When** reviewing the alternatives, **Then** options like ContextLoom, CiteWeave, VaultWeave, Ports and Pages, CiteVector, SourceLoom, ScholarChunk, IndexLoom are present.

#### Naming alternatives (for future consideration)

- ContextLoom (`context-loom`)
- CiteWeave (`cite-weave`)
- VaultWeave (`vault-weave`)
- Ports and Pages (`ports-and-pages`)
- CiteVector (`citevector`)
- SourceLoom (`source-loom`)
- ScholarChunk (`scholar-chunk`)
- IndexLoom (`index-loom`)

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right edge cases.
-->

- Consistency: Name/tagline must be identical across README, constitution header, and any templates referencing the project.
- Brevity: Tagline must remain under 120 characters for badge/marketplace compatibility.
- Accessibility: Avoid jargon or model names in tagline; keep language clear for non-technical audiences.

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: The project MUST present the name "CiteLoom" prominently in the primary documentation entry point.
- **FR-002**: The project MUST include a one-sentence tagline that explains value in non-technical terms.
- **FR-003**: The project MUST provide a short, high-level description covering sources, chunking, citations, per-project organization, and editor/tool integration.
- **FR-004**: The project MUST record alternate name options for future branding decisions.
- **FR-005**: The project MUST ensure the chosen name and tagline are consistent across surfaced documentation.
- **FR-006**: The official tagline MUST be: "Weave long-form sources into small, citable context for your AI work."

### Key Entities *(include if feature involves data)*

- **Project Identity**: Name, tagline, description, alternatives.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: README shows "CiteLoom" in the title and the exact tagline: "Weave long-form sources into small, citable context for your AI work." in the first screenful.
- **SC-002**: README includes a 4–8 bullet overview covering sources, chunking, citations, project organization, and tool/editor integration.
- **SC-003**: At least 80% of test readers correctly summarize the product from the README alone.
- **SC-004**: No discrepancies in name/tagline across README and constitution on a single pass review.

## Clarifications

### Session 2025-10-30

- Q: Select the final tagline text → A: "Weave long-form sources into small, citable context for your AI work."

---

## Appendix: Provided Naming and Description Content

### Top pick

**CiteLoom** — *Weave long-form sources into small, citable context for your AI work.*

**Suggested repo:** `citeloom`

### Other strong options

- **ContextLoom** (`context-loom`) — focus on turning sources into usable context.
- **CiteWeave** (`cite-weave`) — citations + weaving chunks together.
- **VaultWeave** (`vault-weave`) — nod to Obsidian vaults and per-project indices.
- **Port&Pages** (`ports-and-pages`) — playful nod to clean architecture (ports) + documents.
- **CiteVector** (`citevector`) — citations meet vector search.
- **SourceLoom** (`source-loom`) — emphasizes careful stitching of sources.
- **ScholarChunk** (`scholar-chunk`) — academic vibe; chunk-first thinking.
- **IndexLoom** (`index-loom`) — highlights building durable indices.

### What the project is about (high-level)

**CiteLoom** is a personal research & writing stack that turns big sources—books, papers, long PDFs, and web articles—into **small, reliable, citable building blocks** you can pull into your editor or chatbot on demand.

- **One place for your sources.** You keep using your Obsidian vault and Zotero. The project reads what you already have and mirrors it into tidy project indexes.
- **Built for long documents.** Instead of dumping an entire book into an AI prompt, CiteLoom breaks content into **meaningful chunks** (think section-aware snippets) so you only retrieve what matters.
- **Always citable.** Each chunk carries clean **bibliographic metadata** (author, year, title, DOI, tags, collection) so you can attribute sources and keep APA-style references consistent later.
- **Per-project collections.** Your work stays organized by project (e.g., *Clean Architecture for Agentic AI* vs. other topics), so retrieval stays on-topic and clutter-free.
- **Works with your tools.** It exposes MCP endpoints so **Cursor/Claude** can fetch relevant chunks while you write, plan, or refactor—without you leaving your editor.
- **Architecture-friendly.** The core ideas (domain rules in the middle; providers at the edges) keep the system evolvable as your models or tools change over time.
- **Simple day-to-day flow.** Add or update sources → the project converts and indexes them → in your editor/chatbot, ask for what you need → you get **focused, cited** snippets you can drop into sections and chapters.
