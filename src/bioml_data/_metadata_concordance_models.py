"""Immutable, publication-scoped metadata concordance contracts."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import NewType, override

from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId
from bioml_data._split_capability_models import SplitArtifactScope

MetadataFoldId = NewType("MetadataFoldId", str)


@unique
class MetadataExpectationKind(StrEnum):
    """Evidence precision explicitly supported by metadata comparisons."""

    EXACT = "exact"
    RANGE = "range"
    APPROXIMATE = "approximate"
    SET = "set"
    NOT_REPORTED = "not_reported"


@unique
class MetadataMetric(StrEnum):
    """Canonical prepared-dataset metadata that can be compared safely."""

    OBSERVATION_COUNT = "observation_count"
    FEATURE_COUNT = "feature_count"
    STUDY_IDS = "study_ids"
    DONOR_IDS = "donor_ids"
    GROUP_IDS = "group_ids"
    LABEL_VALUES = "label_values"
    ASSAY_VALUES = "assay_values"
    TISSUE_VALUES = "tissue_values"
    LABEL_COUNTS = "label_counts"
    OBSERVATIONS_PER_GROUP = "observations_per_group"


@unique
class MetadataConcordance(StrEnum):
    """Outcome of comparing an observation with scoped external evidence."""

    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_REPORTED = "not_reported"


@dataclass(frozen=True, slots=True)
class MetadataCitation:
    """One human-verifiable source for a metadata expectation."""

    title: str
    uri: str

    def __post_init__(self) -> None:
        """Reject empty citations before they become an evidence claim."""
        if not self.title.strip() or not self.uri.startswith("https://"):
            raise InvalidMetadataExpectationError(
                detail="citation must be non-empty HTTPS"
            )


@dataclass(frozen=True, slots=True)
class MetadataExpectationScope:
    """Exact scientific scope that prevents metadata evidence substitution."""

    dataset: DatasetSnapshotIdentity
    artifact: SplitArtifactScope
    task: TaskId
    protocol: ProtocolId
    citation: MetadataCitation


@dataclass(frozen=True, slots=True)
class MetadataCount:
    """One stable category and its observed cardinality."""

    value: str
    count: int

    def __post_init__(self) -> None:
        """Keep categorical distributions deterministic and non-negative."""
        if not self.value.strip() or self.count < 0:
            raise InvalidMetadataExpectationError(
                detail="metadata counts need a non-empty value and non-negative count"
            )


@dataclass(frozen=True, slots=True)
class InvalidMetadataExpectationError(Exception):
    """Raised when an evidence declaration has no sound comparison meaning."""

    detail: str

    @override
    def __str__(self) -> str:
        return f"invalid metadata expectation: {self.detail}"


@dataclass(frozen=True, slots=True)
class MetadataExpectationScopeMismatchError(Exception):
    """Raised when evidence does not name the exact prepared-data scope."""

    field: str
    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        return (
            f"metadata expectation scope mismatch for {self.field}: "
            f"expected {self.expected!r}, received {self.actual!r}"
        )


@unique
class MetadataPartitionViolation(StrEnum):
    """Structural partition defects that preclude a complete comparison."""

    COVERAGE = "coverage"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    DATASET = "dataset"
    TASK = "task"
    PROTOCOL = "protocol"


@dataclass(frozen=True, slots=True)
class InvalidMetadataPartitionError(Exception):
    """Raised when split rows cannot be compared to prepared rows soundly."""

    violation: MetadataPartitionViolation

    @override
    def __str__(self) -> str:
        return f"invalid metadata partition receipt: {self.violation.value}"
