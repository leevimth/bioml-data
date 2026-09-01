"""Adversarial binding tests for provider acquisition targets."""

from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data._artifacts import TransformProtocolId
from bioml_data._domain import DatasetName, DatasetVersion
from tests._provider_adapter_fixtures import (
    FakeAdapter,
    FigshareReceipt,
    make_artifact,
    provider_target,
)


@pytest.mark.parametrize(
    ("content", "transform_protocol"),
    [
        (b"unexpected fixture", "canonical-single-cell-v1"),
        (b"expected fixture", "other-transform-v1"),
    ],
)
def test_adapter_rejects_wrong_artifact_identity_from_same_provider(
    tmp_path: Path,
    content: bytes,
    transform_protocol: str,
) -> None:
    # Given: a correctly named provider returns bytes outside its requested target.
    provider = bio.ProviderDescriptor(
        id=bio.ProviderId("figshare"),
        adapter_version="v1",
        optional_dependency=None,
    )
    expected_artifact = make_artifact(
        tmp_path,
        source_uri="https://figshare.example/file/expected",
        accession="figshare-file-expected",
        content=b"expected fixture",
    )
    expected = bio.ScientificArtifactIdentity(
        dataset=bio.DatasetSnapshotIdentity(
            name=DatasetName("single-cell-fixture"),
            version=DatasetVersion("v1"),
        ),
        artifact_id=expected_artifact.artifact_id,
        transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
    )
    receipt = FigshareReceipt(
        provider=provider,
        artifact=make_artifact(
            tmp_path,
            source_uri="https://figshare.example/file/2",
            accession="figshare-file-2",
            content=content,
            transform_protocol=transform_protocol,
        ),
        article_id="article-2",
    )

    # When: the same-descriptor adapter resolves the unexpected content.
    target = provider_target(expected, expected_artifact)
    with pytest.raises(bio.ProviderArtifactProvenanceMismatchError):
        _ = bio.acquire_provider_artifact(
            target,
            FakeAdapter(
                descriptor=provider,
                target=target,
                receipt=receipt,
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: provider naming cannot substitute for verified artifact metadata.


def test_adapter_rejects_a_binding_for_another_dataset(tmp_path: Path) -> None:
    # Given: the caller requests one dataset but the adapter is bound to another.
    provider = bio.ProviderDescriptor(
        id=bio.ProviderId("figshare"),
        adapter_version="v1",
        optional_dependency=None,
    )
    receipt = FigshareReceipt(
        provider=provider,
        artifact=make_artifact(
            tmp_path,
            source_uri="https://figshare.example/file/1",
            accession="figshare-file-1",
        ),
        article_id="article-1",
    )
    requested = bio.ScientificArtifactIdentity(
        dataset=bio.DatasetSnapshotIdentity(
            name=DatasetName("requested-dataset"),
            version=DatasetVersion("v1"),
        ),
        artifact_id=receipt.artifact.artifact_id,
        transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
    )
    adapter_target = bio.ScientificArtifactIdentity(
        dataset=bio.DatasetSnapshotIdentity(
            name=DatasetName("other-dataset"),
            version=DatasetVersion("v1"),
        ),
        artifact_id=receipt.artifact.artifact_id,
        transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
    )
    requested_binding = provider_target(requested, receipt.artifact)
    adapter_binding = provider_target(adapter_target, receipt.artifact)

    # When: the mismatched adapter binding is presented for acquisition.
    with pytest.raises(bio.ProviderTargetMismatchError):
        _ = bio.acquire_provider_artifact(
            requested_binding,
            FakeAdapter(
                descriptor=provider,
                target=adapter_binding,
                receipt=receipt,
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: a caller cannot relabel the adapter's artifact as another dataset.
