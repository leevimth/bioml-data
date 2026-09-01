"""Verified artifact handoff tests for eager and lazy adapters."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from bioml_data import VerifiedArtifactChangedError
from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
)
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data._verified_artifact import VerifiedArtifactInput
from bioml_data.datasets._models import DatasetAdapter, DatasetRegistration
from bioml_data.datasets._registry import DatasetRegistry
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


@dataclass(frozen=True, slots=True)
class _Materialization:
    snapshot: DatasetSnapshotIdentity
    verified_input: VerifiedArtifactInput

    @property
    def artifact(self) -> ArtifactManifest:
        return self.verified_input.manifest

    def read(self) -> bytes:
        return self.verified_input.read_bytes()


def _artifact(tmp_path: Path, content: bytes) -> ArtifactReceipt:
    request = ArtifactRequest(
        logical_name="fixture.bin",
        source_uri="https://example.test/fixture",
        accession="TEST",
        release="v1",
        retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version="test",
    )
    return ArtifactCache(tmp_path / "cache").store(request, (content,))


def _registration(materialize: DatasetAdapter) -> DatasetRegistration:
    return replace(
        TMS_AORTA_REGISTRATION,
        definition=replace(
            TMS_AORTA_REGISTRATION.definition,
            supported_splits=(),
        ),
        materialize=materialize,
        split_capabilities=(),
        artifact_scope=None,
    )


def test_adapter_rejects_original_cache_swap_before_verified_read(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, b"trusted")
    original_path = artifact.content_path
    consumed: list[bytes] = []

    def materialize(receipt: VerifiedArtifactInput) -> _Materialization:
        _ = original_path.write_bytes(b"swapped")
        consumed.append(receipt.read_bytes())
        return _Materialization(
            snapshot=TMS_AORTA_REGISTRATION.definition.snapshot,
            verified_input=receipt,
        )

    registration = _registration(materialize)
    with pytest.raises(VerifiedArtifactChangedError):
        _ = DatasetRegistry(registrations=(registration,)).materialize(
            "tms-aorta",
            ArtifactLineageReceipt(artifact=artifact, parent_artifacts=()),
        )

    assert consumed == []


def test_lazy_adapter_revalidates_reads_after_materialize_returns(
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path, b"lazy-content")

    def materialize(receipt: VerifiedArtifactInput) -> _Materialization:
        return _Materialization(
            snapshot=TMS_AORTA_REGISTRATION.definition.snapshot,
            verified_input=receipt,
        )

    registration = _registration(materialize)
    result = DatasetRegistry(registrations=(registration,)).materialize(
        "tms-aorta",
        ArtifactLineageReceipt(artifact=artifact, parent_artifacts=()),
    )

    assert isinstance(result, _Materialization)
    assert result.read() == b"lazy-content"

    _ = artifact.content_path.write_bytes(b"evil-content")
    with pytest.raises(VerifiedArtifactChangedError):
        _ = result.read()
