# CiteLoom
Weave long-form sources into small, citable context for your AI work.

## Intro

Turn big, hard-to-skim documents into small, trustworthy snippets you can search, quote,
and reuse in your work. CiteLoom keeps the link to the original source so every answer
is easy to verify and simple to cite.

- Bring your PDFs and notes; we prepare them for search
- Split into clear, readable snippets with helpful context
- Attach citation details so you can reference with confidence
- Keep projects separate to avoid mixing unrelated material
- Use from the command line and your favorite AI tools
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

Command reference and examples will go here.

## Config

Document `citeloom.toml` fields and examples here.