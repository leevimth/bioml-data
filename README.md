# bioml-data

> Reproducible data protocols for trustworthy biological machine learning.

`bioml-data` is an early-stage, open-source toolkit for turning public
biological datasets into auditable, ML-ready benchmarks. The project focuses on
the parts that are easy to get subtly wrong: provenance, preprocessing,
leakage-aware splitting, and comparable evaluation.

## Why this project

Public biological datasets are often available but not reproducible as machine
learning benchmarks. Researchers still have to reconstruct download logic,
metadata joins, filtering choices, task definitions, split rules, and metrics.
Those choices can materially change a result, especially when biological
relatedness or experimental batches leak across train and test sets.

The intended workflow is:

```text
load → dataset audit → select task → task audit → prepare
     → split → train-fitted preprocessing → split audit → evaluate
```

The core artifact is therefore not a hosted copy of the raw data. It is a
versioned protocol that records how a source dataset became a benchmark.

## Initial direction

Single-cell data is the first major modality we plan to validate because it is
prominent in current biological ML research and exposes the product's hardest
requirements early: study and donor boundaries, batch effects, sparse matrices,
metadata quality, and preprocessing choices that must be fitted on training data
only.

Two initial use cases have different roles:

- **Cell-type annotation** is the technical canary for validating ingestion,
  schemas, study-aware splits, and evaluation.
- **Perturbation prediction** is the intended flagship benchmark because it
  better tests generalization across perturbations, cell contexts, and studies.

Protein sequence and other modalities remain candidates after the protocol
abstractions are stable. Modality priority is a research-backed product decision,
not a permanent restriction.

## Initial scope

- Versioned references to public source artifacts and their checksums
- Canonical dataset and task schemas
- Deterministic preparation protocols
- Leakage-aware split protocols and post-split audits
- Standard evaluation protocols with uncertainty where appropriate
- Python APIs, command-line workflows, metadata, and protocol documentation

## Non-goals for the first release

- Hosting or redistributing every source dataset
- Processing raw sequencing reads such as FASTQ files
- Reimplementing specialized ambient-RNA or doublet-detection algorithms
- Supporting every biological modality or task type at once
- Building dashboards, private registries, or enterprise deployment features

## Status

This repository is in project setup. The public API shown in product discussions
is directional and not yet available. The next milestone is a narrow,
end-to-end single-cell benchmark that proves the protocol model before the
dataset catalog expands.

See [core product decisions](docs/core-decisions.md) for the current conceptual
model and [development](docs/development.md) for local setup and quality checks.
