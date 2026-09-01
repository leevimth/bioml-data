"""TMS Aorta artifact-lineage boundary tests."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data import _tms_aorta as tms
from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactId,
    ArtifactRequest,
)
from bioml_data.datasets.tms_aorta._identity import TMS_AORTA_SOURCE_ARTIFACT
from tests._single_cell_fixtures import make_tms_artifact


def _raw_parent(cache_root: Path, content: bytes) -> bio.ArtifactReceipt:
    request = ArtifactRequest(
        logical_name="unrelated-parent.bin",
        source_uri="https://example.test/tms-aorta/fixture",
        accession="TEST-TMS-AORTA",
        release="fixture-v1",
        retrieved_at=datetime(2026, 8, 30, 14, tzinfo=UTC),
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version="bioml-data/0.0.0",
    )
    return ArtifactCache(cache_root).store(request, (content,))


def test_public_loader_requires_parent_receipts(tmp_path: Path) -> None:
    # Given: a valid derived receipt whose parent bytes were not supplied.
    artifact = make_tms_artifact(tmp_path / "derived")

    # When: only the derived receipt reaches the public materialization boundary.
    with pytest.raises(bio.ArtifactLineageRequiredError):
        bio.load_dataset("tms-aorta", artifact=artifact)

    # Then: a declared parent ID alone is not accepted as verified lineage.


def test_adapter_rejects_processed_artifact_with_unpinned_parent(
    tmp_path: Path,
) -> None:
    artifact = make_tms_artifact(
        tmp_path / "derived",
        parent_artifacts=(ArtifactId("sha256:" + "9" * 64),),
    )

    with pytest.raises(tms.UnlinkedTmsArtifactError):
        _ = tms.load_tms_aorta(artifact)


def test_public_loader_rejects_processed_artifact_with_unpinned_parent(
    tmp_path: Path,
) -> None:
    parent = _raw_parent(tmp_path / "parent", b"unrelated raw parent")
    artifact = make_tms_artifact(
        tmp_path / "derived",
        parent_artifacts=(parent.artifact_id,),
    )

    with pytest.raises(bio.DatasetMaterializationProvenanceMismatchError):
        _ = bio.load_dataset(
            "tms-aorta",
            artifact=ArtifactLineageReceipt(
                artifact=artifact,
                parent_artifacts=(parent,),
            ),
        )


def test_adapter_rejects_processed_artifact_with_extra_parent(
    tmp_path: Path,
) -> None:
    artifact = make_tms_artifact(
        tmp_path / "derived",
        parent_artifacts=(
            TMS_AORTA_SOURCE_ARTIFACT,
            ArtifactId("sha256:" + "7" * 64),
        ),
    )

    with pytest.raises(tms.UnlinkedTmsArtifactError):
        _ = tms.load_tms_aorta(artifact)


def test_public_loader_rejects_processed_artifact_with_extra_parent(
    tmp_path: Path,
) -> None:
    extra_parent = _raw_parent(tmp_path / "parent", b"extra raw parent")
    artifact = make_tms_artifact(
        tmp_path / "derived",
        parent_artifacts=(
            TMS_AORTA_SOURCE_ARTIFACT,
            extra_parent.artifact_id,
        ),
    )

    with pytest.raises(bio.DatasetMaterializationProvenanceMismatchError):
        _ = bio.load_dataset(
            "tms-aorta",
            artifact=ArtifactLineageReceipt(
                artifact=artifact,
                parent_artifacts=(extra_parent,),
            ),
        )
