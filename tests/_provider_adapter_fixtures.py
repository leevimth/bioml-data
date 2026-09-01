"""Shared typed fixtures for provider adapter boundary tests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import bioml_data as bio
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactId,
    ArtifactManifest,
    ArtifactReceipt,
    ArtifactRequest,
    TransformProtocolId,
)


@dataclass(frozen=True, slots=True)
class FigshareReceipt:
    provider: bio.ProviderDescriptor
    artifact: ArtifactReceipt
    article_id: str


@dataclass(frozen=True, slots=True)
class HubReceipt:
    provider: bio.ProviderDescriptor
    artifact: ArtifactReceipt
    object_key: str


@dataclass(frozen=True, slots=True)
class FakeAdapter[ReceiptT: bio.ProviderAcquisitionReceipt]:
    descriptor: bio.ProviderDescriptor
    target: bio.ProviderAcquisitionTarget
    receipt: ReceiptT

    def acquire(self, *, data_dir: Path) -> ReceiptT:
        assert data_dir.name == "research-cache"
        return self.receipt


def make_artifact(
    tmp_path: Path,
    *,
    source_uri: str,
    accession: str,
    content: bytes = b"canonical fixture",
    transform_protocol: str = "canonical-single-cell-v1",
) -> ArtifactReceipt:
    """Store a provider-specific canonical fixture artifact."""
    digest = sha256(content).hexdigest()
    derivation = ArtifactDerivation(
        parent_artifacts=(ArtifactId("sha256:" + "b" * 64),),
        transform_protocol=TransformProtocolId(transform_protocol),
    )
    return ArtifactCache(tmp_path / "research-cache" / accession).store(
        ArtifactRequest(
            logical_name="canonical.h5ad",
            source_uri=source_uri,
            accession=accession,
            release="2026-09-01",
            retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
            expected_byte_size=len(content),
            expected_sha256=digest,
            tool_version="provider-fixture/1",
            derivation=derivation,
        ),
        (content,),
    )


def make_self_attested_artifact(
    tmp_path: Path,
    *,
    source_uri: str,
    accession: str,
) -> ArtifactReceipt:
    """Build claimed receipt fields without canonical cache evidence."""
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


def artifact_expectation(
    artifact: ArtifactReceipt,
) -> bio.ProviderArtifactExpectation:
    """Project a verified fixture manifest into its adapter request metadata."""
    manifest = artifact.manifest
    return bio.ProviderArtifactExpectation(
        logical_name=manifest.logical_name,
        source_uri=manifest.source_uri,
        accession=manifest.accession,
        release=manifest.release,
        byte_size=manifest.byte_size,
        sha256=manifest.sha256,
        derivation=manifest.derivation,
    )


def provider_target(
    identity: bio.ScientificArtifactIdentity,
    artifact: ArtifactReceipt,
) -> bio.ProviderAcquisitionTarget:
    """Bind one scientific identity to its provider-native fixture request."""
    return bio.ProviderAcquisitionTarget(
        scientific_identity=identity,
        artifact_expectation=artifact_expectation(artifact),
    )
