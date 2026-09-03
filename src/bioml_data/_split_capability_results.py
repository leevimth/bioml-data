"""Capability query result types separated from split contract declarations."""

from dataclasses import dataclass
from typing import override

from bioml_data._dataset_definition import UnsupportedSplitProtocolError
from bioml_data._domain import (
    DatasetSnapshotIdentity,
    ProtocolId,
    TaskId,
    parse_protocol_id,
)
from bioml_data._split_capability_models import (
    SplitCapability,
    SplitCapabilityAvailability,
)


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
        """Return no capability for the unassessed scope."""

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
