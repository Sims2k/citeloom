# Quickstart — CiteLoom

## Prerequisites
- pyenv 3.12.x (pinned via .python-version)
- uv for environment/deps
- Qdrant (local Docker) optional for local store

## Setup
```bash
pyenv install -s 3.12.8 && pyenv local 3.12.8
uv sync
```

## Quality Loop
```bash
uvx ruff format .
uvx ruff check .
uv run mypy .
uv run pytest -q
```

## Configure
Create `citeloom.toml` with a project and paths (see plan.md Configuration section).

## Ingest
```bash
uv run citeloom ingest --project citeloom/clean-arch ./assets/raw/clean-arch.pdf
```

## Query
```bash
uv run citeloom query --project citeloom/clean-arch --q "entities vs value objects" --k 6
```

## Inspect
```bash
uv run citeloom inspect --project citeloom/clean-arch --sample 5
```

## Troubleshooting
- Ensure Qdrant is running and URL matches in `citeloom.toml`.
- Verify `references/<project>.json` exists or run `sync-zotero`.
