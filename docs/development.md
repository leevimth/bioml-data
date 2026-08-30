# Development

The project uses Python 3.12 and `uv` for reproducible environments. Python 3.12
is new enough for strict typing while retaining broad compatibility with the
scientific Python ecosystem.

## Setup

```bash
uv sync --locked --all-groups
```

`uv` installs the Python version declared in `.python-version` when needed, so
the system Python does not need to match the project.

## Quality checks

Run the same checks used by CI:

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest
```

Formatting changes can be applied with:

```bash
uv run ruff format .
uv run ruff check --fix .
```

Tests follow Given/When/Then structure and should assert observable behavior.
Protocol transformations and splits must have deterministic regression tests
once those APIs are introduced.
