"""Provider acquisition boundary conformance scenarios."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data._artifacts import (
    ArtifactDerivation,
    ArtifactId,
    ArtifactManifest,
    ArtifactReceipt,
    TransformProtocolId,
)
from bioml_data._domain import DatasetName, DatasetVersion


@dataclass(frozen=True, slots=True)
class _FigshareReceipt:
    provider: bio.ProviderDescriptor
    artifact: ArtifactReceipt
    article_id: str


@dataclass(frozen=True, slots=True)
class _HubReceipt:
    provider: bio.ProviderDescriptor
    artifact: ArtifactReceipt
    object_key: str


@dataclass(frozen=True, slots=True)
class _FakeAdapter[ReceiptT: bio.ProviderAcquisitionReceipt]:
    descriptor: bio.ProviderDescriptor
    receipt: ReceiptT

    def acquire(self, *, data_dir: Path) -> ReceiptT:
        assert data_dir.name == "research-cache"
        return self.receipt


def _artifact(
    tmp_path: Path,
    *,
    source_uri: str,
    accession: str,
) -> ArtifactReceipt:
    digest = "a" * 64
    manifest = ArtifactManifest(
        artifact_id=ArtifactId(f"sha256:{digest}"),
        logical_name="canonical.h5ad",
        source_uri=source_uri,
        accession=accession,
        release="2026-09-01",
        retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
        byte_size=42,
        sha256=digest,
        tool_version="provider-fixture/1",
        derivation=ArtifactDerivation(
            parent_artifacts=(ArtifactId("sha256:" + "b" * 64),),
            transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
        ),
    )
    return ArtifactReceipt(
        manifest=manifest,
        content_path=tmp_path / accession / "blob",
        manifest_path=tmp_path / accession / "manifest.json",
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
    figshare_receipt = _FigshareReceipt(
        provider=figshare,
        artifact=_artifact(
            tmp_path,
            source_uri="https://figshare.example/file/1",
            accession="figshare-file-1",
        ),
        article_id="article-1",
    )
    hub_receipt = _HubReceipt(
        provider=hub,
        artifact=_artifact(
            tmp_path,
            source_uri="https://cellxgene.example/object/1",
            accession="cellxgene-object-1",
        ),
        object_key="object-1",
    )

    # When: each explicit adapter resolves its provider-native receipt.
    first = bio.acquire_provider_artifact(
        snapshot,
        _FakeAdapter(descriptor=figshare, receipt=figshare_receipt),
        data_dir=tmp_path / "research-cache",
    )
    second = bio.acquire_provider_artifact(
        snapshot,
        _FakeAdapter(descriptor=hub, receipt=hub_receipt),
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
    receipt = _FigshareReceipt(
        provider=receipt_provider,
        artifact=_artifact(
            tmp_path,
            source_uri="https://figshare.example/file/1",
            accession="figshare-file-1",
        ),
        article_id="article-1",
    )

    # When: the inconsistent receipt crosses the provider boundary.
    with pytest.raises(bio.ProviderReceiptMismatchError):
        _ = bio.acquire_provider_artifact(
            snapshot,
            _FakeAdapter(descriptor=adapter_provider, receipt=receipt),
            data_dir=tmp_path / "research-cache",
        )

    # Then: provider provenance cannot be silently relabeled.
