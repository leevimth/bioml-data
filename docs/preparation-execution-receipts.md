# Preparation execution receipts

`PreparationExecutionReceipt` records the scientific context of a completed,
split-aware preparation without becoming a cache manifest, a notebook log, or a
model-training record. It is intentionally path-free and deterministic: two
calls with the same inputs emit the same canonical JSON and receipt identity.
The current public TMS flow in the README stops at `run_tms_aorta_canary()` and
does not expose every intermediate artifact, split, prepared-output, and
concordance receipt required here. It must not therefore be presented as a
runnable construction example. Import the API from
`bioml_data.preparation_execution` and call
`record_preparation_execution()` only at an integration point that already
holds those complete receipt objects; call
`validate_preparation_execution_receipt()` before consuming its JSON.

The receipt joins the following layers; none replaces the others.

| Layer | What it proves |
| --- | --- |
| `ArtifactReceipt` | Exact acquired input bytes and their immutable manifest. |
| `DatasetPreparationReceipt` | The canonical artifact, its exact input parent receipts, and whether materialization transformed or reused it. |
| `PreparedBenchmarkReceipt` | The split-bound, train-fitted preparation output, fitted-state identity, and full preparation-protocol semantic identity. |
| `PreparationExecutionReceipt` | Dataset/task, canonical input-to-output chain, semantic preparation parameters, expression matrix, split/seed, bounded runtime versions, and optional metadata-concordance identity/status. |

The execution receipt validates that its supplied artifacts, split receipt,
preparation protocol, prepared-output identity, and optional concordance report
refer to the same dataset/task/protocol context. Its identity hashes every field
that it renders. At factory time it deterministically replays preparation from
the supplied canonical in-memory dataset, protocol, and assignment; the supplied
`PreparedBenchmarkReceipt` must exactly match that replay, including fitted
state and output rows. It also requires the materialization manifest to equal
the canonical dataset's complete manifest, not merely its content ID. The
current preparation pipeline accepts only the transform's declared
`expression_input=raw.X`; it records deterministic canonical materialization as
`none` fit scope and the split-aware prepared output as `train_only` fit scope.
Before consuming a split receipt, it replays the named allocation against the
canonical split observations; a stale identity or a rehashed invented allocation
is rejected. Alignment semantics are directly inspectable as the exact immutable
feature-ID tuple in operational preparation order, its count, and its SHA-256
identity. The tuple is bounded at 50,000 IDs so this is a reproducibility
record, not a replacement data matrix.

## Deliberate trust boundary

The factory does not reopen raw files or establish that arbitrary transform code
computed canonical bytes. The artifact and materialization boundaries retain
that responsibility. It does replay the package's deterministic preparation
against the supplied canonical in-memory dataset, which prevents an arbitrary
prepared/fitted receipt from being joined into a new execution record. When an
optional concordance report is supplied, its comparisons and aggregate status
are recomputed from that same dataset and split using the report's declared
expectations. That catches altered observed values, counts, partitions, and
statuses. Publication expectations and citations remain caller-supplied evidence
unless a dataset-specific registry supplies an independent expectation source.
`validate_preparation_execution_receipt()` is deliberately narrower: it checks
the serialized record's structural fields and outer identity, but cannot replay
without a canonical dataset object or prove upstream artifact authenticity.

No standalone CLI command currently emits this receipt. The existing command
line canary may be invoked with an already-canonical artifact, while this record
requires the complete `DatasetPreparationReceipt` linking the raw input to that
canonical output. Creating a CLI receipt without that real parent would create a
false lineage claim. Use the Python API at the point where acquisition,
materialization, splitting, and preparation receipts are all available.

Runtime data is deliberately bounded to the toolkit version and named
single-cell dependencies (`anndata`, `numpy`, and `scipy`). The receipt never
automatically collects local paths, cache roots, environment variables,
host/user identity, timestamps, command lines, secrets, or a full dependency
freeze. Runtime values and serialized identifiers are explicitly parsed through
bounded allowlists/grammars; paths, URIs, control characters, environment-like,
and command-like forms are rejected, and rejected values are not echoed by the
typed receipt error. This is syntax validation, not a claim to
detect secrets embedded in arbitrary scientific labels. Semantic numeric
parameters must be finite before either receipt identity or JSON is rendered.
The same checks are replayed at every public identity, validation, and JSON
boundary, so frozen-object mutation followed by a forged hash cannot introduce
unsafe runtime metadata.

Preparation-protocol semantic identity is a fail-closed, canonical JSON hash
with an explicit `bioml-data/preparation-protocol-semantics` domain and `v1`
schema. It binds ordered feature IDs, QC, normalization, feature selection,
and the fixed `raw.X`/fit-scope contract into the prepared-output receipt. The
execution receipt records those matrix/scope values as separate fields too.
This is pre-release protocol work: older receipts are not accepted and must be
regenerated under this schema.
