# Tabula Muris Senis literature protocol evidence

## Scope

Tabula Muris Senis (TMS) is a family of release- and assay-specific artifacts,
not one interchangeable benchmark. It contains repeated tissues from the same
mouse, so a random-cell partition does not establish performance on new
animals. The primary paper describes 30 mice across six ages, with 110,824
FACS/Smart-seq2 and 245,389 droplet/10x processed cells.

The literature surveyed for this project does **not** establish a universal,
or TMS-Aorta-specific, recommended split. A protocol must therefore state its
evidence basis, concrete partition semantics, and scientific question rather
than inherit a generic `recommended` label.

## Evidence basis and protocol usage

| Evidence basis or usage | Current evidence | Intended interpretation |
|---|---|---|
| `LITERATURE_REFERENCE` | scArches maps a separate Tabula Muris query to a filtered TMS reference. | Reproduce a prominent cross-study reference-mapping setting; it is not an animal-held-out TMS split. |
| `COMMUNITY_REFERENCE` | OpenProblems Label Projection v1 includes a TMS Lung derivative. | Compare with a fixed community artifact; its TMS Lung partition is random-cell, not a leakage-safe group holdout. |
| `PACKAGE_DEFINED` | `animal-held-out-v1` separates TMS Aorta mice. | Its strategy is `group-held-out`, with animal held out through `donor_id`; it targets an unseen animal and is not literature-recommended. |
| Package usage: `is_canary=true` | The current TMS Aorta implementation. | Exercise artifact, preparation, split, audit, and evaluation contracts; it is not an evidence basis or scientific benchmark claim. |

These bases and package usage are not interchangeable. In particular, the scArches setting uses
a separate Tabula Muris query rather than a held-out TMS age slice, and the
OpenProblems TMS Lung artifact must not be substituted for TMS Aorta.

## Interpretation and metrics

The current TMS Aorta canary's `animal-held-out-v1` split remains a transparent
product protocol, as documented in [the TMS Aorta contract](tms-aorta.md). No
comparable published performance range was verified for the same Aorta artifact,
task, animal-held-out split, and metric. Results from random-cell TMS Lung,
other tissues, and full-atlas integration should not be pooled as an Aorta
animal-holdout baseline.

Before a literature setting becomes executable here, it needs its own immutable
artifact pin, task definition, split or reference/query declaration,
preparation fit scope, metrics, and tests preventing identity confusion with the
TMS Aorta canary.

The machine-readable TMS evidence and the documentation-only pancreas candidate
are summarized in the [split and protocol evidence matrix](split-protocol-evidence-matrix.md).

## Sources

- [Tabula Muris Senis primary paper](https://www.nature.com/articles/s41586-020-2496-1)
- [Official TMS repository](https://github.com/czbiohub-sf/tabula-muris-senis)
- [Official processed TMS data objects](https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728)
- [scArches](https://www.nature.com/articles/s41587-021-01001-7)
- [scArches reproducibility repository](https://github.com/theislab/scArches-reproducibility)
- [OpenProblems Label Projection v1](https://www.openproblems.bio/benchmarks/label_projection/v1.0.0/)
- [Symphony](https://www.nature.com/articles/s41467-021-25957-x)
