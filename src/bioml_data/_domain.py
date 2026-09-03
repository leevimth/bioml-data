"""Immutable dataset protocol contracts."""

from dataclasses import dataclass, field
from enum import StrEnum, unique
from typing import NewType, override

DatasetName = NewType("DatasetName", str)
DatasetVersion = NewType("DatasetVersion", str)
ProtocolId = NewType("ProtocolId", str)
SourceUri = NewType("SourceUri", str)
TaskId = NewType("TaskId", str)


@unique
class DatasetLifecycle(StrEnum):
    """Implementation state of a built-in dataset definition."""

    PLANNED = "planned"
    SUPPORTED = "supported"


@unique
class SplitProtocolRole(StrEnum):
    """Deprecated evidence-role vocabulary retained for reader compatibility."""

    CANARY = "canary"
    COMMUNITY_REFERENCE = "community_reference"
    LITERATURE_REFERENCE = "literature_reference"
    REFERENCE = "reference"
    ROBUSTNESS = "robustness"


@unique
class SplitEvidenceBasis(StrEnum):
    """External or package source that justifies publishing a split."""

    LITERATURE_REFERENCE = "literature_reference"
    COMMUNITY_REFERENCE = "community_reference"
    PACKAGE_DEFINED = "package_defined"


@unique
class SplitStrategy(StrEnum):
    """Concrete partitioning strategy independently of evidence source."""

    GROUP_HELD_OUT = "group-held-out"
    LEAVE_ONE_STUDY_OUT = "leave-one-study-out"


@dataclass(frozen=True, slots=True)
class DatasetSnapshotIdentity:
    """Immutable catalog identity for one upstream dataset snapshot."""

    name: DatasetName
    version: DatasetVersion


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Stable upstream reference known before artifact download."""

    uri: SourceUri


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    """Learning problem selected from a dataset snapshot."""

    id: TaskId
    prediction_unit: str
    target: str


@dataclass(frozen=True, slots=True)
class SplitProtocolCompatibilityRoleError(Exception):
    """Raised when new split semantics conflict with a legacy role input."""

    protocol: ProtocolId
    role: SplitProtocolRole

    @override
    def __str__(self) -> str:
        return (
            f"legacy split role {self.role.value!r} conflicts with active "
            f"semantics for {self.protocol!r}"
        )


@dataclass(frozen=True, slots=True)
class SplitProtocolDefinition:
    """A versioned split contract supported by a dataset task."""

    id: ProtocolId
    role: SplitProtocolRole | None
    task: TaskId
    required_metadata: tuple[str, ...]
    basis: SplitEvidenceBasis | None = None
    strategy: SplitStrategy | None = None
    held_out_axis: str = ""
    leakage_unit: str = ""
    grouping_column: str = ""
    evaluation_target: str = ""
    is_canary: bool = False
    _role_is_projection: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Project legacy role reads from separate canary usage."""
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
                    protocol=self.id,
                    role=mismatch,
                )
        object.__setattr__(self, "role", expected_role)
        object.__setattr__(self, "_role_is_projection", True)


@dataclass(frozen=True, slots=True)
class SplitPlan:
    """Resolved identities required before split assignment is materialized."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId


@dataclass(frozen=True, slots=True)
class CatalogKeyError(Exception):
    """Raised when a public catalog key is empty after normalization."""

    field: str

    @override
    def __str__(self) -> str:
        return f"{self.field} must not be empty"


@dataclass(frozen=True, slots=True)
class UnknownDatasetError(Exception):
    """Raised when a dataset key is absent from the built-in catalog."""

    name: DatasetName
    available: tuple[DatasetName, ...]

    @override
    def __str__(self) -> str:
        return f"unknown dataset {self.name!r}; available: {self.available!r}"


@dataclass(frozen=True, slots=True)
class UnknownDatasetVersionError(Exception):
    """Raised when a dataset exists but the requested version does not."""

    name: DatasetName
    requested: DatasetVersion
    available: tuple[DatasetVersion, ...]

    @override
    def __str__(self) -> str:
        return (
            f"unknown version {self.requested!r} for {self.name!r}; "
            f"available: {self.available!r}"
        )


@dataclass(frozen=True, slots=True)
class DatasetVersionRequiredError(Exception):
    """Raised when a dataset has several versions and none was requested."""

    name: DatasetName
    available: tuple[DatasetVersion, ...]

    @override
    def __str__(self) -> str:
        return f"version required for {self.name!r}; available: {self.available!r}"


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


def parse_dataset_name(raw: str) -> DatasetName:
    """Normalize a public dataset key once at the package boundary."""
    return DatasetName(_normalized_key(raw, field="dataset name"))


def parse_dataset_version(raw: str) -> DatasetVersion:
    """Normalize a public dataset version once at the package boundary."""
    return DatasetVersion(_normalized_key(raw, field="dataset version"))


def parse_protocol_id(raw: str) -> ProtocolId:
    """Normalize a public split protocol identifier."""
    return ProtocolId(_normalized_key(raw, field="protocol id"))


def parse_task_id(raw: str) -> TaskId:
    """Normalize a public task identifier."""
    return TaskId(_normalized_key(raw, field="task id"))


def _normalized_key(raw: str, *, field: str) -> str:
    normalized = raw.strip().lower()
    if not normalized:
        raise CatalogKeyError(field=field)
    return normalized
