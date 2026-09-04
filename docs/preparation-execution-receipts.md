# Preparation execution receipts

`PreparationExecutionReceipt` records the scientific context of a completed,
split-aware preparation without becoming a cache manifest, a notebook log, or a
model-training record. It is intentionally path-free and deterministic: two
calls with the same inputs emit the same canonical JSON and receipt identity.

```python
import bioml_data as bio

execution = bio.record_preparation_execution(bio.PreparationExecutionRequest(
    dataset=dataset,
    input_artifact=download.artifact,
    materialization=prepared_artifact,
    prepared=prepared_rows,
    assignment=split_receipt,
    protocol=preparation_protocol,
    runtime=bio.PreparationExecutionRuntime(
        toolkit_version=bio.__version__,
        dependencies=(
            bio.DependencyVersion(bio.RuntimeComponent.ANNDATA, "0.12.0"),
            bio.DependencyVersion(bio.RuntimeComponent.NUMPY, "2.0.0"),
        ),
    ),
    concordance=metadata_report,
))

bio.validate_preparation_execution_receipt(execution)
print(execution.to_json())
```

The receipt joins the following layers; none replaces the others.

| Layer | What it proves |
| --- | --- |
| `ArtifactReceipt` | Exact acquired input bytes and their immutable manifest. |
| `DatasetPreparationReceipt` | The canonical artifact, its exact input parent receipts, and whether materialization transformed or reused it. |
| `PreparedBenchmarkReceipt` | The split-bound, train-fitted preparation output and fitted-state identity. |
| `PreparationExecutionReceipt` | Dataset/task, canonical input-to-output chain, semantic preparation parameters, expression matrix, split/seed, bounded runtime versions, and optional metadata-concordance identity/status. |

The execution receipt validates that its supplied artifacts, split receipt,
preparation protocol, prepared-output identity, and optional concordance report
refer to the same dataset/task/protocol context. Its identity hashes every field
that it renders. It includes the transform's declared `expression_input`
(`raw.X` or `X`). It records deterministic canonical materialization as
`none` fit scope and the split-aware prepared output as `train_only` fit scope.

## Deliberate trust boundary

This is a record of already-produced receipts. It does not reopen files,
re-execute a transform, fit a model, or establish that arbitrary transform code
computed the canonical bytes. The artifact and materialization boundaries retain
that responsibility. `validate_preparation_execution_receipt()` detects changes
to the rendered execution record by recomputing its identity; it cannot prove
that a caller supplied authentic in-memory objects.

No standalone CLI command currently emits this receipt. The existing command
line canary may be invoked with an already-canonical artifact, while this record
requires the complete `DatasetPreparationReceipt` linking the raw input to that
canonical output. Creating a CLI receipt without that real parent would create a
false lineage claim. Use the Python API at the point where acquisition,
materialization, splitting, and preparation receipts are all available.

Runtime data is deliberately bounded to the toolkit version and named
single-cell dependencies (`anndata`, `numpy`, and `scipy`). The receipt never
records absolute paths, cache roots, environment variables, host/user identity,
timestamps, arbitrary command lines, secrets, or a full dependency freeze.
