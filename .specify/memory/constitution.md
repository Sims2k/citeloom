# citeloom Constitution
<!--
Sync Impact Report
- Version change: 1.2.0 → 1.3.0
- Modified principles/sections:
  - Tooling & Workflow → expanded with authoritative Toolchain Policy
  - Testing/Coverage policy → clarified (domain ≥90%, prefer 100%)
  - Observability → Pareto-minimal logging/tracing guidance; correlation ID per ingest run
  - Security posture → de-emphasized initially
  - CI/CD Gates → explicit mypy strict-domain enforcement and architecture import checks
- Added sections:
  - Toolchain & Execution Policy (authoritative)
  - Operating Procedure (humans & agents)
  - Branching Policy (trunk-based: main-only)
- Removed sections:
  - None
- Templates requiring updates:
  - .specify/templates/plan-template.md ✅ aligned (Constitution Check generic)
  - .specify/templates/spec-template.md ✅ no change needed
  - .specify/templates/tasks-template.md ✅ no change needed
  - README.md ✅ updated with Developer Quickstart
- Deferred TODOs:
  - TODO(RATIFICATION_DATE): Original adoption date unknown; set once confirmed
  - TODO(PERSISTENCE): Confirm DB/files/none and migration policy
  - (none for coverage/observability/security baseline)
-->

## Core Principles

### I. Clean Architecture Dependency Rule
All dependencies MUST point inward toward business rules. Inner layers (domain, application) MUST NOT depend on outer layers (infrastructure). Outer layers adapt to inner contracts.

Rationale: Preserves changeability and testability by isolating business logic from frameworks and I/O.

### II. Separation of Concerns (Domain, Application, Infrastructure)
- Domain: Entities, Value Objects, Domain Services, Domain Errors — pure, deterministic, no I/O.
- Application: Use cases orchestrate domain, define ports (ABCs/Protocols) and DTOs. No framework imports.
- Infrastructure: Adapters and frameworks implement ports, translate inbound/outbound data, and host delivery (CLI/HTTP/etc.).

Rationale: Explicit responsibilities avoid framework bleed and hidden coupling.

### III. Framework Independence
Frameworks and drivers MUST be kept at the edge. Domain and application MUST remain import-clean from framework code. Swapping a framework MUST NOT require changes to domain/application code.

Rationale: Minimizes lock‑in and enables incremental migrations.

### IV. Stable Boundaries via Ports and DTOs
Use small, explicit interfaces (ports) and typed request/response models at use case boundaries. Outbound dependencies (e.g., repositories, buses) are consumed via ports. Inbound adapters call use cases.

Rationale: Makes dependencies explicit, facilitates testing with doubles, and prevents stringly‑typed contracts.

### V. Tests as Architectural Feedback
- Unit test domain in isolation.
- Application tests use doubles for outbound ports.
- Infrastructure tests cover adapters and thin integrations.
- Add architecture tests to enforce dependency direction and structure.

Rationale: Tests verify both behavior and architecture fitness over time.

## Architecture & Boundaries (Three Layers)

```text
src/
  domain/          # Entities, Value Objects, Domain Services, Domain Errors
  application/     # Use cases (interactors), Ports (ABCs/Protocols), DTOs
  infrastructure/  # Adapters: controllers, presenters, gateways, frameworks/drivers
tests/
  architecture/    # fitness tests for structure + dependency direction
```

Domain (pure)
- Contains: Entities, Value Objects, Domain Services, Errors
- Rules: No I/O, no framework imports, deterministic logic only

Application (use cases)
- Contains: Interactors orchestrating domain; ports for outbound deps; request/response DTOs
- Rules: Depends only on domain; no framework imports; coordinates but does not perform I/O

Infrastructure (adapters + frameworks/drivers)
- Contains: Controllers (CLI/HTTP/etc.), presenters/view models, gateways/repositories, framework glue
- Rules: Translate external formats to internal DTOs and vice versa; implement ports; uphold dependency direction

## Tooling & Workflow

Language & Packaging
- Python: 3.12.x via pyenv (pinned in `.python-version`)
- Package/env: uv. Canonical commands: `uv venv`, `uv sync`, `uv add`, `uv lock`, `uv run <cmd>`

Linting, Types, Formatting
- Lint/Format: Ruff — `uvx ruff format . && uvx ruff check .`
- Types: mypy — `uv run mypy .` (strict in `src/domain`)
- Imports: stdlib → third‑party → local; no wildcard imports

Testing
- Framework: pytest
- Pillars:
  - Domain unit tests (pure)
  - Application tests with doubles for ports (no real I/O)
  - Infrastructure adapter tests (integration/smoke)
  - Architecture tests (structure + dependency direction)
- Coverage: Domain 100% preferred (≥90% minimum); overall target ≥80%

CI/CD Gates (defaults)
```bash
# Environment bootstrap
pyenv --version
pyenv install -s 3.12.8 && pyenv local 3.12.8
uv sync

# Quality gates
uvx ruff format .        # optional write in CI; checks still required
uvx ruff check .         # must pass
uv run mypy .            # must pass (strict in src/domain)
uv run mypy --strict src/domain  # enforce strict typing in domain package
uv run pytest -q         # must pass
# Coverage (domain ≥90%, prefer 100%; overall ≥80%)
uv run pytest -q --cov=src/domain --cov-report=term-missing --cov-fail-under=90
# Optionally enforce overall threshold when broader coverage in place:
# uv run pytest -q --cov=src --cov-report=term-missing --cov-fail-under=80
```

Observability (Pareto-Minimal)
- Goal: Minimal effort, maximal signal (Pareto principle).
- Logs: Structured logs in infrastructure; redact PII; include a correlation ID per ingest run.
- Tracing: Lightweight request/task correlation only (no heavy tracing until needed).
- Metrics: Basic counters/timers for critical paths if present; add more only when justified by an ADR.
- Environments: dev/stage/prod as needed; logging level tuned per env (e.g., DEBUG in dev, INFO in prod).

Operational Clarifications (to be decided by ADRs)
- Runtime entrypoints: CLI (primary). Future: HTTP API/workers/library via adapters as needed
- Data & state: TODO(PERSISTENCE) (DB/files/none) and migration policy
- Security & privacy: Initial posture: not a focus area. Avoid logging PII; use least-privilege by default. Formal authN/Z and secrets management to be introduced via ADR when requirements emerge.

## Governance

Amendments
- Changes to principles or governance REQUIRE an ADR under `docs/adr/NNN-title.md` with Context, Decision, Consequences, Alternatives.
- Minor clarifications may be PATCH releases; new principles or substantial guidance are MINOR; redefining/removing principles is MAJOR.

Reviews & Compliance
- All PRs MUST validate against: Ruff, mypy, pytest, and architecture tests.
- Architecture drift (e.g., inward dependency violations) MUST be fixed or explicitly justified via ADR before merge.

Versioning Policy
- Semantic versioning for this constitution: MAJOR.MINOR.PATCH per rules above.
- Ratification date remains the original adoption; Last Amended reflects the most recent change.

Branching Policy
- Trunk-based development: `main` is the single protected branch for releases.
- Short-lived feature branches permitted; merges must keep `main` green (gates above).

Toolchain & Execution Policy (Authoritative)
- Python version via pyenv 3.12.x — store `.python-version` in repo.
- All env/deps/commands via uv:
  - Create/sync venv + resolve: `uv sync` (or `uv venv && uv lock && uv sync`)
  - Add/remove deps: `uv add <pkg>`, `uv add --dev <pkg>`, `uv remove <pkg>`
  - Run: `uv run <cmd>`; single-shot tools via `uvx <tool>`
- Forbidden: `pip install`, manual venv activation, invoking tools outside `uv run/uvx`.
- pyproject edits: Do not hand-edit dependency tables; use uv commands. Hand edits allowed only for project metadata and tool configs (ruff, mypy, etc.).
- Virtualenv: project-local `.venv/` managed by uv (keep uncommitted).

Policy Enforcement Signals (CI)
- Fail if `pip install` appears in code/scripts (exclude docs): grep guard.
- Fail if `[project].dependencies` change without corresponding `uv.lock` change.
- Require `.python-version` and `uv.lock` to be present.

Operating Procedure (Humans & Agents)
1. Select Python: `pyenv install -s 3.12.x && pyenv local 3.12.x`
2. Sync env: `uv sync`
3. Add deps: `uv add <pkg>` / `uv add --dev <pkg>`
4. Run tasks: `uv run <cmd>` or `uvx <tool>`
5. Quality loop: `uvx ruff format . && uvx ruff check . && uv run mypy . && uv run pytest -q`
6. Commit: code + `pyproject.toml` + `uv.lock`
7. Never: manual dep edits, `pip install`, manual venv activation

**Version**: 1.3.0 | **Ratified**: TODO(RATIFICATION_DATE) | **Last Amended**: 2025-10-30
# [PROJECT_NAME] Constitution
<!-- Example: Spec Constitution, TaskFlow Constitution, etc. -->

## Core Principles

### [PRINCIPLE_1_NAME]
<!-- Example: I. Library-First -->
[PRINCIPLE_1_DESCRIPTION]
<!-- Example: Every feature starts as a standalone library; Libraries must be self-contained, independently testable, documented; Clear purpose required - no organizational-only libraries -->

### [PRINCIPLE_2_NAME]
<!-- Example: II. CLI Interface -->
[PRINCIPLE_2_DESCRIPTION]
<!-- Example: Every library exposes functionality via CLI; Text in/out protocol: stdin/args → stdout, errors → stderr; Support JSON + human-readable formats -->

### [PRINCIPLE_3_NAME]
<!-- Example: III. Test-First (NON-NEGOTIABLE) -->
[PRINCIPLE_3_DESCRIPTION]
<!-- Example: TDD mandatory: Tests written → User approved → Tests fail → Then implement; Red-Green-Refactor cycle strictly enforced -->

### [PRINCIPLE_4_NAME]
<!-- Example: IV. Integration Testing -->
[PRINCIPLE_4_DESCRIPTION]
<!-- Example: Focus areas requiring integration tests: New library contract tests, Contract changes, Inter-service communication, Shared schemas -->

### [PRINCIPLE_5_NAME]
<!-- Example: V. Observability, VI. Versioning & Breaking Changes, VII. Simplicity -->
[PRINCIPLE_5_DESCRIPTION]
<!-- Example: Text I/O ensures debuggability; Structured logging required; Or: MAJOR.MINOR.BUILD format; Or: Start simple, YAGNI principles -->

## [SECTION_2_NAME]
<!-- Example: Additional Constraints, Security Requirements, Performance Standards, etc. -->

[SECTION_2_CONTENT]
<!-- Example: Technology stack requirements, compliance standards, deployment policies, etc. -->

## [SECTION_3_NAME]
<!-- Example: Development Workflow, Review Process, Quality Gates, etc. -->

[SECTION_3_CONTENT]
<!-- Example: Code review requirements, testing gates, deployment approval process, etc. -->

## Governance
<!-- Example: Constitution supersedes all other practices; Amendments require documentation, approval, migration plan -->

[GOVERNANCE_RULES]
<!-- Example: All PRs/reviews must verify compliance; Complexity must be justified; Use [GUIDANCE_FILE] for runtime development guidance -->

**Version**: [CONSTITUTION_VERSION] | **Ratified**: [RATIFICATION_DATE] | **Last Amended**: [LAST_AMENDED_DATE]
<!-- Example: Version: 2.1.1 | Ratified: 2025-06-13 | Last Amended: 2025-07-16 -->
