# Dataset split and protocol evidence matrix

This matrix separates executable package support from protocols that are only
documented candidates. It records three independent facts: why a protocol is
published, how it partitions data, and whether the package uses it as a
technical canary. None is a model recommendation or a universal claim that the
split is scientifically best.

## Evidence basis

| Evidence basis | Meaning |
|---|---|
| `LITERATURE_REFERENCE` | Reproduces a named, influential publication setting within its exact dataset, artifact, task, and split scope. |
| `COMMUNITY_REFERENCE` | Preserves comparability with a named community benchmark artifact and protocol. |
| `PACKAGE_DEFINED` | Makes a package-owned protocol explicit without presenting it as a literature or community reference. |

The legacy `SplitProtocolRole` and `SplitEvidenceType` enums remain readable
for API compatibility. New registrations use `SplitEvidenceBasis`; in
particular, `CANARY` and `ROBUSTNESS` are not active evidence roles.
For compatibility, an active canary split's deprecated `.role` field is
`CANARY` when `is_canary=true`; `.basis` remains the only active evidence
source. A new-contract registration that explicitly supplies a different legacy
role is rejected rather than silently normalized.

`SplitEvidenceType` is likewise a deprecated reader, not evidence authority.
An active `PACKAGE_DEFINED` record reads as `PRODUCT_PROTOCOL`; active
`LITERATURE_REFERENCE` and `COMMUNITY_REFERENCE` records read as
`LITERATURE_REUSE`. A mismatched supplied legacy type is rejected, while the
typed `SplitEvidenceBasis` remains the source of truth.

One executable split can carry several evidence records from different bases.
Each record repeats the exact dataset snapshot, source artifact, transform,
task, and split identity so evidence cannot silently move to another scope.
The split strategy, held-out axis, leakage unit, grouping column, and evaluation
target are concrete semantics shared by those evidence records. `is_canary` is
separate package-test usage.

For generic `group-held-out` protocols, registry validation can establish typed,
canonical fields and agreement between the definition and executable capability;
it cannot establish that a free-text biological axis is scientifically valid.
That claim remains bounded by the cited evidence and by post-split leakage audit.

## Current matrix

| Dataset snapshot | Artifact scope | Task | Protocol | Status | Evidence basis | Split semantics | Package usage | Fit scope and leakage caveat |
|---|---|---|---|---|---|---|---|---|
| `tms-aorta@figshare-project-64982` | Figshare file `23872460`, SHA-256 `0fbf731…ced3c3`, transformed by `tms-aorta-csr-v1` | `cell-type-annotation-v1` | `animal-held-out-v1` | Executable | `PACKAGE_DEFINED`, [TMS Aorta contract](tms-aorta.md) | `group-held-out`; animal held out; mouse leakage unit; `donor_id` grouping; target: unseen animal | `is_canary=true` | Feature selection fits training rows only. Mouse groups do not cross partitions. This is neither a literature-reference split nor a performance reference. |
| Human pancreas benchmark v2 candidate | Zenodo record `3357167`, file `4282cdc9-55cd-4b4d-aa13-2ff780c742bf`, SHA-256 `038d0a61…bf06`, `CC-BY-4.0` | Cross-study cell-type annotation over shared alpha, beta, delta, and gamma labels | `pancreas-four-study-lodo-reference-v1` | Fetch/cache/inspection available; not registered as a canonical dataset | `LITERATURE_REFERENCE`, Abdelaal, Michielsen *et al.* (2019) | `leave-one-study-out`; study held out; study leakage unit; `study_id` grouping; target: unseen study | exact raw ZIP inspection only | Four whole-study holdouts reproduce the paper. Actual whole-cohort and four-label held-out-test metadata are verified; this is not presented as a modern leakage-safe recommendation. |

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

print(capability.basis, capability.strategy, capability.held_out_axis)
print(capability.is_canary, capability.evaluation_target)
for evidence in capability.evidence:
    print(evidence.basis, evidence.citations, evidence.leakage_caveat)
```

The pancreas row intentionally remains outside `load_dataset()` and capability
queries until a canonical materialization and executable dataset registration
are defined. Its archive rights, bytes, and source CSV schema are now verified.

## Artifact-lineage trust boundary

Executable materialization requires an `ArtifactLineageReceipt`. The public
loader reopens the derived and parent manifests, streams and hashes their cached
bytes, and checks the exact ordered parent tuple and transform protocol declared
by the dataset registration. Supplying only an `ArtifactReceipt`, adding an
unrelated parent, or forging an in-memory parent identity is rejected before the
dataset adapter runs.

Adapters receive a `VerifiedArtifactInput`, not a raw cache path. Every eager or
lazy read captures bytes from a no-follow file handle, hashes that exact
capture, and returns it only when its size and SHA-256 still match the manifest.
A post-return cache mutation therefore raises `VerifiedArtifactChangedError`
instead of silently reaching a lazy materialization. The handle owns no
persistent copy or cleanup resource, and its source remains the canonical
caller-selected cache receipt.

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

Registry construction snapshots caller registrations, and its public
`registrations`, loader, and capability-query results are detached views. This
prevents ordinary same-process mutation of a returned public object from
changing later public reads. Direct mutation of private registry or index backing
objects remains outside this public API boundary; frozen dataclasses are not a
tamper-proof security boundary in Python.
