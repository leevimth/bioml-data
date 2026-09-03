"""Immutable, publication-scoped metadata concordance contracts."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import Literal, NewType, override

from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId
from bioml_data._split_capability_models import SplitArtifactScope
from bioml_data.datasets._evidence_validation import valid_https_citation

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


ScalarMetadataMetric = Literal[
    MetadataMetric.OBSERVATION_COUNT,
    MetadataMetric.FEATURE_COUNT,
]
ValueMetadataMetric = Literal[
    MetadataMetric.STUDY_IDS,
    MetadataMetric.DONOR_IDS,
    MetadataMetric.GROUP_IDS,
    MetadataMetric.LABEL_VALUES,
    MetadataMetric.ASSAY_VALUES,
    MetadataMetric.TISSUE_VALUES,
]
DistributionMetadataMetric = Literal[
    MetadataMetric.LABEL_COUNTS,
    MetadataMetric.OBSERVATIONS_PER_GROUP,
]


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
        if not valid_https_citation(self.title, self.uri):
            raise InvalidMetadataExpectationError(
                detail="citation must be a public uncredentialed HTTPS URL"
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
        if (
            not self.value.strip()
            or type(self.count) is not int
            or self.count < 0
        ):
            raise InvalidMetadataExpectationError(
                detail=(
                    "metadata counts need a non-empty value and exact "
                    "non-negative integer"
                )
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
    GROUPING = "grouping"
    IDENTITY = "identity"
    RECEIPT_COUNTS = "receipt_counts"
    TASK = "task"
    PROTOCOL = "protocol"


@dataclass(frozen=True, slots=True)
class InvalidMetadataPartitionError(Exception):
    """Raised when split rows cannot be compared to prepared rows soundly."""

    violation: MetadataPartitionViolation

    @override
    def __str__(self) -> str:
        return f"invalid metadata partition receipt: {self.violation.value}"
