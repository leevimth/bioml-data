# TMS Aorta dataset and protocol contract

## Scope and status

The Tabula Muris Senis Aorta integration is a fixture-scale technical canary for
the protocol system. The snapshot identity is
`tms-aorta@figshare-project-64982`, and the task is
`cell-type-annotation-v1` at the cell prediction unit.

The adapter consumes a sparse, processed interchange artifact with schema
`tms-aorta-csr-v1`. That artifact must be content-addressed and linked to its raw
parent through the same transform-protocol identity. CI constructs a small local
artifact with this schema, so tests never require the large public download.

The catalog's benchmark lifecycle remains `planned`: download support is now
pinned to Figshare article `12654728` v1, file `23872460`, with the official
44,547,302-byte size and MD5. The package also records a project-computed
SHA-256 whose bytes were independently checked against that official size and
MD5; it does not present the SHA-256 as published by Figshare. Resolving the
upstream H5AD is separate from adapting it into the package's canonical schema
and running the complete benchmark lifecycle. See [dataset downloads and local
cache](downloads.md) for the exact pin and reuse behavior, and the
[upstream artifact audit](tms-aorta-artifact-audit.md) for the observed H5AD
schema, lineage confidence, and rights boundary that constrain the future
transform.

## Split protocol

`animal-held-out-v1` is explicit and has no default selection.

| Field | Value |
|---|---|
| Role | `CANARY` |
| Evidence | `PRODUCT_PROTOCOL` |
| Held-out axis | animal |
| Leakage unit | mouse |
| Canonical grouping column | `donor_id` |
| Required columns | `cell_id`, `donor_id` |
| Requested group fractions | 80% train, 10% validation, 10% test |
| Allocation | stable seeded group ordering plus largest remainder |

This is a transparent package-defined smoke protocol. It is not a reused
literature split, a `REFERENCE` protocol, a recommended scientific split, or
evidence that animal holdout is universally preferable. Changing its fractions
or allocation behavior requires a new protocol version.

## Preparation lifecycle

The canary preparation protocol is `tms-aorta-canary-preparation@v1`.
Train-independent work applies fixed count-support QC, aligns the artifact's
ordered genes, and normalizes each cell to a target sum of 100. The split is then
assigned. Feature selection is fitted from training rows only and reapplied to
validation and test rows through a serializable fitted state.

The preparation receipt records the input artifact, protocol version, seed,
split assignment, fitted-state identity, and prepared output identity. Changing
validation or test membership without changing training membership does not
change the fitted state.

## Leakage audit

The post-assignment audit reports exact observation duplication and
cross-partition overlap for donor/animal, study, library/batch, assay, tissue,
and label metadata. Each axis records coverage; missing metadata is `UNKNOWN`,
not safe. Required leakage-unit overlap is `FAIL`, informative overlap is
`WARN`, and complete covered separation is `PASS`. Unsupported protocol support,
unassessed support, and observed overlap failure remain distinct outcomes.

## Evaluation

The smoke evaluation uses the product protocol
`tms-aorta-mouse-macro-f1-canary@v1`, equal-weight per-animal macro-F1, and a
deterministic group bootstrap. Its small fixed feature-threshold estimator exists
only to execute the plumbing. It is not a benchmark model, model recommendation,
leaderboard baseline, performance reference, or state-of-the-art claim.

## Reproducible outputs

Python and CLI both call `run_tms_aorta_canary` and emit the same frozen receipt.
It includes:

- dataset snapshot and artifact identity;
- explicit split protocol and seed;
- split-assignment and preparation-receipt identities;
- leakage-audit report identity and status;
- metric-protocol and evaluation-receipt identities;
- the smoke evaluation point estimate.

The fixture path is exercised by `tests/test_e2e.py` and `tests/test_cli.py`.
HTTP streaming, checksum mismatch, truncated response, and HTTP error behavior
are exercised through deterministic transport fakes in
`tests/test_http_artifacts.py`; no live network is used.
