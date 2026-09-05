# Human pancreas cross-study annotation evidence

## Scope and candidate artifact

The proposed first pancreas artifact is a cross-study cell-type annotation
reference, not a generic pancreas benchmark or an integration benchmark. Its
historical anchor is the comparison by Abdelaal and Michielsen *et al.*
([Genome Biology, 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6734286/)).

The acquisition source is benchmark dataset v2 at Zenodo DOI
[`10.5281/zenodo.3357167`](https://zenodo.org/records/3357167), whose archive is
named `scRNAseq_Benchmark_datasets.zip`. This is a pinned inspection source,
not yet a supported `load_dataset()` artifact.

## Literature-reference protocol

`pancreas-four-study-lodo-reference-v1` is the candidate literature-reference
identity. It reproduces the reported four-study leave-one-dataset-out design:

- each of Baron Human, Muraro, Segerstolpe, and Xin is held out once;
- the remaining three whole cohorts form the reference/training data;
- shared labels are alpha, beta, delta, and gamma; and
- reported outcomes are per-class F1, median per-class F1, and unclassified
  rate. Accuracy may be recorded as a secondary metric.

The source reported both raw and MNN-aligned conditions. It did not document an
independent validation split, a seed schedule, or clearly nested train-only
feature fitting. Consequently this protocol is a `LITERATURE_REFERENCE`: it
records historical comparability, not a claim of modern leakage-safe
preprocessing or universal generalization.

## Publication metadata boundary

Abdelaal *et al.* report whole-cohort counts for the four source studies. The
package records these values in
`bioml_data.datasets.pancreas.PANCREAS_LODO_COHORT_METADATA`:

| Cohort | Cells | Genes | Distinct labels |
| --- | ---: | ---: | ---: |
| Baron Human | 8,569 | 17,499 | 14 |
| Muraro | 2,122 | 18,915 | 9 |
| Segerstolpe | 2,133 | 22,757 | 13 |
| Xin | 1,449 | 33,889 | 4 |

These are whole-cohort observations, not post-harmonization fold statistics.
The four-label benchmark subset is smaller and is reported separately in
Supplementary Table S2:

| Held-out cohort | alpha | beta | delta | gamma | subset cells |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baron Human | 2,326 | 2,525 | 601 | 255 | 5,707 |
| Muraro | 812 | 448 | 193 | 101 | 1,554 |
| Segerstolpe | 872 | 263 | 110 | 195 | 1,440 |
| Xin | 855 | 466 | 46 | 82 | 1,449 |

For each fold, the held-out test sample total and four-label counts are
directly reported by S2. The current expectation model has no evidence-origin
field, so train values—even though they can be arithmetically summed from the
three reported component rows—remain `NOT_REPORTED` rather than being
overstated as direct paper claims. Fold feature dimensions and validation
metadata are also `NOT_REPORTED`; no validation partition is part of the
paper's protocol.

Donor-held-out evaluation, where adequate donor metadata can be verified, would
be a separate package-defined protocol with a different target of
generalization. The OpenProblems label-projection pancreas artifact is likewise
a separate community task with its own labels and upstream preparation; it must
not be treated as a replacement for this four-cohort reference.

## Verified archive boundary

The official [Zenodo record API](https://zenodo.org/api/records/3357167) reports
open access and `cc-by-4.0`; the prior claim that its redistribution license was
unresolved was incorrect. The package still uses a fetch-only local cache and
does not host or mirror the 3.67 GB archive.

On 2026-09-04, the record API and downloaded bytes were verified as follows:

| Field | Verified value |
| --- | --- |
| Zenodo record / file ID | `3357167` / `4282cdc9-55cd-4b4d-aa13-2ff780c742bf` |
| archive / URL | `scRNAseq_Benchmark_datasets.zip` / official API content URL |
| byte size | 3,671,466,589 |
| provider MD5 | `b799a660b8bcaf5f3580a9b6f9372e5b` |
| local SHA-256 | `038d0a61ed3891c3d5f4ebd1dab5956465223e38b89859e1bf4792a9aeffbf06` |
| record license | `CC-BY-4.0` |

The ZIP integrity test completed with no errors. The package inspection path
reads, without extraction, the four `Intra-dataset/Pancreatic_data/<study>/`
member pairs: `Labels.csv` and `Filtered_*_HumanPancreas_data.csv`. Label rows
give whole-cohort cell and label counts; the matrix CSV header gives the whole
cohort feature dimension.

For the paper's four leave-one-study-out test cohorts, the selection rule is
the exact four labels `alpha`, `beta`, `delta`, and `gamma`; the Muraro archive
spells the last label `pp`, which the inspection normalizes to `gamma`. The
sum of those four observed label counts is the directly reported S2 held-out
test-cell count. This does not infer a train set: the paper does not report
train partition metadata or fold feature dimensions, so those remain
`NOT_REPORTED`.

The opt-in real-data check first imports already downloaded exact bytes into a
caller-selected content-addressed cache, then compares every whole cohort and
four-label held-out test cohort with the package's publication metadata:

```bash
BIOML_RUN_LIVE_PANCREAS=1 \
BIOML_PANCREAS_DATA_DIR=.cache/bioml-data \
BIOML_PANCREAS_ARCHIVE=/path/to/scRNAseq_Benchmark_datasets.zip \
uv run pytest tests/test_pancreas_live_metadata.py
```

The checked result is recorded in
[`evidence/pancreas-zenodo-3357167-metadata-v1.json`](evidence/pancreas-zenodo-3357167-metadata-v1.json).
A future supported snapshot still needs a canonical materialization and an
explicit decision about the benchmark's historical preprocessing—not a new
rights or source-byte investigation.

## Sources

- [Abdelaal, Michielsen *et al.* (2019)](https://link.springer.com/article/10.1186/s13059-019-1795-z)
- [Primary supplementary table source](https://repository.tudelft.nl/file/File_830444e0-e6b6-49ed-9c72-bf5e1c2bfcb4?preview=1)
- [Paper supplementary table](https://academic.oup.com/view-large/531233769)
- [Benchmark dataset v2 on Zenodo](https://zenodo.org/records/3357167)
- [Earlier benchmark dataset record](https://zenodo.org/records/2877646)
- [OpenProblems Label Projection v1](https://www.openproblems.bio/benchmarks/label_projection/v1.0.0/)
- [Zenodo terms](https://about.zenodo.org/terms/)
