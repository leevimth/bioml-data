"""Immutable models for explicit dataset support-readiness reports."""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum, unique
from typing import override

from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data.datasets._evidence_validation import valid_https_citation


@unique
class ReadinessDimension(StrEnum):
    """Required independently-reviewable dataset support dimensions."""

    SOURCE_CHECKSUM = "source_checksum"
    RIGHTS = "rights"
    CANONICAL_SCHEMA = "canonical_schema"
    TASK = "task"
    DETERMINISTIC_PREPARATION = "deterministic_preparation"
    SPLIT = "split"
    EVALUATION = "evaluation"
    METADATA_CONCORDANCE = "metadata_concordance"


@unique
class ReadinessFieldStatus(StrEnum):
    """A single field's explicit support-readiness outcome."""

    SATISFIED = "satisfied"
    MISSING = "missing"
    FAILING = "failing"
    QUALIFIED = "qualified"


@unique
class ReadinessVerdict(StrEnum):
    """Overall result without mutating the dataset lifecycle declaration."""

    READY = "ready"
    READY_WITH_QUALIFICATIONS = "ready_with_qualifications"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class InvalidReadinessEvidenceError(Exception):
    """Raised when a readiness evidence bundle is not a bounded public claim."""

    detail: str

    @override
    def __str__(self) -> str:
        return f"invalid readiness evidence: {self.detail}"


@dataclass(frozen=True, slots=True)
class ReadinessCitation:
    """One public source supporting a readiness claim or qualification."""

    title: str
    uri: str

    def __post_init__(self) -> None:
        """Reject non-public citations before publishing a readiness report."""
        if not valid_https_citation(self.title, self.uri):
            raise InvalidReadinessEvidenceError(detail="citation must be public HTTPS")


@dataclass(frozen=True, slots=True)
class ReadinessEvidence:
    """A cited field-level evidence declaration supplied by the built-in catalog."""

    detail: str
    citation: ReadinessCitation

    def __post_init__(self) -> None:
        """Keep published evidence explanations non-empty and canonical."""
        if not self.detail or self.detail != self.detail.strip():
            raise InvalidReadinessEvidenceError(
                detail="evidence detail must be non-empty"
            )


@dataclass(frozen=True, slots=True)
class ReadinessQualification:
    """A cited, field-specific limitation that prevents a false failure claim."""

    dimension: ReadinessDimension
    detail: str
    citation: ReadinessCitation

    def __post_init__(self) -> None:
        """Reject unbounded qualifications that could silently waive a gate."""
        if not self.detail or self.detail != self.detail.strip():
            raise InvalidReadinessEvidenceError(
                detail="qualification detail must be non-empty"
            )


@dataclass(frozen=True, slots=True)
class DatasetReadinessEvidence:
    """External evidence that cannot be inferred from implementation structure."""

    rights: ReadinessEvidence | None
    evaluation: ReadinessEvidence | None
    metadata_concordance: ReadinessEvidence | None
    qualifications: tuple[ReadinessQualification, ...] = ()

    def __post_init__(self) -> None:
        """Require one qualification at most for each precise readiness field."""
        dimensions = tuple(item.dimension for item in self.qualifications)
        if len(set(dimensions)) != len(dimensions):
            raise InvalidReadinessEvidenceError(
                detail="qualifications must not repeat a readiness dimension"
            )


@dataclass(frozen=True, slots=True)
class ReadinessField:
    """One deterministic readiness result with no implicit fallback outcome."""

    dimension: ReadinessDimension
    status: ReadinessFieldStatus
    detail: str
    citation: ReadinessCitation | None = None


@dataclass(frozen=True, slots=True)
class DatasetReadinessReport:
    """Structured readiness outcome separate from catalog lifecycle status."""

    dataset: DatasetSnapshotIdentity
    verdict: ReadinessVerdict
    fields: tuple[ReadinessField, ...]

    @property
    def missing_fields(self) -> tuple[ReadinessField, ...]:
        """Return all explicitly absent required evidence fields."""
        return tuple(
            item for item in self.fields if item.status is ReadinessFieldStatus.MISSING
        )

    @property
    def failing_fields(self) -> tuple[ReadinessField, ...]:
        """Return all unqualified structural or contract failures."""
        return tuple(
            item for item in self.fields if item.status is ReadinessFieldStatus.FAILING
        )

    @property
    def qualified_fields(self) -> tuple[ReadinessField, ...]:
        """Return limitations accepted only with a field-level public citation."""
        return tuple(
            item
            for item in self.fields
            if item.status is ReadinessFieldStatus.QUALIFIED
        )

    def to_json(self) -> str:
        """Serialize a stable, canonical machine-readable report."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
