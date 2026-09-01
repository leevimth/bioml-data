"""Compatibility behavior for manually constructed download receipts."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data._artifacts import ArtifactId


def test_legacy_download_receipt_constructor_does_not_fabricate_provider() -> None:
    # Given: an existing caller constructs the original two-field public receipt.
    artifact = bio.ArtifactReceipt(
        manifest=bio.ArtifactManifest(
            artifact_id=ArtifactId("sha256:" + "a" * 64),
            logical_name="fixture.h5ad",
            source_uri="https://example.test/fixture.h5ad",
            accession="fixture",
            release="v1",
            retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
            tool_version="test",
            byte_size=1,
            sha256="a" * 64,
        ),
        content_path=Path("fixture/blob"),
        manifest_path=Path("fixture/manifest.json"),
    )

    # When: the receipt is created without provider-native pin provenance.
    receipt = bio.DatasetDownloadReceipt(
        artifact=artifact,
        outcome=bio.DatasetDownloadOutcome.CACHE_HIT,
    )

    # Then: construction remains compatible and provider access fails explicitly.
    assert receipt.pin is None
    with pytest.raises(bio.DatasetDownloadProvenanceUnavailableError):
        _ = receipt.provider
