"""Adversarial integrity tests for provider-native artifact receipts."""

from dataclasses import replace
from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data._artifacts import ArtifactReceipt, TransformProtocolId
from bioml_data._domain import DatasetName, DatasetVersion
from tests._provider_adapter_fixtures import (
    FakeAdapter,
    FigshareReceipt,
    artifact_expectation,
    make_artifact,
    make_self_attested_artifact,
    provider_target,
)


def _provider() -> bio.ProviderDescriptor:
    return bio.ProviderDescriptor(
        id=bio.ProviderId("figshare"),
        adapter_version="v1",
        optional_dependency=None,
    )


def _identity(artifact: ArtifactReceipt) -> bio.ScientificArtifactIdentity:
    return bio.ScientificArtifactIdentity(
        dataset=bio.DatasetSnapshotIdentity(
            name=DatasetName("single-cell-fixture"),
            version=DatasetVersion("v1"),
        ),
        artifact_id=artifact.artifact_id,
        transform_protocol=TransformProtocolId("canonical-single-cell-v1"),
    )


def _assert_receipt_load_fails(
    tmp_path: Path,
    artifact: ArtifactReceipt,
    claimed: ArtifactReceipt,
) -> None:
    provider = _provider()
    expected = _identity(artifact)
    target = provider_target(expected, artifact)
    receipt = FigshareReceipt(provider=provider, artifact=claimed, article_id="1")
    with pytest.raises(bio.ArtifactReceiptLoadError):
        _ = bio.acquire_provider_artifact(
            target,
            FakeAdapter(
                descriptor=provider,
                target=target,
                receipt=receipt,
            ),
            data_dir=tmp_path / "research-cache",
        )


def test_adapter_rejects_self_attested_noncanonical_manifest_path(
    tmp_path: Path,
) -> None:
    # Given: a same-descriptor receipt only claims expected hash and protocol fields.
    provider = _provider()
    artifact = make_self_attested_artifact(
        tmp_path / "research-cache",
        source_uri="https://evil.example/forged",
        accession="forged",
    )
    artifact.manifest_path.parent.mkdir(parents=True)
    _ = artifact.manifest_path.write_text(
        artifact.manifest.model_dump_json(),
        encoding="utf-8",
    )
    _ = artifact.content_path.write_bytes(b"x" * artifact.manifest.byte_size)
    receipt = FigshareReceipt(
        provider=provider,
        artifact=artifact,
        article_id="forged",
    )
    expected = _identity(artifact)
    target = provider_target(expected, artifact)

    # When: the noncanonical manifest path crosses the provider boundary.
    with pytest.raises(bio.ArtifactReceiptLoadError) as caught:
        _ = bio.acquire_provider_artifact(
            target,
            FakeAdapter(
                descriptor=provider,
                target=target,
                receipt=receipt,
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: claimed fields never substitute for canonical cache verification.
    assert caught.value.reason is bio.ArtifactReceiptFailure.INVALID_LAYOUT


def test_adapter_rejects_claimed_content_path_outside_verified_receipt(
    tmp_path: Path,
) -> None:
    # Given: a valid canonical manifest paired with an attacker-selected blob path.
    provider = _provider()
    verified = make_artifact(
        tmp_path,
        source_uri="https://provider.example/file/1",
        accession="provider-file-1",
    )
    claimed = ArtifactReceipt(
        manifest=verified.manifest,
        content_path=tmp_path / "evil" / "blob",
        manifest_path=verified.manifest_path,
    )
    receipt = FigshareReceipt(provider=provider, artifact=claimed, article_id="1")
    expected = _identity(verified)
    target = provider_target(expected, verified)

    # When: the claimed path is compared with the canonically reopened receipt.
    with pytest.raises(bio.ProviderReceiptIntegrityMismatchError):
        _ = bio.acquire_provider_artifact(
            target,
            FakeAdapter(
                descriptor=provider,
                target=target,
                receipt=receipt,
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: a valid manifest cannot authorize an unrelated content path.


def test_adapter_rejects_canonical_receipt_outside_requested_cache_root(
    tmp_path: Path,
) -> None:
    # Given: a valid canonical receipt stored outside the requested data directory.
    provider = _provider()
    artifact = make_artifact(
        tmp_path / "outside",
        source_uri="https://provider.example/file/1",
        accession="provider-file-1",
    )
    receipt = FigshareReceipt(provider=provider, artifact=artifact, article_id="1")
    expected = _identity(artifact)
    target = provider_target(expected, artifact)

    # When: the valid receipt is presented for another caller-owned cache root.
    with pytest.raises(bio.ProviderReceiptCacheRootMismatchError):
        _ = bio.acquire_provider_artifact(
            target,
            FakeAdapter(
                descriptor=provider,
                target=target,
                receipt=receipt,
            ),
            data_dir=tmp_path / "research-cache",
        )

    # Then: canonical layout alone cannot escape the requested cache root.


def test_adapter_rejects_forged_source_against_native_request(tmp_path: Path) -> None:
    # Given: valid bytes whose canonical manifest source was changed after acquisition.
    provider = _provider()
    verified = make_artifact(
        tmp_path,
        source_uri="https://provider.example/file/1",
        accession="provider-file-1",
    )
    expectation = artifact_expectation(verified)
    forged_manifest = verified.manifest.model_copy(
        update={"source_uri": "https://evil.example/forged"}
    )
    _ = verified.manifest_path.write_text(
        forged_manifest.model_dump_json(),
        encoding="utf-8",
    )
    forged = replace(verified, manifest=forged_manifest)
    receipt = FigshareReceipt(provider=provider, artifact=forged, article_id="1")
    expected = _identity(verified)
    target = bio.ProviderAcquisitionTarget(
        scientific_identity=expected,
        artifact_expectation=expectation,
    )

    # When: verified content is compared with the adapter's native request metadata.
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

    # Then: content integrity alone cannot relabel acquisition provenance.


def test_adapter_rejects_forged_manifest_size(tmp_path: Path) -> None:
    # Given: one canonical receipt whose declared byte size was modified.
    artifact = make_artifact(
        tmp_path,
        source_uri="https://provider.example/file/1",
        accession="provider-file-1",
    )
    forged_manifest = artifact.manifest.model_copy(update={"byte_size": 999})
    _ = artifact.manifest_path.write_text(
        forged_manifest.model_dump_json(),
        encoding="utf-8",
    )
    claimed = replace(artifact, manifest=forged_manifest)

    # When: the canonical receipt is reopened against its blob.
    _assert_receipt_load_fails(tmp_path, artifact, claimed)

    # Then: the forged size is rejected before provider identity is constructed.


def test_adapter_rejects_forged_blob(tmp_path: Path) -> None:
    # Given: one canonical receipt whose blob bytes were modified.
    artifact = make_artifact(
        tmp_path,
        source_uri="https://provider.example/file/1",
        accession="provider-file-1",
    )
    _ = artifact.content_path.write_bytes(b"forged blob")

    # When: the canonical receipt is reopened and streamed from disk.
    _assert_receipt_load_fails(tmp_path, artifact, artifact)

    # Then: the forged blob is rejected before provider identity is constructed.
