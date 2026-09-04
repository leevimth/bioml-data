# bioml-data

> Reproducible data protocols for trustworthy biological machine learning.

North-star target: turn public biological datasets into reproducible in-silico
ML experiments.

`bioml-data` is intended to become an open-source protocol layer for describing
and executing the dataset-specific decisions between public biological data and
a scientifically defensible machine-learning experiment. The target platform
spans versioned, auditable protocols for source resolution, dataset
understanding, preparation, task construction, biologically meaningful
splitting, split auditing, and evaluation.

The current implementation is deliberately narrower: a fixture-scale TMS Aorta
technical canary proving selected contracts for verified artifacts, canonical
sparse loading, split-aware preparation, animal-held-out assignment, leakage
auditing, and deterministic evaluation receipts.

```text
North-star protocol layer

Public biological data
GEO / CELLxGENE / UniProt / PDB / Hugging Face / Zenodo / ...
                         ↓
              source resolution + provenance
                         ↓
                    dataset audit
                         ↓
                     preparation
                         ↓
                  task construction
                         ↓
                  scientific split
                         ↓
                     split audit
                         ↓
                evaluation protocol
                         ↓
              reproducibility receipts
                         ↓
          reproducible in-silico experiment
```

## Why this project

Access to public biological data has improved. The difficult part is still
turning a source artifact into an experiment whose scientific choices are
explicit and reproducible. A researcher must often determine:

- which source artifact and version to use;
- what its metadata fields and biological units mean;
- which observations, sequences, or features belong in the task;
- which preparation is scientifically appropriate and which steps are fitted;
- what the prediction target and unit of generalization are;
- how train, validation, and test should be constructed and audited; and
- which evaluation protocol answers the intended scientific question.

Those decisions materially affect the result, but they commonly live in
dataset-specific scripts, notebooks, and undocumented conventions. This is the
gap `bioml-data` aims to own.

## Dataset != experiment

A public dataset describes what data exists. A `bioml-data` protocol describes
how a specific source version becomes an experiment:

```text
source artifact + version
        ↓
canonical/raw representation
        ↓
quality audit + inclusion rules
        ↓
preparation + task definition
        ↓
split + train-fitted transforms
        ↓
evaluation protocol
        ↓
reproducible experiment identity
```

Dataset and task remain separate concepts. One single-cell dataset may support
cell-type annotation, batch integration, disease classification, or
representation learning; a perturbation dataset may support response prediction,
gene-interaction prediction, or representation learning. Each task can require a
different preparation, split, and evaluation protocol.

The long-term research interface may therefore look like the following. This is
a direction, not a claim that every method shown is implemented today:

```python
dataset = bio.load("public-dataset")
dataset.audit()
prepared = dataset.prepare(protocol="standard")
task = prepared.task("cell_type_annotation")
train, validation, test = task.split(protocol="study-held-out")
results = task.evaluate(predictions)
```

## Relationship to the ecosystem

`bioml-data` complements existing infrastructure rather than replacing it:

- GEO, CELLxGENE, UniProt, PDB, and Zenodo are authoritative data sources.
- Hugging Face Datasets, bio-datasets, and cloud storage provide distribution,
  serialization, loading, and caching.
- Scanpy, scvi-tools, and other domain libraries provide established scientific
  algorithms and preprocessing primitives.
- OpenProblems, ProteinGym, and TDC provide task-specific benchmark ecosystems.
- The north-star `bioml-data` platform would connect those components through
  versioned scientific protocols, provenance, audits, and reproducibility
  receipts.

As provider integrations are added, data acquisition should remain
provider-specific and replaceable. The project should reuse provider download,
query, cache, revision, and streaming capabilities whenever practical, while
recording exactly what entered an experiment. Scientific preparation should not
need to change because the same dataset moves between storage providers.

Leakage-aware splitting remains important, but it is one part of experimental
validity alongside source provenance, dataset audit, preparation, task
definition, distribution-shift analysis, and evaluation.

## Initial direction

Single-cell data is the first major modality we plan to validate because it is
prominent in current biological ML research and exposes the product's hardest
requirements early: study and donor boundaries, batch effects, sparse matrices,
metadata quality, and preprocessing choices that must be fitted on training data
only.

Two initial use cases have different roles:

- **Cell-type annotation** is the technical canary for validating ingestion,
  schemas, animal-/group-aware splits, and evaluation.
- **Perturbation prediction** is the intended flagship use case for showing how
  a protocol turns public Perturb-seq data into an experiment with explicit
  controls, metadata harmonization, generalization-aware splits, and evaluation.

The goal is not to build another perturbation leaderboard. Existing benchmark
ecosystems can remain the evaluation backends when they already solve that part
well.

Protein sequence and other modalities remain candidates after the protocol
abstractions are stable. Modality priority is a research-backed product decision,
not a permanent restriction.

## Target / near-term scope

The following is the intended product scope, not a statement of what the
current technical canary supports:

- Provider-aware source resolution and provenance capture
- Canonical or modality-appropriate dataset representations
- Transparent dataset audits and inclusion rules
- Separate, versioned preparation and task protocols
- Biologically meaningful split protocols and post-split audits
- Evaluation protocols and uncertainty where appropriate
- Reproducibility receipts for source, preparation, split, and evaluation
- Python APIs, command-line workflows, and protocol documentation

## Non-goals for the first release

- Becoming a dataset hosting, file-transfer, streaming, or generic storage system
- Replacing Hugging Face Datasets, CELLxGENE, GEO, UniProt, PDB, or Zenodo
- Introducing a universal biological storage or serialization format
- Reimplementing established scientific algorithms without protocol-level value
- Processing raw sequencing reads such as FASTQ files
- Inventing opaque dataset quality or ML-readiness scores
- Building a new leaderboard or generic model-training framework
- Supporting every biological modality or task type at once
- Building single-cell visualization, dashboards, or enterprise deployment tools

## Status

The repository now includes a narrow, fixture-scale TMS Aorta technical canary.
It exercises content-addressed artifact ingest, canonical loading,
train-independent preparation, explicit animal-held-out splitting, train-only
fitting, leakage auditing, and evaluation without downloading the large public
dataset during CI.

TMS Aorta's `animal-held-out-v1` split has `PACKAGE_DEFINED` evidence basis and
separate `is_canary=true` package-test usage. It is not a literature reference,
recommended scientific split, model recommendation, or state-of-the-art claim.

## Quickstart

Reopen a previously verified content-addressed artifact and run the shared
Python pipeline:

```python
from pathlib import Path

import bioml_data as bio

data_dir = Path(".cache/bioml-data")
download = bio.download_dataset("tms-aorta", data_dir=data_dir)
prepared = bio.prepare_dataset(
    "tms-aorta",
    artifact=download.artifact,
    data_dir=data_dir,
)
dataset = bio.load_dataset("tms-aorta", artifact=prepared.lineage)
receipt = bio.run_tms_aorta_canary(
    prepared.artifact,
    split_protocol="animal-held-out-v1",
    seed=17,
)

assert receipt.artifact_identity == dataset.artifact.artifact_id
```

The shared runner follows the lifecycle
`load_dataset → train-independent prepare → explicit split → train-fitted apply
→ audit → evaluate`. The split protocol has no default: passing `None` raises
`MissingSplitProtocolError` before any fitted state is created.

Run the same pipeline from the command line:

```bash
RAW_SHA256="0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3"
uv run bioml-data \
  --artifact-manifest ".cache/bioml-data/sha256/${RAW_SHA256:0:2}/$RAW_SHA256/manifest.json" \
  --prepare-data-dir .cache/bioml-data \
  --split-protocol animal-held-out-v1 \
  --seed 17
```

Both surfaces emit the same deterministic identity chain: artifact, split
assignment, preparation receipt, leakage-audit report, metric protocol, and
evaluation receipt identities. The CLI writes the receipt as JSON.

Scientific materialization through `load_dataset()` reopens and hashes the
derived artifact and every required parent receipt, then requires their exact
registered parent tuple and transform protocol. The direct canary runner and
CLI are lower-level technical paths that assume their processed artifact
receipt came from a trusted producer. Receipt verification proves the byte
identities and declared lineage; it does not prove that arbitrary transform
code actually computed those bytes. That semantic transform boundary remains
part of the upstream-H5AD-to-canonical integration gap described below.

Current acquisition is separate from `run_tms_aorta_canary`. The dataset-aware
`download_dataset("tms-aorta", data_dir=...)` path owns the built-in TMS source
pin and content-addressed cache. The lower-level
`download_artifact(HttpArtifactDownload(...))` path is for callers that already
have an `ArtifactRequest`. Both yield a verified `ArtifactReceipt` (directly or
as `DatasetDownloadReceipt.artifact`), and neither automatically calls the
canary runner. `prepare_dataset()` explicitly converts that upstream receipt to
the canonical artifact accepted by `load_dataset()` and the canary.

The built-in TMS download is the upstream H5AD. The `tms-aorta-csr-v1`
transform selects integer-valued `raw.X`, preserves the raw artifact as its
parent, records `expression_input=raw.X` in its derivation parameters, leaves
absent assay/batch metadata unknown, and validates the resulting canonical
schema. Public preparation rejects receipts that do not match the complete
built-in pin. The pinned TMS SHA-256 is project-verified against the official
Figshare byte size and MD5, rather than supplied by an upstream SHA-256 manifest.
This narrow acquisition path supports the provenance contract; it is not a
commitment to build a generic transfer or caching framework. Future
provider-backed datasets should reuse their provider's acquisition capabilities
while `bioml-data` records the resulting source and artifact identity.

See [the TMS Aorta dataset and protocol contract](docs/tms-aorta.md) for the
canary's exact role, transform behavior, split behavior, preparation parameters,
and audit coverage. Use [protocol inspection](docs/protocol-inspection.md) to
read the exact declared split contract before acquiring or preparing data.

Literature evidence for [TMS protocol roles](docs/tms-literature-protocols.md)
and the candidate [human pancreas cross-study annotation
reference](docs/pancreas-cross-study-annotation.md) is documented separately.
The [dataset split and protocol evidence
matrix](docs/split-protocol-evidence-matrix.md) shows executable and candidate
settings without conflating candidate evidence with the implemented TMS Aorta
canary.

See [core product decisions](docs/core-decisions.md) for the current conceptual
model and [development](docs/development.md) for local setup and quality checks.
