# BIO-32 v7 receipt root boundary evidence

Worktree: `/private/tmp/bioml-bio32`  
Branch: `codex/bio-32-preparation-execution-receipts`

## Security scenarios

| Scenario | Invocation | Binary observable | Result |
| --- | --- | --- | --- |
| Exact root boundary | `.venv/bin/python -m pytest tests/test_preparation_execution_enum_security.py -q` | A `PreparationExecutionReceipt` subclass is rejected by validation, identity rendering, and `to_json()` with field `preparation_execution_receipt`. | `9 passed in 0.27s` |
| Hostile root parsing | same invocation | A string, `None`, and decoded mapping object are rejected before any receipt-field access with the same typed field. | `9 passed in 0.27s` |
| Closed enum boundary | same invocation | Rehashed enum-coercible strings are rejected by public validation and JSON rendering. | `9 passed in 0.27s` |
| Existing execution lineage regression | `.venv/bin/python -m pytest tests/test_preparation_execution*.py tests/test_preparation*.py -q` | Execution receipt validation, replay, registered-contract, hostile tuple, and fitted-state tests stay green. | `122 passed in 0.42s` |

## Architecture and quality gates

| Check | Invocation | Binary observable | Result |
| --- | --- | --- | --- |
| Shared low-level contracts | `rg -n "_preparation_execution_models.*ExpressionInput|isinstance\\(" src/bioml_data/_preparation*.py` | No reverse import from core preparation models to execution models and no `isinstance` public-boundary checks in the preparation-execution modules. | no matches |
| Format and lint | `.venv/bin/ruff format --check . && .venv/bin/ruff check .` | Repository formatter and lint complete successfully. | `164 files already formatted`; `All checks passed!` |
| Static types | `.venv/bin/basedpyright` | No diagnostics. | `0 errors, 0 warnings, 0 notes` |
| No-excuse and size | `check-no-excuse-rules.py` over each changed Python module, plus `wc -l` | No exceptions; changed production modules are each at most 250 physical lines. | `no violations in 8 file(s)`; largest production module `233` lines |
| Whole suite including notebook | `.venv/bin/python -m pytest -q` | All local executable tests pass; the sole skip requires an opt-in live remote artifact. | `412 passed, 1 skipped in 4.05s` |
| Diff hygiene | `git diff --check` | No whitespace errors. | exit 0 |

The original focused root test was red before this change: a subclass passed and string/`None`/object roots raised raw `AttributeError`. The passing scenarios above are the captured green result after exact parsing was added.
