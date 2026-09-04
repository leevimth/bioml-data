"""Typed fixture construction for preparation-execution receipt tests."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import bioml_data as bio
import bioml_data.preparation_execution as execution
from bioml_data._artifact_derivation import ArtifactDerivationParameter
from bioml_data._artifacts import (
    ArtifactDerivation,
    ArtifactId,
    ArtifactManifest,
    ArtifactReceipt,
    TransformProtocolId,
)
from bioml_data._dataset_preparation_models import DatasetPreparationOutcome
from bioml_data._preparation import (
    FeatureSelectionParameters,
    GeneAlignmentParameters,
    NormalizationParameters,
    PreparationProtocol,
    QcParameters,
)

from ._metadata_concordance_helpers import (
    explicit_partition_evidence,
    metadata_dataset,
    metadata_scope,
)
from ._single_cell_fixtures import make_split


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Typed fixture inputs for one public receipt-construction scenario."""

    dataset: bio.CanonicalSingleCellDataset
    input_artifact: ArtifactReceipt
    materialization: bio.DatasetPreparationReceipt
    prepared: bio.PreparedBenchmarkReceipt
    assignment: bio.SplitAssignmentReceipt
    protocol: PreparationProtocol
    runtime: execution.PreparationExecutionRuntime
    concordance: bio.MetadataConcordanceReport


def execution_context(tmp_path: Path) -> ExecutionContext:
    """Return a complete fixture-scale scientific execution context."""
    dataset = metadata_dataset()
    raw = artifact(
        artifact_id=ArtifactId(
            "sha256:0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3"
        ),
        directory=tmp_path / "raw",
    )
    canonical = ArtifactReceipt(
        manifest=dataset.artifact.model_copy(
            update={
                "derivation": ArtifactDerivation(
                    parent_artifacts=(raw.artifact_id,),
                    transform_protocol=TransformProtocolId("tms-aorta-csr-v1"),
                    parameters=(
                        ArtifactDerivationParameter(
                            name="expression_input",
                            value="raw.X",
                        ),
                    ),
                )
            }
        ),
        content_path=tmp_path / "canonical" / "blob",
        manifest_path=tmp_path / "canonical" / "manifest.json",
    )
    dataset = replace(dataset, artifact=canonical.manifest)
    materialization = bio.DatasetPreparationReceipt(
        artifact=canonical,
        parent_artifacts=(raw,),
        outcome=DatasetPreparationOutcome.TRANSFORMED,
    )
    split = make_split(dataset)
    protocol = _protocol(dataset)
    prepared = bio.prepare_benchmark(
        bio.PreparationRequest(
            dataset=dataset,
            protocol=protocol,
            split=split,
            seed=17,
        )
    )
    scope = metadata_scope()
    concordance = bio.compare_metadata_concordance(
        dataset,
        split,
        expectations=(
            bio.PublicationMetadataExpectation.not_reported(
                scope=scope,
                partition=None,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
            ),
            *explicit_partition_evidence(scope),
        ),
    )
    return ExecutionContext(
        dataset=dataset,
        input_artifact=raw,
        materialization=materialization,
        prepared=prepared,
        assignment=split,
        protocol=protocol,
        runtime=execution.PreparationExecutionRuntime(
            toolkit_version="0.0.0",
            dependencies=(
                execution.DependencyVersion(
                    component=execution.RuntimeComponent.ANNDATA, version="0.12"
                ),
                execution.DependencyVersion(
                    component=execution.RuntimeComponent.NUMPY, version="2.0"
                ),
            ),
        ),
        concordance=concordance,
    )


def record(context: ExecutionContext) -> execution.PreparationExecutionReceipt:
    """Invoke the public receipt boundary with complete typed fixture inputs."""
    return execution.record_preparation_execution(
        execution.PreparationExecutionRequest(
            dataset=context.dataset,
            input_artifact=context.input_artifact,
            materialization=context.materialization,
            prepared=context.prepared,
            assignment=context.assignment,
            protocol=context.protocol,
            runtime=context.runtime,
            concordance=context.concordance,
        )
    )


def artifact(*, artifact_id: ArtifactId, directory: Path) -> ArtifactReceipt:
    """Return one path-free test-only raw receipt identity."""
    digest = str(artifact_id).removeprefix("sha256:")
    return ArtifactReceipt(
        manifest=ArtifactManifest(
            artifact_id=artifact_id,
            logical_name="raw.h5ad",
            source_uri="https://example.test/raw",
            accession="fixture-raw",
            release="v1",
            retrieved_at=datetime(2026, 9, 4, tzinfo=UTC),
            byte_size=0,
            sha256=digest,
            tool_version="test",
        ),
        content_path=directory / "blob",
        manifest_path=directory / "manifest.json",
    )


def _protocol(dataset: bio.CanonicalSingleCellDataset) -> PreparationProtocol:
    """Return the small fixture's complete semantic preparation protocol."""
    return PreparationProtocol(
        protocol_id="fixture-preparation-v1",
        version="1",
        qc=QcParameters(minimum_cell_count=1, minimum_feature_cells=1),
        alignment=GeneAlignmentParameters(
            feature_ids=tuple(item.feature_id for item in dataset.features),
        ),
        normalization=NormalizationParameters(target_sum=100.0),
        feature_selection=FeatureSelectionParameters(max_features=3),
    )
