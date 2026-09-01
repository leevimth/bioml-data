# Dataset split and protocol evidence matrix

This matrix separates executable package support from protocols that are only
documented candidates. A role describes the evidence for a protocol; it is not
a model recommendation or a universal claim that the split is scientifically
best.

## Role vocabulary

| Role | Meaning |
|---|---|
| `LITERATURE_REFERENCE` | Reproduces a named, influential publication setting within its exact dataset, artifact, task, and split scope. |
| `COMMUNITY_REFERENCE` | Preserves comparability with a named community benchmark artifact and protocol. |
| `ROBUSTNESS` | Tests a package-declared generalization or independence condition; it is not automatically literature-recommended. |
| `CANARY` | Exercises package plumbing and reproducibility contracts; it is not a scientific benchmark claim. |

The older generic `REFERENCE` enum value remains available for API
compatibility. New evidence should use `LITERATURE_REFERENCE` or
`COMMUNITY_REFERENCE` so the basis of comparison is explicit.

One executable split can carry several evidence records. For example, a split
may be both a technical canary and a package-defined robustness check. Each
record repeats the exact dataset snapshot, source artifact, transform, task,
and split identity so evidence cannot silently move to another scope.

## Current matrix

| Dataset snapshot | Artifact scope | Task | Protocol | Status | Role evidence | Basis | Fit scope and leakage caveat |
|---|---|---|---|---|---|---|---|
| `tms-aorta@figshare-project-64982` | Figshare file `23872460`, SHA-256 `0fbf731…ced3c3`, transformed by `tms-aorta-csr-v1` | `cell-type-annotation-v1` | `animal-held-out-v1` | Executable canary | `CANARY`; `ROBUSTNESS` | Package-defined [TMS Aorta contract](tms-aorta.md) | Feature selection fits training rows only. Mouse groups do not cross partitions, but this is neither a literature-recommended Aorta split nor a performance reference. |
| Human pancreas benchmark v2 candidate | Zenodo record `3357167`, candidate archive `scRNAseq_Benchmark_datasets.zip`; exact local SHA-256 and upstream rights unresolved | Cross-study cell-type annotation over shared alpha, beta, delta, and gamma labels | `pancreas-four-study-lodo-reference-v1` | Documented candidate; not registered or executable | `LITERATURE_REFERENCE` | Abdelaal, Michielsen *et al.* (2019), summarized in the [pancreas evidence note](pancreas-cross-study-annotation.md) | Four whole-study holdouts reproduce the paper. Independent validation, seed schedule, and clearly nested train-only feature fitting were not documented, so this is historical comparability rather than a modern leakage-safe recommendation. |

## Inspection from Python

```python
import bioml_data as bio

dataset = bio.load_dataset("tms-aorta")
split = dataset.supported_splits[0]
capability = bio.query_split_capability(
    bio.SplitCapabilityQuery(
        dataset=dataset.snapshot,
        task=split.task,
        protocol=split.id,
    )
).require_supported()

for evidence in capability.evidence:
    print(evidence.role, evidence.citations, evidence.leakage_caveat)
```

The pancreas row intentionally remains documentation-only until artifact
rights, bytes, schema, and an executable registration are verified. It must not
appear in `load_dataset()` or capability queries before that gate closes.

## Artifact-lineage trust boundary

Executable materialization requires an `ArtifactLineageReceipt`. The public
loader reopens the derived and parent manifests, streams and hashes their cached
bytes, and checks the exact ordered parent tuple and transform protocol declared
by the dataset registration. Supplying only an `ArtifactReceipt`, adding an
unrelated parent, or forging an in-memory parent identity is rejected before the
dataset adapter runs.

The verified derived bytes are atomically published and reused under the source
cache's `.materialization-snapshots/sha256/` namespace before adapter dispatch.
This snapshot has the cache's lifecycle, so eager and lazy adapters read the
same bytes that were hashed even after `load_dataset()` returns. It is a
content-addressed cache entry, not an unmanaged temporary file.

This establishes content identity and a verifiable declared lineage edge. It
does not cryptographically prove that arbitrary transform code computed the
derived bytes from the parents. That stronger semantic guarantee requires a
package-owned, reproducible transform execution and receipt, which remains the
TMS raw-H5AD integration boundary rather than a claim made by this matrix.

Built-in `DatasetRegistration` source code is the package's trusted authority.
Registry validation prevents accidental disagreement among a registration,
capability, and evidence scope; it cannot defend against a malicious source-code
change that rewrites all three authorities together. The current TMS download
pin and registration both derive from the same typed identity constant, so the
download index is not misrepresented as an independent trust anchor.
