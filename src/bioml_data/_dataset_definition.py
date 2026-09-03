"""Dataset definitions and split-planning outcomes."""

from dataclasses import dataclass
from typing import override

from bioml_data._domain import (
    DatasetLifecycle,
    DatasetSnapshotIdentity,
    ProtocolId,
    SourceReference,
    SplitProtocolDefinition,
    TaskDefinition,
    TaskId,
    parse_protocol_id,
    parse_task_id,
)


@dataclass(frozen=True, slots=True)
class SplitPlan:
    """Resolved identities required before split assignment is materialized."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId


@dataclass(frozen=True, slots=True)
class UnknownTaskError(Exception):
    """Raised when a task is absent from a dataset definition."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    available: tuple[TaskId, ...]

    @override
    def __str__(self) -> str:
        return f"unknown task {self.task!r} for {self.dataset!r}"


@dataclass(frozen=True, slots=True)
class UnsupportedSplitProtocolError(Exception):
    """Raised when a split protocol is not declared for a dataset task."""

    dataset: DatasetSnapshotIdentity
    protocol: ProtocolId
    supported: tuple[ProtocolId, ...]

    @override
    def __str__(self) -> str:
        return f"unsupported split protocol {self.protocol!r} for {self.dataset!r}"


@dataclass(frozen=True, slots=True)
class DatasetDefinition:
    """Immutable dataset contract available before artifact materialization."""

    snapshot: DatasetSnapshotIdentity
    source: SourceReference
    lifecycle: DatasetLifecycle
    tasks: tuple[TaskDefinition, ...]
    supported_splits: tuple[SplitProtocolDefinition, ...]

    def plan_split(self, *, task: str, protocol: str) -> SplitPlan:
        """Resolve an explicit task and split protocol without assigning rows."""
        task_id = parse_task_id(task)
        available_tasks = tuple(definition.id for definition in self.tasks)
        if task_id not in available_tasks:
            raise UnknownTaskError(
                dataset=self.snapshot,
                task=task_id,
                available=available_tasks,
            )

        protocol_id = parse_protocol_id(protocol)
        supported = tuple(
            definition.id
            for definition in self.supported_splits
            if definition.task == task_id
        )
        if protocol_id not in supported:
            raise UnsupportedSplitProtocolError(
                dataset=self.snapshot,
                protocol=protocol_id,
                supported=supported,
            )
        return SplitPlan(dataset=self.snapshot, task=task_id, protocol=protocol_id)
