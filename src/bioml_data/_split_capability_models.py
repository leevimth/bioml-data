"""Typed outcomes for dataset-specific split capability evidence."""

from dataclasses import dataclass, field
from enum import StrEnum, unique
from typing import override

from bioml_data._artifact_types import ArtifactId, TransformProtocolId
from bioml_data._domain import (
    DatasetSnapshotIdentity,
    ProtocolId,
    SplitEvidenceBasis,
    SplitProtocolCompatibilityRoleError,
    SplitProtocolRole,
    SplitStrategy,
    TaskId,
    UnsupportedSplitProtocolError,
    parse_protocol_id,
)


@unique
class SplitEvidenceType(StrEnum):
    """Deprecated evidence-type vocabulary retained for reader compatibility."""

    LITERATURE_REUSE = "literature_reuse"
    COMPARATIVE_EVIDENCE = "comparative_evidence"
    PRODUCT_PROTOCOL = "product_protocol"


@unique
class SplitCapabilityAvailability(StrEnum):
    """Assessment state independent of protocol role or audit result."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SplitArtifactScope:
    """Exact raw artifact and transform to which split evidence applies."""

    source_artifact: ArtifactId
    transform_protocol: TransformProtocolId

    @property
    def parent_artifacts(self) -> tuple[ArtifactId, ...]:
        """Return the exact ordered derivation parents required by this scope."""
        return (self.source_artifact,)


@dataclass(frozen=True, slots=True)
class SplitEvidenceScope:
    """Scientific scope preventing evidence reuse across incompatible contracts."""

    dataset: DatasetSnapshotIdentity
    artifact: SplitArtifactScope
    task: TaskId
    protocol: ProtocolId


@dataclass(frozen=True, slots=True)
class SplitEvidenceCitation:
    """Human-readable provenance for a split-role claim."""

    title: str
    uri: str


@dataclass(frozen=True, slots=True)
class SplitProtocolEvidence:
    """One evidence-basis claim, its source, and its interpretation limits."""

    scope: SplitEvidenceScope
    role: SplitProtocolRole | None
    evidence_type: SplitEvidenceType | None
    citations: tuple[SplitEvidenceCitation, ...]
    fit_scope: str
    leakage_caveat: str
    basis: SplitEvidenceBasis | None = None

    def __post_init__(self) -> None:
        """Keep active evidence basis records free of legacy role claims."""
        if self.basis is not None and self.role is not None:
            raise SplitProtocolCompatibilityRoleError(
                protocol=self.scope.protocol,
                role=self.role,
            )


@dataclass(frozen=True, slots=True)
class SplitCapability:
    """Machine-readable contract for one supported split protocol."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId
    role: SplitProtocolRole | None
    evidence_type: SplitEvidenceType | None
    artifact: SplitArtifactScope
    evidence: tuple[SplitProtocolEvidence, ...]
    held_out_axis: str
    leakage_unit: str
    required_columns: tuple[str, ...]
    grouping_column: str
    basis: SplitEvidenceBasis | None = None
    strategy: SplitStrategy | None = None
    evaluation_target: str = ""
    is_canary: bool = False
    _role_is_projection: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Project legacy capability role reads from separate canary usage."""
        if self.basis is None:
            return
        expected_role = SplitProtocolRole.CANARY if self.is_canary else None
        match self.role:
            case None:
                pass
            case SplitProtocolRole.CANARY if self._role_is_projection:
                pass
            case mismatch:
                raise SplitProtocolCompatibilityRoleError(
                    protocol=self.protocol,
                    role=mismatch,
                )
        object.__setattr__(self, "role", expected_role)
        object.__setattr__(self, "_role_is_projection", True)


@dataclass(frozen=True, slots=True)
class SplitCapabilityQuery:
    """Explicit dataset, task, and protocol capability lookup."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: str


@dataclass(frozen=True, slots=True)
class SupportedSplitCapability:
    """A declared protocol and its evidence-bearing contract."""

    capability: SplitCapability

    @property
    def availability(self) -> SplitCapabilityAvailability:
        """Return the assessed support state."""
        return SplitCapabilityAvailability.SUPPORTED

    @property
    def supported_protocols(self) -> tuple[ProtocolId, ...]:
        """Return the resolved supported protocol."""
        return (self.capability.protocol,)

    def capability_or_none(self) -> SplitCapability:
        """Return the declared capability for non-raising consumers."""
        return self.capability

    def require_supported(self) -> SplitCapability:
        """Return the declared capability."""
        return self.capability


@dataclass(frozen=True, slots=True)
class UnsupportedSplitCapability:
    """An assessed dataset/task scope without the requested protocol."""

    query: SplitCapabilityQuery
    supported_protocols: tuple[ProtocolId, ...]

    @property
    def availability(self) -> SplitCapabilityAvailability:
        """Return the assessed support state."""
        return SplitCapabilityAvailability.UNSUPPORTED

    def capability_or_none(self) -> None:
        """Return no capability for the unsupported request."""

    def require_supported(self) -> SplitCapability:
        """Raise the assessed unsupported-protocol outcome."""
        raise UnsupportedSplitProtocolError(
            dataset=self.query.dataset,
            protocol=parse_protocol_id(self.query.protocol),
            supported=self.supported_protocols,
        )


@dataclass(frozen=True, slots=True)
class UnknownSplitCapability:
    """A dataset/task scope whose capabilities have not been assessed."""

    query: SplitCapabilityQuery

    @property
    def availability(self) -> SplitCapabilityAvailability:
        """Return the unassessed support state."""
        return SplitCapabilityAvailability.UNKNOWN

    @property
    def supported_protocols(self) -> tuple[ProtocolId, ...]:
        """Return no alternatives for an unassessed scope."""
        return ()

    def capability_or_none(self) -> None:
        """Return no capability for the unassessed request."""

    def require_supported(self) -> SplitCapability:
        """Raise the unassessed-scope outcome."""
        raise UnknownSplitCapabilityError(
            dataset=self.query.dataset,
            task=self.query.task,
            protocol=parse_protocol_id(self.query.protocol),
        )


@dataclass(frozen=True, slots=True)
class UnknownSplitCapabilityError(Exception):
    """Raised when split support has not been assessed for a scope."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId

    @override
    def __str__(self) -> str:
        return f"split capability unknown for {self.dataset!r}, task {self.task!r}"


type SplitCapabilityResult = (
    SupportedSplitCapability | UnsupportedSplitCapability | UnknownSplitCapability
)
