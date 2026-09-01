# Jupyter loading and EDA

Install the notebook dependencies alongside the package:

```console
uv sync --all-groups --all-extras
```

Open `examples/tms_aorta_eda.ipynb` and choose where downloaded data should be
cached before running it:

```console
export BIOML_DATA_DIR=/data/bioml-data
jupyter notebook examples/tms_aorta_eda.ipynb
```

The notebook calls `download_dataset("tms-aorta", data_dir=...)`. A valid
artifact already present in that directory is fully checked and reused without
an HTTP request. `load_anndata()` then reopens the receipt from its manifest and
rechecks the blob before passing it to AnnData for upstream EDA. In the same
cell, `prepare_dataset()` builds or reuses `tms-aorta-csr-v1`, and
`load_dataset()` opens the canonical count artifact. The notebook checks that
the upstream and canonical dimensions agree.

TMS Aorta's upstream observation fields remain unchanged. The loader also
provides two canonical aliases for downstream protocols:

| Upstream field | Canonical alias |
|---|---|
| `mouse.id` | `donor_id` |
| `cell_ontology_class` | `cell_type` |

The expression matrix is not densified. The notebook verifies that it remains
sparse, runs `scanpy.pp.calculate_qc_metrics`, reports donor and cell-type
counts, and saves a compact figure plus `summary.json`. Set
`BIOML_EDA_OUTPUT_DIR` to select the output location.

For a network-free run against an existing cache entry, set
`BIOML_ARTIFACT_MANIFEST` to its canonical `manifest.json` path. This is also
how the upstream EDA path can run without a download. CI sets
`BIOML_EDA_RAW_ONLY=1` for its small synthetic H5AD, whose bytes intentionally
cannot impersonate the exact pinned upstream artifact. Normal research use
leaves it unset, so the exact pinned receipt is prepared and materialized with
its verified parent lineage.

The public artifact is Tabula Muris Senis Data Objects, Figshare article
12654728, file 23872460, DOI
[10.6084/m9.figshare.12654728.v1](https://doi.org/10.6084/m9.figshare.12654728.v1).
