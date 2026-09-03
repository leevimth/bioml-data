# Human pancreas cross-study annotation evidence

## Scope and candidate artifact

The proposed first pancreas artifact is a cross-study cell-type annotation
reference, not a generic pancreas benchmark or an integration benchmark. Its
historical anchor is the comparison by Abdelaal and Michielsen *et al.*
([Genome Biology, 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6734286/)).

The acquisition candidate is the benchmark dataset v2 at Zenodo DOI
[`10.5281/zenodo.3357167`](https://zenodo.org/records/3357167), whose archive is
named `scRNAseq_Benchmark_datasets.zip`. This is a candidate snapshot, not yet
a supported package dataset.

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

Donor-held-out evaluation, where adequate donor metadata can be verified, would
be a separate package-defined protocol with a different target of
generalization. The OpenProblems label-projection pancreas artifact is likewise
a separate community task with its own labels and upstream preparation; it must
not be treated as a replacement for this four-cohort reference.

## Rights and implementation gate

Public access to the Zenodo record does not by itself clear redistribution. The
record/file license, access conditions, archive bytes, and compatibility with
upstream cohort terms must be verified before implementation or release.

Until that gate closes, this protocol is non-executable only because the rights,
exact archive bytes, and schema are unresolved—not because its historical split
is considered unusable. The appropriate product boundary is a provenance-aware
local acquisition/cache recipe, not hosting or mirroring the archive. A future
supported snapshot must record the exact record and file metadata, byte size,
published checksum where available, locally verified SHA-256, and the resolved
upstream terms.

## Sources

- [Abdelaal, Michielsen *et al.* (2019)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6734286/)
- [Benchmark dataset v2 on Zenodo](https://zenodo.org/records/3357167)
- [Earlier benchmark dataset record](https://zenodo.org/records/2877646)
- [OpenProblems Label Projection v1](https://www.openproblems.bio/benchmarks/label_projection/v1.0.0/)
- [Zenodo terms](https://about.zenodo.org/terms/)
