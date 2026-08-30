"""Serializable evidence contracts for post-split leakage audits."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, NewType

from pydantic import BaseModel, ConfigDict

from bioml_data._artifacts import ArtifactId
from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import SplitAssignmentReceipt, SplitObservation

LeakageAuditIdentity = NewType("LeakageAuditIdentity", str)


@unique
class AuditStatus(StrEnum):
    """Evidence outcome for an audit or individual check."""

    PASS = "pass"  # noqa: S105  # Audit outcome, not a credential.
    WARN = "warn"
    FAIL = "fail"
    UNKNOWN = "unknown"


@unique
class AuditSupport(StrEnum):
    """Capability assessment state kept separate from audit evidence."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class MetadataCoverage(BaseModel):
    """Observed metadata coverage for one audit axis."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    present: int
    total: int


class OverlapCheck(BaseModel):
    """Coverage and cross-partition overlap for one biological axis."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    axis: str
    columns: tuple[str, ...]
    required: bool
    status: AuditStatus
    coverage: MetadataCoverage
    overlapping_values: tuple[str, ...]


class DuplicateSummary(BaseModel):
    """Exact observation duplication evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    repeated_observation_ids: tuple[str, ...]
    cross_partition_observation_ids: tuple[str, ...]


class LeakageAuditReport(BaseModel):
    """Deterministic machine and human-readable leakage evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    report_identity: LeakageAuditIdentity
    dataset: DatasetSnapshotIdentity
    artifact_identity: ArtifactId
    protocol: ProtocolId
    assignment_identity: str
    support: AuditSupport
    status: AuditStatus
    evidence_fields: tuple[str, ...]
    supported_protocols: tuple[ProtocolId, ...]
    duplicates: DuplicateSummary
    checks: tuple[OverlapCheck, ...]

    def to_json(self) -> str:
        """Render deterministic JSON evidence."""
        return self.model_dump_json()

    def to_text(self) -> str:
        """Render a compact deterministic human report."""
        header = " ".join(
            (
                f"leakage-audit {self.report_identity}",
                f"support={self.support}",
                f"status={self.status}",
            )
        )
        identity = " ".join(
            (
                f"dataset={self.dataset.name}@{self.dataset.version}",
                f"artifact={self.artifact_identity}",
                f"protocol={self.protocol}",
            )
        )
        checks = tuple(
            "".join(
                (
                    f"{check.axis}: {check.status} ",
                    f"coverage={check.coverage.present}/{check.coverage.total} ",
                    f"overlap={','.join(check.overlapping_values) or '-'}",
                )
            )
            for check in self.checks
        )
        return "\n".join((header, identity, *checks))


@dataclass(frozen=True, slots=True)
class LeakageAuditRequest:
    """Canonical rows and identities required for one split audit."""

    dataset: DatasetSnapshotIdentity
    artifact_identity: ArtifactId
    observations: tuple[SplitObservation, ...]
    assignment: SplitAssignmentReceipt

    @classmethod
    def from_dataset(
        cls,
        dataset: CanonicalSingleCellDataset,
        assignment: SplitAssignmentReceipt,
    ) -> "LeakageAuditRequest":
        """Project a canonical dataset onto the audit boundary."""
        return cls(
            dataset=dataset.snapshot,
            artifact_identity=dataset.artifact.artifact_id,
            observations=dataset.split_observations,
            assignment=assignment,
        )
