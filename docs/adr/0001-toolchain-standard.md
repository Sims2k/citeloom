# ADR 0001: Toolchain Standard (pyenv + uv + Ruff + Mypy)

Date: 2025-10-30

## Status
Accepted

## Context
We need a fast, reproducible Python toolchain aligned with the constitution. We standardize on Python 3.12.x, uv for env/deps, Ruff for formatting/linting, and Mypy for typing.

## Decision
- Python 3.12.x pinned via `.python-version`
- uv manages the virtualenv and lockfile (`uv.lock`)
- Ruff provides formatting (`ruff format`) and linting (`ruff check`)
- Mypy enforces type safety, strict in `src/domain`
- GitHub Actions CI runs ruff, mypy, pytest with coverage gate for domain (≥90%)

## Consequences
- Faster local/CI installs
- Consistent formatting and linting
- Clear quality bar enforced in CI
