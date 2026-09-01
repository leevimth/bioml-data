"""Typed boundary between provider acquisition and scientific protocols."""

from dataclasses import dataclass
from pathlib import Path
from typing import NewType, Protocol, override

from bioml_data._artifact_receipts import load_artifact_receipt
from bioml_data._artifacts import (
    ArtifactDerivation,
    ArtifactId,
    ArtifactReceipt,
    TransformProtocolId,
)
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


@dataclass(frozen=True, slots=True)
class ProviderArtifactExpectation:
    """Immutable provider-native request metadata expected after acquisition."""

    logical_name: str
    source_uri: str
    accession: str
    release: str
    byte_size: int
    sha256: str
    derivation: ArtifactDerivation | None


@dataclass(frozen=True, slots=True)
class ProviderAcquisitionTarget:
    """Caller-requested scientific identity and provider-native artifact pin."""

    scientific_identity: ScientificArtifactIdentity
    artifact_expectation: ProviderArtifactExpectation


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
    def target(self) -> ProviderAcquisitionTarget:
        """Return the exact caller-requestable target bound by this adapter."""
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

    expected: ProviderAcquisitionTarget
    actual: ProviderAcquisitionTarget

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


@dataclass(frozen=True, slots=True)
class ProviderReceiptIntegrityMismatchError(Exception):
    """Raised when receipt paths or manifest differ after canonical reopening."""

    claimed: ArtifactReceipt
    verified: ArtifactReceipt

    @override
    def __str__(self) -> str:
        return "provider receipt differs from its verified canonical cache receipt"


@dataclass(frozen=True, slots=True)
class ProviderReceiptCacheRootMismatchError(Exception):
    """Raised when a receipt escapes the caller-selected acquisition root."""

    cache_root: Path
    manifest_path: Path

    @override
    def __str__(self) -> str:
        return f"provider receipt {self.manifest_path} is outside {self.cache_root}"


@dataclass(frozen=True, slots=True)
class ProviderArtifactProvenanceMismatchError(Exception):
    """Raised when verified artifact metadata differs from the native request."""

    expected: ProviderArtifactExpectation
    actual: ProviderArtifactExpectation

    @override
    def __str__(self) -> str:
        return f"provider artifact provenance {self.actual!r} != {self.expected!r}"


def acquire_provider_artifact[ReceiptT: ProviderAcquisitionReceipt](
    expected: ProviderAcquisitionTarget,
    adapter: ProviderAdapter[ReceiptT],
    *,
    data_dir: Path,
) -> ResolvedProviderArtifact[ReceiptT]:
    """Acquire through one explicit adapter and expose both identity layers."""
    adapter_target = adapter.target
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
    cache_root = data_dir.resolve()
    manifest_path = receipt.artifact.manifest_path.resolve()
    if not manifest_path.is_relative_to(cache_root):
        raise ProviderReceiptCacheRootMismatchError(
            cache_root=cache_root,
            manifest_path=manifest_path,
        )
    verified = load_artifact_receipt(receipt.artifact.manifest_path)
    if verified != receipt.artifact:
        raise ProviderReceiptIntegrityMismatchError(
            claimed=receipt.artifact,
            verified=verified,
        )
    manifest = verified.manifest
    actual_expectation = ProviderArtifactExpectation(
        logical_name=manifest.logical_name,
        source_uri=manifest.source_uri,
        accession=manifest.accession,
        release=manifest.release,
        byte_size=manifest.byte_size,
        sha256=manifest.sha256,
        derivation=manifest.derivation,
    )
    if actual_expectation != expected.artifact_expectation:
        raise ProviderArtifactProvenanceMismatchError(
            expected=expected.artifact_expectation,
            actual=actual_expectation,
        )
    derivation = manifest.derivation
    transform_protocol = None if derivation is None else derivation.transform_protocol
    actual = ScientificArtifactIdentity(
        dataset=expected.scientific_identity.dataset,
        artifact_id=verified.artifact_id,
        transform_protocol=transform_protocol,
    )
    if actual != expected.scientific_identity:
        raise ProviderArtifactIdentityMismatchError(
            expected=expected.scientific_identity,
            actual=actual,
        )
    return ResolvedProviderArtifact(
        identity=expected.scientific_identity,
        receipt=receipt,
    )


__all__ = [
    "ProviderAcquisitionReceipt",
    "ProviderAcquisitionTarget",
    "ProviderAdapter",
    "ProviderArtifactExpectation",
    "ProviderArtifactIdentityMismatchError",
    "ProviderArtifactProvenanceMismatchError",
    "ProviderDescriptor",
    "ProviderId",
    "ProviderReceiptCacheRootMismatchError",
    "ProviderReceiptIntegrityMismatchError",
    "ProviderReceiptMismatchError",
    "ProviderTargetMismatchError",
    "ResolvedProviderArtifact",
    "ScientificArtifactIdentity",
    "acquire_provider_artifact",
]
