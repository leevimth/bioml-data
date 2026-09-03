# Publication-scoped metadata concordance

`compare_metadata_concordance()` compares a prepared canonical dataset against
explicit external metadata evidence. It reports the complete prepared dataset
and every partition actually present in the split receipt: train, validation,
and test. It does not create a validation partition when a future split contract
does not have one.

Every expectation is bound to one exact scope: dataset snapshot; raw
source-artifact SHA-256 and transform protocol; task and split protocol. Each
expectation retains its own human-verifiable citation as evidence provenance,
but citations do not define scientific compatibility. This prevents a whole-atlas or primary-paper
statistic from being presented as evidence for a smaller tissue, assay,
transform, or split artifact. The checker rejects scope substitution before it
compares a count.

Supported evidence precision is `EXACT`, `RANGE`, `APPROXIMATE`, `SET`, and
`NOT_REPORTED`. `NOT_REPORTED` produces an explicit non-passing unknown result;
the package never fills it from observed data. The report includes observed cell
and feature counts, studies, donors, split groups, labels, assays, tissues,
label distributions, and observations per group when those metrics are
requested.

The checker also rejects incomplete or duplicated partition assignment rows and
reports groups that occur in more than one partition. That overlap is evidence
for the separate leakage audit; metadata concordance does not label a split safe
or unsafe and makes no model-performance claim.

Fold identity is retained as an optional report scope for future leave-one-
entity-out receipts. BIO-33 owns fold construction and real Pancreas execution.

## TMS Aorta boundary

The pinned TMS Aorta source audit declares expectations of 906 cells, 22,966 features,
six label counts, and tissue `Aorta` for the exact FACS Aorta H5AD. These expectations are
scoped to `tms-aorta@figshare-project-64982`, source SHA-256
`0fbf731…ced3c3`, transform `tms-aorta-csr-v1`, and
`animal-held-out-v1`. They are not statistics for the Tabula Muris Senis atlas
or its primary paper. The source file has no explicit assay field, so canonical
assay evidence is `NOT_REPORTED`, rather than inferred from `method`. They are
contract-only declarations: this checkout has not verified them against a locally
materialized 906 × 22,966 artifact. Actual-artifact execution remains gated on
BIO-27/BIO-31 readiness.

See the [TMS Aorta artifact audit](tms-aorta-artifact-audit.md) for the
source-level observations and the [TMS Aorta contract](tms-aorta.md) for the
package-defined split semantics.
