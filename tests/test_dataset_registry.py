"""Dataset registry dispatch contract tests."""

from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bioml_data._artifacts import ArtifactId, ArtifactManifest, ArtifactReceipt
from bioml_data._domain import (
    DatasetDefinition,
    DatasetLifecycle,
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    SourceReference,
    SourceUri,
    TaskId,
)
from bioml_data.datasets._models import DatasetRegistration
from bioml_data.datasets._registry import (
    DatasetCapabilityMismatchError,
    DatasetMaterializationArtifactMismatchError,
    DatasetMaterializationSnapshotMismatchError,
    DatasetRegistry,
    DuplicateDatasetRegistrationError,
)
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


@dataclass(frozen=True, slots=True)
class _FakeMaterialization:
    snapshot: DatasetSnapshotIdentity
    artifact: ArtifactManifest


def _artifact(tmp_path: Path) -> ArtifactReceipt:
    manifest = ArtifactManifest(
        artifact_id=ArtifactId("sha256:" + "1" * 64),
        logical_name="protein-fixture.json",
        source_uri="https://example.test/protein",
        accession="TEST-PROTEIN",
        release="v1",
        retrieved_at=datetime(2026, 8, 31, tzinfo=UTC),
        byte_size=1,
        sha256="1" * 64,
        tool_version="test",
    )
    return ArtifactReceipt(
        manifest=manifest,
        content_path=tmp_path / "blob",
        manifest_path=tmp_path / "manifest.json",
    )


def test_registration_excludes_provider_specific_download_metadata() -> None:
    # Given: the generic registration model shared by every dataset.

    # When: its architectural fields are inspected.
    field_names = tuple(field.name for field in fields(DatasetRegistration))

    # Then: Figshare-shaped compatibility pins are outside the registry seam.
    assert "download_pin" not in field_names


def test_registry_rejects_duplicate_exact_snapshot_keys() -> None:
    # Given: two registrations for the same exact dataset snapshot.

    # When: the registry is constructed.
    with pytest.raises(DuplicateDatasetRegistrationError):
        _ = DatasetRegistry(
            registrations=(TMS_AORTA_REGISTRATION, TMS_AORTA_REGISTRATION)
        )

    # Then: ambiguous exact keys never enter the registry.


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "dataset",
            DatasetSnapshotIdentity(
                name=DatasetName("other-dataset"),
                version=DatasetVersion("v1"),
            ),
        ),
        ("task", TaskId("other-task")),
        ("protocol", ProtocolId("other-protocol")),
    ],
)
def test_registry_rejects_incoherent_split_capabilities(
    field: str,
    value: DatasetSnapshotIdentity | TaskId | ProtocolId,
) -> None:
    # Given: one capability whose dataset, task, or protocol leaves its definition.
    capability = replace(
        TMS_AORTA_REGISTRATION.split_capabilities[0],
        **{field: value},
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(capability,),
    )

    # When: the incoherent registration enters the boundary.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: invalid capability metadata cannot become authoritative.


def test_materialize_rejects_snapshot_mismatch(tmp_path: Path) -> None:
    # Given: an adapter returning a snapshot other than its registration declares.
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
        materialize=materialize,
    )
    registry = DatasetRegistry(registrations=(registration,))

    # When: the adapter result crosses the registry boundary.
    with pytest.raises(DatasetMaterializationSnapshotMismatchError):
        _ = registry.materialize("tms-aorta", artifact)

    # Then: the mismatched materialization cannot escape.


def test_materialize_rejects_artifact_manifest_mismatch(tmp_path: Path) -> None:
    # Given: an adapter returning provenance for a different input artifact.
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
        materialize=materialize,
    )
    registry = DatasetRegistry(registrations=(registration,))

    # When: the adapter result crosses the registry boundary.
    with pytest.raises(DatasetMaterializationArtifactMismatchError):
        _ = registry.materialize("tms-aorta", artifact)

    # Then: artifact provenance cannot be substituted by an adapter.


def test_registry_dispatches_a_second_dataset_without_tms_branching(
    tmp_path: Path,
) -> None:
    # Given: a non-TMS dataset registration with its own typed adapter.
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

    # When: the generic registry materializes the second dataset.
    result = registry.materialize("protein-fixture", artifact)

    # Then: its registered adapter owns dispatch without any TMS conditional.
    assert result.snapshot == snapshot
    assert result.artifact == artifact.manifest
    assert consumed == [artifact]
