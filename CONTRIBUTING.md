# Contributing

## Setup

```bash
git clone https://github.com/<your-org>/next-mcp-odoo
cd next-mcp-odoo
uv sync --extra dev
```

## Running tests

```bash
# Unit tests (no server needed)
uv run python -m pytest tests/ -q

# Integration tests against Odoo 19+ with JSON-2
uv run python -m pytest tests/ -m json2 -v
```

## Environment for integration tests

```bash
cp .env.example .env
# Edit .env with your Odoo credentials
```

## Code style

```bash
uv run ruff check .
uv run ruff format .
```

## Pull requests

- One feature or fix per PR
- Add or update tests for your changes
- Update `CHANGELOG.md` under `[Unreleased]`
