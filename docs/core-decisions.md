# Core product decisions

This document separates decisions already made from questions that still need
evidence. It should change through explicit review as the first benchmark is
implemented.

## Product boundary

`bioml-data` is a data and evaluation protocol layer between public biological
data and model training. It should make the transformation from source artifact
to benchmark inspectable, reproducible, and leakage-aware.

The product does not treat a download URL as a dataset definition. A usable
definition also records source, license, citation, checksums, schema, task,
preparation, split, known leakage risks, metrics, and reference results.

## Dataset and task are separate concepts

A **DatasetSnapshot** identifies immutable source artifacts plus their observed
schema and provenance. It answers, “What data did we receive?”

A **TaskDefinition** selects inputs, targets, eligible observations, prediction
unit, and metrics from a dataset snapshot. It answers, “What learning problem
are we constructing?”

The separation is necessary because one biological dataset can support several
tasks, and the leakage units that matter depend on the task. Reusing a snapshot
must not silently reuse a task definition or split.

## Raw artifacts are immutable

Downloaded source artifacts are content-addressed and never edited in place.
Every derived artifact points back to:

- source URI and retrieval timestamp;
- upstream release or accession when available;
- content checksum and byte size;
- toolkit and protocol versions;
- parameters and parent artifacts.

Corrections produce a new derived artifact and provenance record. They do not
rewrite history.

## Three audit layers

### Dataset audit

Runs before a task is chosen. It checks source integrity, schema compatibility,
duplicate identifiers, missing metadata, feature identifiers, and suspicious
study or donor inconsistencies.

### Task audit

Runs after a TaskDefinition is applied. It checks target availability, class or
response support, covariate coverage, prediction-unit consistency, and whether
the task's intended generalization claim is supported by the available metadata.

### Split audit

Runs after split assignment. It checks forbidden overlaps and reports relatedness
between partitions. Examples include donor, study, batch, perturbation, cell
line, biological replicate, or sequence-homology overlap. Passing an audit means
the declared constraints were satisfied; it does not prove that every possible
source of leakage was eliminated.

## Preparation has two phases

**Deterministic preparation** may inspect the full immutable dataset when its
output does not learn population statistics. Examples include schema
normalization, stable identifier mapping, lossless format conversion, and rules
whose parameters are fixed in the protocol.

**Train-fitted preprocessing** learns statistics or representations from the
training partition only, then applies the fitted state to validation and test.
Examples include feature selection, scaling parameters, learned vocabularies,
dimensionality reduction, and data-driven thresholds.

The protocol records which phase owns each transformation. A split is created
before any train-fitted transformation.

## Initial modality and use cases

Single-cell is the first major modality to validate. It forces the toolkit to
handle study, donor, batch, and biological replicate boundaries rather than
treating observations as independent rows.

- Cell-type annotation is the **technical canary**. It validates ingestion,
  canonical schemas, animal-/group-aware splitting, and evaluation on a
  tractable task.
- Perturbation prediction is the **flagship use case**. Its protocol should make
  the held-out axis explicit, such as perturbation, cell context, combination,
  donor, or study, and should avoid presenting one split as universal evidence of
  generalization.

Protein sequence remains a likely follow-on modality. Homology-aware splitting
is one instance of the broader split-protocol and relatedness-audit model, not a
special case that should define the entire architecture.

### First implementation target

Tabula Muris Senis Aorta is the first technical canary. Its canonical sparse
adapter, product-defined animal-held-out split, preparation lifecycle, leakage
audit, and evaluation receipt are executable for an explicitly pinned processed
artifact. Public retrieval is pinned to an exact upstream file with its official
byte size and MD5 plus a project-verified SHA-256. The catalog entry remains
`planned`, but the acquisition-to-canonical boundary is now executable:
`prepare_dataset()` accepts only that pinned source receipt, selects `raw.X`
under `tms-aorta-csr-v1`, records the choice as a derivation parameter, and
produces the artifact consumed by the complete canary lifecycle.

The implementation order after the common contracts is artifact provenance,
dataset-specific split capabilities, the TMS Aorta adapter, train-fitted
preprocessing, and an end-to-end evaluation receipt.

## Public API and protocol selection

The dataset entry point is `bioml_data.load_dataset()`. It resolves a versioned,
immutable dataset definition before downloading or preparing data. When a
catalog contains more than one version, callers must select a version rather
than silently receiving a moving `latest` definition.

Task and split protocol are separate selections. Split planning requires both
to be explicit; there is no default split. Literature-reused behavior is labeled
as a reference protocol, while a biologically safer alternative may be exposed
as a robustness protocol. Neither label claims that one protocol is universally
correct, and the package must not choose between them silently.

Small reference models may be used as executable sanity checks. Their results
verify that a protocol can run end to end; they are not model recommendations or
leaderboard claims.

## Versioned protocol identity

A prepared benchmark should be citeable using independently versioned pieces:

- dataset snapshot;
- task definition;
- preparation protocol;
- split protocol;
- evaluation protocol.

Changing any behavior that can alter benchmark membership or results creates a
new protocol version. Documentation-only corrections do not.

## Open questions

These items are deliberately not decided yet:

- Which perturbation benchmark and held-out axes best represent the flagship?
- What minimum metadata quality is required before a dataset is supported?
- Which artifact formats form the stable public interchange boundary?
- Which open-source license should govern the repository?
- What compatibility policy should protocol versions follow before `1.0`?
