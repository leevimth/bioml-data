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


@dataclass(frozen=True, slots=True)
class ScientificArtifactIdentity:
    """Provider-neutral identity consumed by scientific protocol layers."""

    dataset: DatasetSnapshotIdentity
    artifact_id: ArtifactId
    transform_protocol: TransformProtocolId | None


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

    @property
    def scientific_identity(self) -> ScientificArtifactIdentity:
        """Return the exact dataset and verified artifact this adapter serves."""
        ...

    def acquire(self, *, data_dir: Path) -> ReceiptT:
        """Acquire one pinned provider resource into a caller-owned directory."""
        ...


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


@dataclass(frozen=True, slots=True)
class ProviderTargetMismatchError(Exception):
    """Raised when an adapter is bound to another scientific target."""

    expected: ScientificArtifactIdentity
    actual: ScientificArtifactIdentity

    @override
    def __str__(self) -> str:
        return f"provider target {self.actual!r} != requested {self.expected!r}"


@dataclass(frozen=True, slots=True)
class ProviderArtifactIdentityMismatchError(Exception):
    """Raised when acquired bytes do not match the verified target."""

    expected: ScientificArtifactIdentity
    actual: ScientificArtifactIdentity

    @override
    def __str__(self) -> str:
        return f"provider artifact {self.actual!r} != requested {self.expected!r}"


def acquire_provider_artifact[ReceiptT: ProviderAcquisitionReceipt](
    expected: ScientificArtifactIdentity,
    adapter: ProviderAdapter[ReceiptT],
    *,
    data_dir: Path,
) -> ResolvedProviderArtifact[ReceiptT]:
    """Acquire through one explicit adapter and expose both identity layers."""
    adapter_target = adapter.scientific_identity
    if adapter_target != expected:
        raise ProviderTargetMismatchError(
            expected=expected,
            actual=adapter_target,
        )
    receipt = adapter.acquire(data_dir=data_dir)
    if receipt.provider != adapter.descriptor:
        raise ProviderReceiptMismatchError(
            expected=adapter.descriptor,
            actual=receipt.provider,
        )
    derivation = receipt.artifact.manifest.derivation
    transform_protocol = None if derivation is None else derivation.transform_protocol
    actual = ScientificArtifactIdentity(
        dataset=expected.dataset,
        artifact_id=receipt.artifact.artifact_id,
        transform_protocol=transform_protocol,
    )
    if actual != expected:
        raise ProviderArtifactIdentityMismatchError(
            expected=expected,
            actual=actual,
        )
    return ResolvedProviderArtifact(
        identity=expected,
        receipt=receipt,
    )


__all__ = [
    "ProviderAcquisitionReceipt",
    "ProviderAdapter",
    "ProviderArtifactIdentityMismatchError",
    "ProviderDescriptor",
    "ProviderId",
    "ProviderReceiptMismatchError",
    "ProviderTargetMismatchError",
    "ResolvedProviderArtifact",
    "ScientificArtifactIdentity",
    "acquire_provider_artifact",
]
