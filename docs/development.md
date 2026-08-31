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

## Internal package boundaries

Built-in datasets are implemented as vertical slices under
`src/bioml_data/datasets/<dataset>/`. A slice owns its immutable identity,
catalog definition, adapter, supported protocol declarations, dataset-specific
workflows, and any dataset-owned compatibility pin. `datasets/_registry.py` is
the static dispatch point; its generic registration contract does not contain
provider-shaped download metadata, and adding a dataset must not add
dataset-name conditionals to the public catalog.

The root `_dataset_downloads.py` module maintains only the current verified HTTP
compatibility index by exact dataset snapshot. It is not a future provider
adapter abstraction; provider-specific Hugging Face, CELLxGENE, and GEO adapters
remain out of scope.

Dataset and modality remain separate concepts. A future modality package owns
canonical schemas and transformations shared by several datasets, while a
dataset slice may reference more than one modality. Runtime plugin discovery is
not part of the current architecture.

Existing top-level private modules such as `_tms_aorta.py` and `_pipeline.py`
remain compatibility facades while implementations move into dataset-owned
packages. Public imports from `bioml_data` must remain stable during these
internal moves, and deterministic receipt identities must be regression-tested.
