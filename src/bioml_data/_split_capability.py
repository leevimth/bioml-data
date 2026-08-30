"""Dataset-specific split capability evidence."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Final, override

from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    SplitProtocolRole,
    TaskId,
    UnsupportedSplitProtocolError,
    parse_protocol_id,
)


@unique
class SplitEvidenceType(StrEnum):
    """Evidence supporting a protocol's declared role."""

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
class SplitCapability:
    """Machine-readable contract for one supported split protocol."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId
    role: SplitProtocolRole
    evidence_type: SplitEvidenceType
    held_out_axis: str
    leakage_unit: str
    required_columns: tuple[str, ...]
    grouping_column: str


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

_TMS_SNAPSHOT: Final = DatasetSnapshotIdentity(
    name=DatasetName("tms-aorta"),
    version=DatasetVersion("figshare-project-64982"),
)
_TMS_TASK: Final = TaskId("cell-type-annotation-v1")
_ANIMAL_HELD_OUT: Final = SplitCapability(
    dataset=_TMS_SNAPSHOT,
    task=_TMS_TASK,
    protocol=ProtocolId("animal-held-out-v1"),
    role=SplitProtocolRole.CANARY,
    evidence_type=SplitEvidenceType.PRODUCT_PROTOCOL,
    held_out_axis="animal",
    leakage_unit="mouse",
    required_columns=("cell_id", "donor_id"),
    grouping_column="donor_id",
)
_CAPABILITIES: Final = (_ANIMAL_HELD_OUT,)
_ASSESSED_SCOPES: Final = ((_TMS_SNAPSHOT, _TMS_TASK),)


def query_split_capability(query: SplitCapabilityQuery) -> SplitCapabilityResult:
    """Return supported, unsupported, or unknown without conflating the states."""
    requested = parse_protocol_id(query.protocol)
    candidates = tuple(
        capability
        for capability in _CAPABILITIES
        if capability.dataset == query.dataset and capability.task == query.task
    )
    for capability in candidates:
        if capability.protocol == requested:
            return SupportedSplitCapability(capability=capability)
    if (query.dataset, query.task) in _ASSESSED_SCOPES:
        return UnsupportedSplitCapability(
            query=query,
            supported_protocols=tuple(capability.protocol for capability in candidates),
        )
    return UnknownSplitCapability(query=query)
