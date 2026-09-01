"""Artifact-lineage verification at dataset materialization boundaries."""

from dataclasses import dataclass
from typing import override

from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifact_receipts import load_artifact_receipt
from bioml_data._artifacts import (
    ArtifactDerivation,
    ArtifactManifest,
    ArtifactReceipt,
)
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data._split_capability_models import SplitArtifactScope
from bioml_data.datasets._models import DatasetMaterialization, DatasetRegistration


@dataclass(frozen=True, slots=True)
class DatasetMaterializationSnapshotMismatchError(Exception):
    """Raised when an adapter returns a different dataset snapshot."""

    expected: DatasetSnapshotIdentity
    actual: DatasetSnapshotIdentity

    @override
    def __str__(self) -> str:
        return f"materialization snapshot {self.actual!r} != {self.expected!r}"


@dataclass(frozen=True, slots=True)
class DatasetMaterializationArtifactMismatchError(Exception):
    """Raised when an adapter substitutes input artifact provenance."""

    expected: ArtifactManifest
    actual: ArtifactManifest

    @override
    def __str__(self) -> str:
        return "materialization artifact manifest differs from its input"


@dataclass(frozen=True, slots=True)
class DatasetMaterializationProvenanceMismatchError(Exception):
    """Raised when a materialized artifact leaves its registered lineage."""

    expected: SplitArtifactScope
    actual: ArtifactDerivation | None

    @override
    def __str__(self) -> str:
        return "materialization derivation differs from its registered artifact scope"


def materialize_verified(
    registration: DatasetRegistration,
    lineage: ArtifactLineageReceipt,
) -> DatasetMaterialization:
    """Verify cached bytes and exact lineage before dispatching an adapter."""
    artifact = lineage.artifact
    verified_artifact = load_artifact_receipt(artifact.manifest_path)
    if verified_artifact != artifact:
        raise DatasetMaterializationArtifactMismatchError(
            expected=verified_artifact.manifest,
            actual=artifact.manifest,
        )
    verified_parents = tuple(
        load_artifact_receipt(parent.manifest_path)
        for parent in lineage.parent_artifacts
    )
    for verified_parent, supplied_parent in zip(
        verified_parents,
        lineage.parent_artifacts,
        strict=True,
    ):
        if verified_parent != supplied_parent:
            raise DatasetMaterializationArtifactMismatchError(
                expected=verified_parent.manifest,
                actual=supplied_parent.manifest,
            )
    _require_registered_lineage(
        registration, artifact.manifest.derivation, verified_parents
    )

    result = registration.materialize(artifact)
    expected_snapshot = registration.definition.snapshot
    if result.snapshot != expected_snapshot:
        raise DatasetMaterializationSnapshotMismatchError(
            expected=expected_snapshot,
            actual=result.snapshot,
        )
    if result.artifact != artifact.manifest:
        raise DatasetMaterializationArtifactMismatchError(
            expected=artifact.manifest,
            actual=result.artifact,
        )
    return result


def _require_registered_lineage(
    registration: DatasetRegistration,
    derivation: ArtifactDerivation | None,
    verified_parents: tuple[ArtifactReceipt, ...],
) -> None:
    scope = registration.artifact_scope
    if scope is None:
        return
    verified_parent_ids = tuple(parent.artifact_id for parent in verified_parents)
    if (
        derivation is None
        or derivation.transform_protocol != scope.transform_protocol
        or derivation.parent_artifacts != scope.parent_artifacts
        or verified_parent_ids != scope.parent_artifacts
    ):
        raise DatasetMaterializationProvenanceMismatchError(
            expected=scope,
            actual=derivation,
        )
