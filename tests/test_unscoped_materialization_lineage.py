"""Generic lineage invariants for registrations without an artifact scope."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
    TransformProtocolId,
)
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data._verified_artifact import VerifiedArtifactInput
from bioml_data.datasets._materialization_verification import (
    DatasetMaterializationLineageMismatchError,
)
from bioml_data.datasets._registry import DatasetRegistry
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


@dataclass(frozen=True, slots=True)
class _Materialization:
    snapshot: DatasetSnapshotIdentity
    artifact: ArtifactManifest


def _artifact(cache_root: Path, content: bytes) -> ArtifactReceipt:
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
    return ArtifactCache(cache_root).store(request, (content,))


def _assert_unscoped_lineage_rejected(
    tmp_path: Path,
    supplied_order: tuple[int, ...],
) -> None:
    parents = tuple(
        _artifact(tmp_path / f"parent-{index}", f"parent-{index}".encode())
        for index in range(3)
    )
    derived_content = b"derived"
    derived_request = ArtifactRequest(
        logical_name="derived.bin",
        source_uri="https://example.test/derived",
        accession="TEST",
        release="v1",
        retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
        expected_byte_size=len(derived_content),
        expected_sha256=sha256(derived_content).hexdigest(),
        tool_version="test",
        derivation=ArtifactDerivation(
            parent_artifacts=(parents[0].artifact_id, parents[1].artifact_id),
            transform_protocol=TransformProtocolId("fixture-transform-v1"),
        ),
    )
    derived = ArtifactCache(tmp_path / "derived").store(
        derived_request,
        (derived_content,),
    )

    def materialize(receipt: VerifiedArtifactInput) -> _Materialization:
        return _Materialization(
            snapshot=TMS_AORTA_REGISTRATION.definition.snapshot,
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
    supplied = tuple(parents[index] for index in supplied_order)

    with pytest.raises(DatasetMaterializationLineageMismatchError):
        _ = DatasetRegistry(registrations=(registration,)).materialize(
            "tms-aorta",
            ArtifactLineageReceipt(artifact=derived, parent_artifacts=supplied),
        )


def test_unscoped_registration_rejects_missing_parent_receipt(tmp_path: Path) -> None:
    _assert_unscoped_lineage_rejected(tmp_path, (0,))


def test_unscoped_registration_rejects_extra_parent_receipt(tmp_path: Path) -> None:
    _assert_unscoped_lineage_rejected(tmp_path, (0, 1, 2))


def test_unscoped_registration_rejects_reordered_parent_receipts(
    tmp_path: Path,
) -> None:
    _assert_unscoped_lineage_rejected(tmp_path, (1, 0))
