"""Provider acquisition boundary conformance scenarios."""

from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data._artifacts import (
    TransformProtocolId,
)
from bioml_data._domain import DatasetName, DatasetVersion
from tests._provider_adapter_fixtures import (
    FakeAdapter,
    FigshareReceipt,
    HubReceipt,
    make_artifact,
)


def test_two_provider_receipts_share_scientific_identity_without_losing_provenance(
    tmp_path: Path,
) -> None:
    # Given: two native providers deliver the same canonical scientific artifact.
    snapshot = bio.DatasetSnapshotIdentity(
        name=DatasetName("single-cell-fixture"),
        version=DatasetVersion("v1"),
    )
    figshare = bio.ProviderDescriptor(
        id=bio.ProviderId("figshare"),
        adapter_version="v1",
        optional_dependency=None,
    )
    hub = bio.ProviderDescriptor(
        id=bio.ProviderId("cellxgene"),
        adapter_version="v2",
        optional_dependency="cellxgene-census",
    )
    figshare_receipt = FigshareReceipt(
        provider=figshare,
        artifact=make_artifact(
            tmp_path,
            source_uri="https://figshare.example/file/1",
            accession="figshare-file-1",
        ),
        article_id="article-1",
    )
    hub_receipt = HubReceipt(
        provider=hub,
        artifact=make_artifact(
            tmp_path,
            source_uri="https://cellxgene.example/object/1",
            accession="cellxgene-object-1",
        ),
        object_key="object-1",
    )
    expected = bio.ScientificArtifactIdentity(
        dataset=snapshot,
        artifact_id=figshare_receipt.artifact.artifact_id,
        transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
    )

    # When: each explicit adapter resolves its provider-native receipt.
    first = bio.acquire_provider_artifact(
        expected,
        FakeAdapter(
            descriptor=figshare,
            scientific_identity=expected,
            receipt=figshare_receipt,
        ),
        data_dir=tmp_path / "research-cache",
    )
    second = bio.acquire_provider_artifact(
        expected,
        FakeAdapter(
            descriptor=hub,
            scientific_identity=expected,
            receipt=hub_receipt,
        ),
        data_dir=tmp_path / "research-cache",
    )

    # Then: scientific identity is equal while provider-native provenance differs.
    assert first.identity == second.identity
    assert first.receipt.article_id == "article-1"
    assert second.receipt.object_key == "object-1"
    assert first.receipt.provider != second.receipt.provider
    assert first.receipt.artifact.manifest.source_uri != (
        second.receipt.artifact.manifest.source_uri
    )


def test_adapter_rejects_a_receipt_claiming_another_provider(tmp_path: Path) -> None:
    # Given: an adapter descriptor and native receipt that name different providers.
    snapshot = bio.DatasetSnapshotIdentity(
        name=DatasetName("single-cell-fixture"),
        version=DatasetVersion("v1"),
    )
    adapter_provider = bio.ProviderDescriptor(
        id=bio.ProviderId("figshare"),
        adapter_version="v1",
        optional_dependency=None,
    )
    receipt_provider = bio.ProviderDescriptor(
        id=bio.ProviderId("cellxgene"),
        adapter_version="v2",
        optional_dependency="cellxgene-census",
    )
    receipt = FigshareReceipt(
        provider=receipt_provider,
        artifact=make_artifact(
            tmp_path,
            source_uri="https://figshare.example/file/1",
            accession="figshare-file-1",
        ),
        article_id="article-1",
    )
    expected = bio.ScientificArtifactIdentity(
        dataset=snapshot,
        artifact_id=receipt.artifact.artifact_id,
        transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
    )

    # When: the inconsistent receipt crosses the provider boundary.
    with pytest.raises(bio.ProviderReceiptMismatchError):
        _ = bio.acquire_provider_artifact(
            expected,
            FakeAdapter(
                descriptor=adapter_provider,
                scientific_identity=expected,
                receipt=receipt,
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: provider provenance cannot be silently relabeled.
