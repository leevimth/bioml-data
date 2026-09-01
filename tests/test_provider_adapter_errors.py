"""Provider boundary error-path security and consistency tests."""

from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data._artifacts import ArtifactId, TransformProtocolId
from bioml_data._domain import DatasetName, DatasetVersion
from tests._provider_adapter_fixtures import (
    FakeAdapter,
    FigshareReceipt,
    artifact_expectation,
    make_artifact,
    provider_target,
)


def _identity(artifact_id: ArtifactId) -> bio.ScientificArtifactIdentity:
    return bio.ScientificArtifactIdentity(
        dataset=bio.DatasetSnapshotIdentity(
            name=DatasetName("single-cell-fixture"),
            version=DatasetVersion("v1"),
        ),
        artifact_id=artifact_id,
        transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
    )


def _provider() -> bio.ProviderDescriptor:
    return bio.ProviderDescriptor(
        id=bio.ProviderId("figshare"),
        adapter_version="v1",
        optional_dependency=None,
    )


def test_provenance_mismatch_error_redacts_source_uri_secrets(tmp_path: Path) -> None:
    # Given: verified provider metadata contains URL userinfo and a query token.
    secret_uri = "https://alice:password@provider.example/file?token=top-secret"  # noqa: S105
    actual = make_artifact(
        tmp_path,
        source_uri=secret_uri,
        accession="provider-file-actual",
    )
    expected = make_artifact(
        tmp_path,
        source_uri="https://provider.example/expected",
        accession="provider-file-expected",
    )
    identity = _identity(actual.artifact_id)
    target = bio.ProviderAcquisitionTarget(
        scientific_identity=identity,
        artifact_expectation=artifact_expectation(expected),
    )
    provider = _provider()

    # When: the exact provider-native expectation check fails.
    with pytest.raises(bio.ProviderArtifactProvenanceMismatchError) as caught:
        _ = bio.acquire_provider_artifact(
            target,
            FakeAdapter(
                descriptor=provider,
                target=target,
                receipt=FigshareReceipt(
                    provider=provider,
                    artifact=actual,
                    article_id="1",
                ),
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: diagnostics retain useful evidence without credential material.
    message = str(caught.value)
    assert "alice" not in message
    assert "password" not in message
    assert "top-secret" not in message
    assert "https://provider.example/file" in message
    assert "provider-file-actual" in message
    assert actual.manifest.sha256 in message


def test_adapter_rejects_internally_inconsistent_scientific_identity(
    tmp_path: Path,
) -> None:
    # Given: provider metadata matches the receipt but its scientific hash does not.
    artifact = make_artifact(
        tmp_path,
        source_uri="https://provider.example/file/1",
        accession="provider-file-1",
    )
    target = provider_target(_identity(ArtifactId("sha256:" + "f" * 64)), artifact)
    provider = _provider()

    # When: the inconsistent target crosses the verified provider boundary.
    with pytest.raises(bio.ProviderArtifactIdentityMismatchError):
        _ = bio.acquire_provider_artifact(
            target,
            FakeAdapter(
                descriptor=provider,
                target=target,
                receipt=FigshareReceipt(
                    provider=provider,
                    artifact=artifact,
                    article_id="1",
                ),
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: verified provider metadata cannot authorize a false scientific hash.
