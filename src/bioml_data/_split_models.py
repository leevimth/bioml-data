"""Immutable data contracts for deterministic split assignment."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import NewType

from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId

AssignmentIdentity = NewType("AssignmentIdentity", str)
GroupId = NewType("GroupId", str)
MetadataColumn = NewType("MetadataColumn", str)
ObservationId = NewType("ObservationId", str)


@unique
class SplitPartition(StrEnum):
    """Benchmark partition assigned to an observation."""

    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class MetadataValue:
    """One canonical metadata value supplied by a dataset adapter."""

    column: MetadataColumn
    value: str


@dataclass(frozen=True, slots=True)
class SplitObservation:
    """Stable observation identity plus canonical split metadata."""

    observation_id: ObservationId
    metadata: tuple[MetadataValue, ...]


@dataclass(frozen=True, slots=True)
class SplitAssignment:
    """Partition membership for one observation and biological group."""

    observation_id: ObservationId
    group: GroupId
    partition: SplitPartition


@dataclass(frozen=True, slots=True)
class PartitionGroupCounts:
    """Group counts for train, validation, and test partitions."""

    train: int
    validation: int
    test: int


@dataclass(frozen=True, slots=True)
class PartitionFractions:
    """Requested partition fractions embedded in a versioned protocol."""

    train: float
    validation: float
    test: float


@dataclass(frozen=True, slots=True)
class SplitAssignmentReceipt:
    """Reproducible identity and realized allocation for one assignment."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId
    seed: int
    assignment_identity: AssignmentIdentity
    assignments: tuple[SplitAssignment, ...]
    requested_group_fractions: PartitionFractions
    realized_group_counts: PartitionGroupCounts
    observation_count: int
    group_count: int
