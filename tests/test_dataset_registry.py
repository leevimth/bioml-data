"""Dataset registry dispatch contract tests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from bioml_data._artifacts import ArtifactId, ArtifactManifest, ArtifactReceipt
from bioml_data._domain import (
    DatasetDefinition,
    DatasetLifecycle,
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    SourceReference,
    SourceUri,
)
from bioml_data.datasets._models import DatasetRegistration
from bioml_data.datasets._registry import DatasetRegistry


@dataclass(frozen=True, slots=True)
class _FakeMaterialization:
    snapshot: DatasetSnapshotIdentity
    artifact: ArtifactManifest


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
    artifact = ArtifactReceipt(
        manifest=manifest,
        content_path=tmp_path / "blob",
        manifest_path=tmp_path / "manifest.json",
    )
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
                download_pin=None,
            ),
        ),
    )

    # When: the generic registry materializes the second dataset.
    result = registry.materialize("protein-fixture", artifact)

    # Then: its registered adapter owns dispatch without any TMS conditional.
    assert result.snapshot == snapshot
    assert result.artifact == manifest
    assert consumed == [artifact]
