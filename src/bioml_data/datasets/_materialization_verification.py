"""Artifact-lineage verification at dataset materialization boundaries."""

from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final, override

from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifact_paths import open_binary_nofollow
from bioml_data._artifact_receipts import load_artifact_receipt
from bioml_data._artifact_types import ArtifactId
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
)
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data._split_capability_models import SplitArtifactScope
from bioml_data.datasets._models import DatasetMaterialization, DatasetRegistration

_SNAPSHOT_CACHE_DIRECTORY: Final = ".materialization-snapshots"


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


@dataclass(frozen=True, slots=True)
class DatasetMaterializationLineageMismatchError(Exception):
    """Raised when supplied parent receipts differ from declared derivation."""

    declared: tuple[ArtifactId, ...]
    supplied: tuple[ArtifactId, ...]

    @override
    def __str__(self) -> str:
        return "supplied parent receipts differ from the artifact derivation"


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

    snapshot = _verified_persistent_snapshot(verified_artifact)
    result = registration.materialize(snapshot)
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
    supplied_parent_ids = tuple(parent.artifact_id for parent in verified_parents)
    declared_parent_ids = () if derivation is None else derivation.parent_artifacts
    if declared_parent_ids != supplied_parent_ids:
        raise DatasetMaterializationLineageMismatchError(
            declared=declared_parent_ids,
            supplied=supplied_parent_ids,
        )

    scope = registration.artifact_scope
    if scope is None:
        return
    if (
        derivation is None
        or derivation.transform_protocol != scope.transform_protocol
        or derivation.parent_artifacts != scope.parent_artifacts
    ):
        raise DatasetMaterializationProvenanceMismatchError(
            expected=scope,
            actual=derivation,
        )


def _verified_persistent_snapshot(receipt: ArtifactReceipt) -> ArtifactReceipt:
    manifest = receipt.manifest
    request = ArtifactRequest(
        logical_name=manifest.logical_name,
        source_uri=manifest.source_uri,
        accession=manifest.accession,
        release=manifest.release,
        retrieved_at=manifest.retrieved_at,
        expected_byte_size=manifest.byte_size,
        expected_sha256=manifest.sha256,
        tool_version=manifest.tool_version,
        derivation=manifest.derivation,
    )
    with open_binary_nofollow(receipt.content_path) as source:
        snapshot = ArtifactCache(_snapshot_cache_root(receipt)).store(
            request,
            iter(partial(source.read, 1024 * 1024), b""),
        )
    if snapshot.manifest != manifest:
        raise DatasetMaterializationArtifactMismatchError(
            expected=manifest,
            actual=snapshot.manifest,
        )
    return snapshot


def _snapshot_cache_root(receipt: ArtifactReceipt) -> Path:
    cache_root = receipt.manifest_path.parents[3]
    if cache_root.name == _SNAPSHOT_CACHE_DIRECTORY:
        return cache_root
    return cache_root / _SNAPSHOT_CACHE_DIRECTORY
