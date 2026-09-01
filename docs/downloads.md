# Dataset downloads and local cache

Dataset downloads use a caller-selected directory as an immutable,
content-addressed cache. For example:

```python
from pathlib import Path

import bioml_data as bio

download = bio.download_dataset(
    "tms-aorta",
    data_dir=Path("/data/bioml-data"),
)

print(download.outcome)  # downloaded or cache_hit
print(download.artifact.content_path)  # .../sha256/<prefix>/<sha256>/blob
print(download.provider.id)  # figshare
print(download.pin.file_id)  # provider-native file identity

prepared = bio.prepare_dataset(
    "tms-aorta",
    artifact=download.artifact,
    data_dir=Path("/data/bioml-data"),
)
dataset = bio.load_dataset("tms-aorta", artifact=prepared.lineage)
print(prepared.outcome)  # transformed or cache_hit
print(dataset.counts.shape)
```

Before opening an HTTP connection, the package derives the expected SHA-256
address and checks the complete cached artifact. It rejects symlinked path
components and rechecks the canonical directory layout, byte size, SHA-256,
manifest artifact identity, and manifest-to-blob consistency. A valid entry is
returned with `outcome == DatasetDownloadOutcome.CACHE_HIT`; no HTTP request is
made. A missing entry is downloaded once and atomically published with
`outcome == DatasetDownloadOutcome.DOWNLOADED`.

An occupied but invalid address raises `ArtifactCollisionError`. The package
does not silently overwrite or redownload corrupt data; this keeps provenance
failures visible to the researcher. Different `data_dir` values are independent
caches, while the same bytes retain the same artifact identity in each cache.

## TMS Aorta pin

`get_dataset_download_pin("tms-aorta")` exposes the exact implemented source:

| Field | Value |
|---|---|
| Figshare article | `12654728` |
| DOI | `10.6084/m9.figshare.12654728.v1` |
| Release | `v1` |
| File ID | `23872460` |
| Source URL | `https://ndownloader.figshare.com/files/23872460` |
| Filename | `tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad` |
| Byte size | `44,547,302` |
| Official MD5 | `4b1c150cf856a7406b3293ebdacd72c6` |
| Project-verified SHA-256 | `0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3` |
| Article license metadata | `MIT` |

Figshare publishes the byte size and MD5. The SHA-256 is not presented as an
official Figshare checksum: the project independently computed it from bytes
that matched the official size and MD5. This distinction is retained in
`Sha256Provenance.PROJECT_VERIFIED`.

Download support only resolves and verifies the upstream H5AD artifact.
`prepare_dataset()` is the explicit next boundary: it transforms integer-valued
`raw.X` into `tms-aorta-csr-v1`, records the raw parent in the derivation
receipt together with `expression_input=raw.X`, validates the canonical schema,
and reuses verified output in the same `data_dir`. It rejects locally forged or
alternative H5AD receipts that do not match the exact built-in pin. It does not
run split, audit, or evaluation stages.

The Figshare-native receipt retains its complete pin and provider descriptor.
The provider-neutral identity and extension contract are documented in
[`provider-adapters.md`](provider-adapters.md).

The [upstream artifact audit](tms-aorta-artifact-audit.md) records the verified
Figshare child-record lineage, real H5AD schema and cardinalities, split-relevant
dependencies, and the remaining redistribution-rights boundary.

For a researcher-facing verified load and compact Scanpy EDA workflow, see
[`notebook-eda.md`](notebook-eda.md) and `examples/tms_aorta_eda.ipynb`.
