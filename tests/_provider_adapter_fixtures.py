"""Shared typed fixtures for provider adapter boundary tests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import bioml_data as bio
from bioml_data._artifacts import (
    ArtifactDerivation,
    ArtifactId,
    ArtifactManifest,
    ArtifactReceipt,
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
    scientific_identity: bio.ScientificArtifactIdentity
    receipt: ReceiptT

    def acquire(self, *, data_dir: Path) -> ReceiptT:
        assert data_dir.name == "research-cache"
        return self.receipt


def make_artifact(
    tmp_path: Path,
    *,
    source_uri: str,
    accession: str,
    digest: str = "a" * 64,
    transform_protocol: str = "canonical-single-cell-v1",
) -> ArtifactReceipt:
    """Build a provider-specific manifest for one canonical fixture artifact."""
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
            transform_protocol=TransformProtocolId(transform_protocol),
        ),
    )
    return ArtifactReceipt(
        manifest=manifest,
        content_path=tmp_path / accession / "blob",
        manifest_path=tmp_path / accession / "manifest.json",
    )
