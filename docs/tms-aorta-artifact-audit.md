# TMS Aorta upstream artifact audit

This audit fixes the exact upstream input that the future
`tms-aorta-csr-v1` transform may consume. It separates facts observed in
authoritative metadata or the downloaded bytes from lineage inferences and
open rights questions. The audit was run on 2026-09-01.

## Verified artifact identity

The Figshare project `64982` contains the child dataset article `12654728`.
That article describes itself as the official Tabula Muris Senis data release
and contains the following exact file:

| Field | Verified value |
|---|---|
| Project | `Tabula Muris Senis`, Figshare project `64982` |
| Child article | `Tabula Muris Senis Data Objects`, article `12654728` v1 |
| DOI | `10.6084/m9.figshare.12654728.v1` |
| File ID | `23872460` |
| File | `tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad` |
| Scope encoded by the file | FACS, processed, official annotations, Aorta |
| Bytes | `44,547,302` |
| Figshare-supplied and computed MD5 | `4b1c150cf856a7406b3293ebdacd72c6` |
| Project-verified SHA-256 | `0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3` |
| Article-level license displayed by Figshare | `MIT` |

The Figshare API exposes the license on the article record, not as a separate
file-level field. Therefore `MIT` in the current download pin means
**displayed article-record license metadata**. It must not be generalized into
a claim that every upstream raw source, annotation contribution, or alternative
TMS artifact has the same license.

The package's existing `download_dataset("tms-aorta", data_dir=...)` path
downloaded these bytes and returned artifact identity
`sha256:0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3`.
A second call returned `cache_hit` after integrity verification. No data is
mirrored or committed by this repository.

## Lineage status

### Verified

- The upstream TMS repository directs users to Figshare project `64982` for
  processed, Scanpy-ready data.
- Figshare project `64982` lists article `12654728` as a child article.
- Article `12654728` calls itself the official data release, and its file name
  identifies this object as the processed FACS Aorta artifact with official
  annotations.
- NCBI GEO identifies `GSE149590` as Tabula Muris Senis and exposes separate
  `tabula-muris-senis-droplet` and `tabula-muris-senis-facs` samples.

### Inferred, not directly asserted by the child record

The current source declaration relates this Figshare object to `GSE149590`.
The dataset name, modality, and official project documentation support that
dataset-level lineage. However, the Figshare child-article API response does
not itself name `GSE149590` or state a file-specific derivation chain from GEO
sample `GSM4505405` to file `23872460`. The precise processing steps and tool
versions between that GEO sample and this H5AD remain unverified.

### Unresolved rights boundary

The upstream repository says that data received from Chan Zuckerberg Biohub
have no restrictions unless identified at receipt, while the Figshare child
article displays MIT. These are compatible signals for use, but they do not
provide a field-by-field provenance or third-party annotation rights matrix.
Until that chain is documented, the safe product behavior is local acquisition
from Figshare with provenance receipts, not redistribution of the H5AD.

## Real H5AD schema audit

The audit loaded the content-addressed blob using `anndata.read_h5ad` without
densifying its matrices.

| Property | Observed value |
|---|---|
| Shape | 906 cells × 22,966 variables |
| `X` | CSR `float32`; processed non-integer values; 2,000,087 nonzeros |
| `raw.X` | present; CSR `float32`; integer-valued nonzeros; same shape |
| Observation index | unique |
| `cell` column | unique, but not equal to the observation index |
| `mouse.id` | 14 unique values; no missing values |
| `age` | `3m`, `18m`, `24m`; no missing values |
| `sex` | `female`, `male`; no missing values |
| `method` | one value, `facs` |
| `tissue` | one value, `Aorta` |
| `subtissue` | one value, `Heart` |
| `cell_ontology_class` | 6 labels; no missing values |
| `cell_ontology_id` | 5 categories including literal `"nan"` |
| Explicit assay column | absent |
| Explicit batch/library column | absent |

The complete observation columns are:

```text
FACS.selection, age, cell, cell_ontology_class, cell_ontology_id,
free_annotation, method, mouse.id, sex, subtissue, tissue, n_genes,
n_counts, louvain, leiden
```

The six target-label counts are:

| `cell_ontology_class` | Cells |
|---|---:|
| aortic endothelial cell | 467 |
| fibroblast of cardiac tissue | 215 |
| professional antigen presenting cell | 130 |
| fibrocyte | 44 |
| macrophage | 32 |
| epithelial cell | 18 |

`cell_ontology_id` is not a reliable replacement for the class label in this
artifact. The literal `"nan"` value occurs in 556 of 906 rows, and observed IDs
are not in one-to-one correspondence with `cell_ontology_class`. BIO-26 should
preserve the upstream field but must not invent missing ontology mappings.

## Split-relevant dependency audit

Every mouse maps to exactly one age, sex, method, tissue, and subtissue value.
Cell counts per mouse range from 19 to 128, and cell-type support varies sharply
by mouse. A split implementation must therefore report group and label coverage
rather than treating 14 mice as exchangeable equal-sized groups.

Age and sex are partially dependent:

| Age | Female cells | Male cells | Mice |
|---|---:|---:|---:|
| 3m | 87 | 279 | 6 |
| 18m | 159 | 157 | 4 |
| 24m | 0 | 224 | 4 |

All 24-month observations are male, so an age-held-out evaluation at 24 months
cannot separate age shift from sex composition. `FACS.selection` is also
perfectly aligned with age in this file: all 3-month rows contain literal
`"nan"`, while every 18- and 24-month row contains `Viable`.

This artifact cannot support assay-, batch-, tissue-, or subtissue-held-out
protocols: method, tissue, and subtissue are constant, and no explicit
batch/library column exists. Tokens embedded in cell identifiers are not a
documented batch field and must not be parsed into one without upstream
evidence.

## Contract handed to BIO-26

BIO-26 may rely on these verified conditions for this exact content identity:

- sparse `X` and sparse `raw.X` are present at 906 × 22,966;
- observation names and the `cell` column are each unique but distinct;
- `mouse.id` and `cell_ontology_class` are complete;
- age, sex, method, tissue, and subtissue are complete source metadata;
- `cell_ontology_id` contains unusable literal missing markers;
- assay and batch/library are absent and must remain unknown;
- no ontology repair, batch inference, or cross-artifact schema expansion is
  justified by this audit.

The transform still needs an explicit, versioned decision about whether its
expression input is processed `X` or integer-valued `raw.X`, plus a receipt that
records that choice. This audit does not silently choose between them.

## Authoritative references

- [Figshare article 12654728](https://api.figshare.com/v2/articles/12654728)
- [Figshare project 64982](https://api.figshare.com/v2/projects/64982)
- [TMS upstream repository](https://github.com/czbiohub-sf/tabula-muris-senis)
- [NCBI GEO GSE149590](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE149590)
