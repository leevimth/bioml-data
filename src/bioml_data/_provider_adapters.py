"""Typed boundary between provider acquisition and scientific protocols."""

from dataclasses import dataclass
from pathlib import Path
from typing import NewType, Protocol, override

from bioml_data._artifacts import ArtifactId, ArtifactReceipt, TransformProtocolId
from bioml_data._domain import DatasetSnapshotIdentity

ProviderId = NewType("ProviderId", str)


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Static identity and dependency boundary for one acquisition provider."""

    id: ProviderId
    adapter_version: str
    optional_dependency: str | None


class ProviderAcquisitionReceipt(Protocol):
    """Common surface implemented by provider-native receipt types."""

    @property
    def provider(self) -> ProviderDescriptor:
        """Return the provider implementation that produced this receipt."""
        ...

    @property
    def artifact(self) -> ArtifactReceipt:
        """Return the verified local artifact without hiding native fields."""
        ...


class ProviderAdapter[ReceiptT: ProviderAcquisitionReceipt](Protocol):
    """Explicit provider adapter; adapters are passed directly, never discovered."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        """Return this adapter's static provider descriptor."""
        ...

    def acquire(self, *, data_dir: Path) -> ReceiptT:
        """Acquire one pinned provider resource into a caller-owned directory."""
        ...


@dataclass(frozen=True, slots=True)
class ScientificArtifactIdentity:
    """Provider-neutral identity consumed by scientific protocol layers."""

    dataset: DatasetSnapshotIdentity
    artifact_id: ArtifactId
    transform_protocol: TransformProtocolId | None


@dataclass(frozen=True, slots=True)
class ResolvedProviderArtifact[ReceiptT: ProviderAcquisitionReceipt]:
    """Provider-native provenance paired with a provider-neutral identity."""

    identity: ScientificArtifactIdentity
    receipt: ReceiptT


@dataclass(frozen=True, slots=True)
class ProviderReceiptMismatchError(Exception):
    """Raised when an adapter reports a receipt owned by another provider."""

    expected: ProviderDescriptor
    actual: ProviderDescriptor

    @override
    def __str__(self) -> str:
        return f"provider receipt {self.actual!r} != adapter {self.expected!r}"


def acquire_provider_artifact[ReceiptT: ProviderAcquisitionReceipt](
    dataset: DatasetSnapshotIdentity,
    adapter: ProviderAdapter[ReceiptT],
    *,
    data_dir: Path,
) -> ResolvedProviderArtifact[ReceiptT]:
    """Acquire through one explicit adapter and expose both identity layers."""
    receipt = adapter.acquire(data_dir=data_dir)
    if receipt.provider != adapter.descriptor:
        raise ProviderReceiptMismatchError(
            expected=adapter.descriptor,
            actual=receipt.provider,
        )
    derivation = receipt.artifact.manifest.derivation
    transform_protocol = None if derivation is None else derivation.transform_protocol
    return ResolvedProviderArtifact(
        identity=ScientificArtifactIdentity(
            dataset=dataset,
            artifact_id=receipt.artifact.artifact_id,
            transform_protocol=transform_protocol,
        ),
        receipt=receipt,
    )


__all__ = [
    "ProviderAcquisitionReceipt",
    "ProviderAdapter",
    "ProviderDescriptor",
    "ProviderId",
    "ProviderReceiptMismatchError",
    "ResolvedProviderArtifact",
    "ScientificArtifactIdentity",
    "acquire_provider_artifact",
]
