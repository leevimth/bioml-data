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
entity-out receipts. The current Pancreas check directly verifies whole-cohort
and held-out four-label test metadata from its exact Zenodo archive; it does
not derive the paper's unreported train or fold-feature metadata.

## TMS Aorta boundary

The pinned TMS Aorta source audit declares expectations of 906 cells, 22,966 features,
six label counts, and tissue `Aorta` for the exact FACS Aorta H5AD. These expectations are
scoped to `tms-aorta@figshare-project-64982`, source SHA-256
`0fbf731…ced3c3`, transform `tms-aorta-csr-v1`, and
`animal-held-out-v1`. They are not statistics for the Tabula Muris Senis atlas
or its primary paper. The source file has no explicit assay field, so canonical
assay evidence is `NOT_REPORTED`, rather than inferred from `method`. They are
not primary-paper statistics.

On 2026-09-04, implementation commit
`67cb61dfafb739fa85504b6bf27eee52eb617d0f` reproduced the exact official
source SHA-256 `0fbf731…ced3c3`, canonical `tms-aorta-csr-v1` artifact SHA-256
`680a5ef…bf56b3`, and 906 × 22,966 shape. With
`animal-held-out-v1` at seed 17, the realized train/validation/test partitions
contained 692/182/32 cells across 11/2/1 mice with no mouse shared between
partitions. The path-sanitized whole- and partition-level observations and
comparison statuses are recorded in
[`evidence/tms-aorta-real-metadata-v1.json`](evidence/tms-aorta-real-metadata-v1.json).

That execution record does not make the dataset supported. BIO-31 readiness,
the file-level rights and redistribution boundary, and publication-reported
partition values remain unresolved. Because neither the Figshare record nor the
publication reports this package-defined seed-17 partition, every partition
comparison is explicitly `NOT_REPORTED`, not a publication match.

The live check is opt-in so ordinary CI never downloads the artifact:

```bash
BIOML_RUN_LIVE_TMS=1 \
BIOML_TMS_DATA_DIR=.cache/bioml-data \
uv run pytest tests/test_tms_aorta_live_metadata.py
```

The selected content-addressed cache is verified and reused on later runs.

See the [TMS Aorta artifact audit](tms-aorta-artifact-audit.md) for the
source-level observations and the [TMS Aorta contract](tms-aorta.md) for the
package-defined split semantics.
