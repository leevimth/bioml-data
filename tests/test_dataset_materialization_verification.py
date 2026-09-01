"""Dataset registry materialization and lineage verification tests."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactId,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
    TransformProtocolId,
)
from bioml_data._domain import (
    DatasetDefinition,
    DatasetLifecycle,
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    SourceReference,
    SourceUri,
)
from bioml_data._split_capability_models import SplitArtifactScope
from bioml_data.datasets._materialization_verification import (
    DatasetMaterializationArtifactMismatchError,
    DatasetMaterializationSnapshotMismatchError,
)
from bioml_data.datasets._models import DatasetRegistration
from bioml_data.datasets._registry import DatasetRegistry
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


@dataclass(frozen=True, slots=True)
class _FakeMaterialization:
    snapshot: DatasetSnapshotIdentity
    artifact: ArtifactManifest


def _artifact(
    tmp_path: Path,
    *,
    content: bytes = b"x",
    derivation: ArtifactDerivation | None = None,
) -> ArtifactReceipt:
    request = ArtifactRequest(
        logical_name="protein-fixture.json",
        source_uri="https://example.test/protein",
        accession="TEST-PROTEIN",
        release="v1",
        retrieved_at=datetime(2026, 8, 31, tzinfo=UTC),
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version="test",
        derivation=derivation,
    )
    return ArtifactCache(tmp_path / "cache").store(request, (content,))


def test_materialize_rejects_snapshot_mismatch(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    wrong_snapshot = DatasetSnapshotIdentity(
        name=DatasetName("other-dataset"),
        version=DatasetVersion("v1"),
    )

    def materialize(receipt: ArtifactReceipt) -> _FakeMaterialization:
        return _FakeMaterialization(
            snapshot=wrong_snapshot,
            artifact=receipt.manifest,
        )

    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=replace(
            TMS_AORTA_REGISTRATION.definition,
            supported_splits=(),
        ),
        materialize=materialize,
        split_capabilities=(),
        artifact_scope=None,
    )

    with pytest.raises(DatasetMaterializationSnapshotMismatchError):
        _ = DatasetRegistry(registrations=(registration,)).materialize(
            "tms-aorta",
            ArtifactLineageReceipt(artifact=artifact, parent_artifacts=()),
        )


def test_materialize_rejects_artifact_manifest_mismatch(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path)
    wrong_manifest = artifact.manifest.model_copy(
        update={"artifact_id": ArtifactId("sha256:" + "2" * 64)}
    )

    def materialize(_receipt: ArtifactReceipt) -> _FakeMaterialization:
        return _FakeMaterialization(
            snapshot=TMS_AORTA_REGISTRATION.definition.snapshot,
            artifact=wrong_manifest,
        )

    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=replace(
            TMS_AORTA_REGISTRATION.definition,
            supported_splits=(),
        ),
        materialize=materialize,
        split_capabilities=(),
        artifact_scope=None,
    )

    with pytest.raises(DatasetMaterializationArtifactMismatchError):
        _ = DatasetRegistry(registrations=(registration,)).materialize(
            "tms-aorta",
            ArtifactLineageReceipt(artifact=artifact, parent_artifacts=()),
        )


def test_registry_dispatches_a_second_dataset_without_tms_branching(
    tmp_path: Path,
) -> None:
    snapshot = DatasetSnapshotIdentity(
        name=DatasetName("protein-fixture"),
        version=DatasetVersion("v1"),
    )
    definition = DatasetDefinition(
        snapshot=snapshot,
        source=SourceReference(uri=SourceUri("https://example.test/protein")),
        lifecycle=DatasetLifecycle.PLANNED,
        tasks=(),
        supported_splits=(),
    )
    artifact = _artifact(tmp_path)
    consumed: list[ArtifactReceipt] = []

    def materialize(receipt: ArtifactReceipt) -> _FakeMaterialization:
        consumed.append(receipt)
        return _FakeMaterialization(snapshot=snapshot, artifact=receipt.manifest)

    registry = DatasetRegistry(
        registrations=(
            DatasetRegistration(
                definition=definition,
                materialize=materialize,
                split_capabilities=(),
            ),
        ),
    )

    result = registry.materialize(
        "protein-fixture",
        ArtifactLineageReceipt(artifact=artifact, parent_artifacts=()),
    )

    assert result.snapshot == snapshot
    assert result.artifact == artifact.manifest
    assert consumed == [artifact]


def test_materialize_verifies_parent_receipt_bytes_before_dispatch(
    tmp_path: Path,
) -> None:
    parent = _artifact(tmp_path / "parent", content=b"verified parent")
    protocol = TransformProtocolId("fixture-transform-v1")
    derived = _artifact(
        tmp_path / "derived",
        content=b"derived payload",
        derivation=ArtifactDerivation(
            parent_artifacts=(parent.artifact_id,),
            transform_protocol=protocol,
        ),
    )

    def materialize(receipt: ArtifactReceipt) -> _FakeMaterialization:
        return _FakeMaterialization(
            snapshot=TMS_AORTA_REGISTRATION.definition.snapshot,
            artifact=receipt.manifest,
        )

    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=replace(
            TMS_AORTA_REGISTRATION.definition,
            supported_splits=(),
        ),
        split_capabilities=(),
        artifact_scope=SplitArtifactScope(
            source_artifact=parent.artifact_id,
            transform_protocol=protocol,
        ),
        materialize=materialize,
    )
    forged_parent = ArtifactReceipt(
        manifest=parent.manifest.model_copy(
            update={"artifact_id": ArtifactId("sha256:" + "9" * 64)}
        ),
        content_path=parent.content_path,
        manifest_path=parent.manifest_path,
    )

    with pytest.raises(DatasetMaterializationArtifactMismatchError):
        _ = DatasetRegistry(registrations=(registration,)).materialize(
            "tms-aorta",
            ArtifactLineageReceipt(
                artifact=derived,
                parent_artifacts=(forged_parent,),
            ),
        )
