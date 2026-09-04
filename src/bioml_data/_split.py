"""Deterministic grouped split assignment."""

from dataclasses import dataclass, replace
from enum import StrEnum, unique
from hashlib import sha256
from typing import NewType, override

from bioml_data._domain import (
    DatasetSnapshotIdentity,
    ProtocolId,
    TaskId,
)
from bioml_data._group_held_out_rules import (
    GROUP_HELD_OUT_ALLOCATION_RULE,
    group_held_out_partition_counts,
    ordered_group_ids,
)
from bioml_data._split_capability import (
    SplitCapability,
    SplitCapabilityQuery,
    query_split_capability,
)

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


@dataclass(frozen=True, slots=True)
class MissingSplitProtocolError(Exception):
    """Raised when a caller explicitly provides no split protocol."""

    dataset: DatasetSnapshotIdentity
    task: TaskId

    @override
    def __str__(self) -> str:
        return f"split protocol required for {self.dataset!r}, task {self.task!r}"


@dataclass(frozen=True, slots=True)
class InsufficientSplitMetadataError(Exception):
    """Raised when an observation lacks metadata required by a protocol."""

    observation_id: ObservationId
    missing_columns: tuple[str, ...]

    @override
    def __str__(self) -> str:
        return (
            f"observation {self.observation_id!r} lacks split metadata "
            f"{self.missing_columns!r}"
        )


@dataclass(frozen=True, slots=True)
class InsufficientSplitGroupsError(Exception):
    """Raised when non-empty benchmark partitions cannot be constructed."""

    group_count: int
    required_group_count: int

    @override
    def __str__(self) -> str:
        return (
            f"split needs {self.required_group_count} groups; "
            f"received {self.group_count}"
        )


@dataclass(frozen=True, slots=True)
class SplitAssigner:
    """Assign adapter observations through an explicitly selected protocol."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    observations: tuple[SplitObservation, ...]

    def split(
        self,
        *,
        protocol: str | None,
        seed: int,
    ) -> SplitAssignmentReceipt:
        """Assign whole biological groups and return a reproducibility receipt."""
        if protocol is None:
            raise MissingSplitProtocolError(dataset=self.dataset, task=self.task)
        result = query_split_capability(
            SplitCapabilityQuery(
                dataset=self.dataset,
                task=self.task,
                protocol=protocol,
            )
        )
        return _assign(self, capability=result.require_supported(), seed=seed)


def _assign(
    assigner: SplitAssigner,
    *,
    capability: SplitCapability,
    seed: int,
) -> SplitAssignmentReceipt:
    grouped = tuple(
        (observation, _group_for(observation, capability=capability))
        for observation in assigner.observations
    )
    groups = ordered_group_ids(tuple(str(group) for _, group in grouped), seed=seed)
    counts = _realized_counts(len(groups))
    train_end = counts.train
    validation_end = train_end + counts.validation
    partition_by_group = (
        dict.fromkeys(groups[:train_end], SplitPartition.TRAIN)
        | dict.fromkeys(
            groups[train_end:validation_end],
            SplitPartition.VALIDATION,
        )
        | dict.fromkeys(groups[validation_end:], SplitPartition.TEST)
    )
    assignments = tuple(
        sorted(
            (
                SplitAssignment(
                    observation_id=observation.observation_id,
                    group=group,
                    partition=partition_by_group[group],
                )
                for observation, group in grouped
            ),
            key=lambda assignment: assignment.observation_id,
        )
    )
    receipt = SplitAssignmentReceipt(
        dataset=assigner.dataset,
        task=assigner.task,
        protocol=capability.protocol,
        seed=seed,
        assignment_identity=AssignmentIdentity(""),
        assignments=assignments,
        requested_group_fractions=PartitionFractions(
            train=(
                GROUP_HELD_OUT_ALLOCATION_RULE.train_weight
                / GROUP_HELD_OUT_ALLOCATION_RULE.total_weight
            ),
            validation=(
                GROUP_HELD_OUT_ALLOCATION_RULE.validation_weight
                / GROUP_HELD_OUT_ALLOCATION_RULE.total_weight
            ),
            test=(
                GROUP_HELD_OUT_ALLOCATION_RULE.test_weight
                / GROUP_HELD_OUT_ALLOCATION_RULE.total_weight
            ),
        ),
        realized_group_counts=counts,
        observation_count=len(assignments),
        group_count=len(groups),
    )
    return replace(
        receipt,
        assignment_identity=assignment_receipt_identity(receipt),
    )


def assignment_receipt_identity(
    receipt: SplitAssignmentReceipt,
) -> AssignmentIdentity:
    """Recompute the deterministic identity covering receipt headers and rows."""
    header = (
        f"{receipt.dataset.name}\0{receipt.dataset.version}\0{receipt.task}\0"
        f"{receipt.protocol}\0{receipt.seed}"
    )
    rows = "".join(
        f"\0{item.observation_id}\0{item.group}\0{item.partition}"
        for item in receipt.assignments
    )
    return AssignmentIdentity(sha256(f"{header}{rows}".encode()).hexdigest())


def _group_for(
    observation: SplitObservation,
    *,
    capability: SplitCapability,
) -> GroupId:
    values = tuple(
        item.value
        for item in observation.metadata
        if item.column == capability.grouping_column
    )
    if not values:
        raise InsufficientSplitMetadataError(
            observation_id=observation.observation_id,
            missing_columns=(capability.grouping_column,),
        )
    return GroupId(values[0])


def _realized_counts(group_count: int) -> PartitionGroupCounts:
    rule = GROUP_HELD_OUT_ALLOCATION_RULE
    if group_count < rule.minimum_group_count:
        raise InsufficientSplitGroupsError(
            group_count=group_count,
            required_group_count=rule.minimum_group_count,
        )
    counts = group_held_out_partition_counts(group_count)
    return PartitionGroupCounts(
        train=counts.train,
        validation=counts.validation,
        test=counts.test,
    )
