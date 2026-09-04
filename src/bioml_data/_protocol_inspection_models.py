"""Immutable public values used by protocol inspection."""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum, unique
from typing import override

from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._split import SplitAssignmentReceipt


@dataclass(frozen=True, slots=True)
class ProtocolInspectionRequest:
    """Explicit optional realized evidence attached to a plan-time request."""

    version: str | None = None
    assignment: SplitAssignmentReceipt | None = None
    concordance: MetadataConcordanceReport | None = None


@unique
class ProtocolReadiness(StrEnum):
    """Whether the separate support-readiness gate has evaluated this protocol."""

    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class ProtocolInspectionReceiptMismatchError(Exception):
    """Raised when a supplied result was not produced by the inspected protocol."""

    field: str
    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        return (
            f"protocol inspection receipt mismatch for {self.field}: "
            f"expected {self.expected!r}, received {self.actual!r}"
        )


@dataclass(frozen=True, slots=True)
class ProtocolCitationInspection:
    """One evidence citation rendered for stable public inspection."""

    title: str
    uri: str


@dataclass(frozen=True, slots=True)
class ProtocolEvidenceInspection:
    """One bounded evidence record rendered for a protocol report."""

    basis: str
    citations: tuple[ProtocolCitationInspection, ...]
    fit_scope: str
    leakage_caveat: str


@dataclass(frozen=True, slots=True)
class RealizedAssignmentInspection:
    """Receipt-derived assignment details, absent until a receipt is supplied."""

    identity: str
    seed: int
    observation_count: int
    group_count: int
    train_observation_count: int
    validation_observation_count: int
    test_observation_count: int
    train_group_count: int
    validation_group_count: int
    test_group_count: int
    test_group_ids: tuple[str, ...]
    cross_partition_group_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConcordanceInspection:
    """Identity and exact outcome counts for a supplied concordance report."""

    identity: str
    match_count: int
    mismatch_count: int
    not_reported_count: int


@dataclass(frozen=True, slots=True)
class ProtocolInspection:
    """Immutable researcher-facing description of one versioned protocol."""

    dataset_name: str
    dataset_version: str
    source_uri: str
    lifecycle: str
    readiness: ProtocolReadiness
    readiness_note: str
    task_id: str
    prediction_unit: str
    target: str
    protocol_id: str
    source_artifact: str
    transform_protocol: str
    evidence_basis: tuple[str, ...]
    evidence: tuple[ProtocolEvidenceInspection, ...]
    strategy: str
    held_out_axis: str
    leakage_unit: str
    grouping_column: str
    evaluation_target: str
    required_metadata: tuple[str, ...]
    assignment_rule: str
    deterministic_tie_break: str
    seed_policy: str
    requested_group_fractions: tuple[float, float, float] | None
    allocation_policy: str
    validation_policy: str
    group_overlap_invariant: str
    preprocessing_fit_scope: tuple[str, ...]
    limitations: tuple[str, ...]
    is_canary: bool
    realized_assignment: RealizedAssignmentInspection | None
    concordance: ConcordanceInspection | None

    def to_json(self) -> str:
        """Return stable, canonical JSON shared by Python and the CLI."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    def to_text(self) -> str:
        """Return a compact human-readable rendering of the same contract."""
        fractions = (
            "not applicable"
            if self.requested_group_fractions is None
            else "/".join(
                f"{fraction:.0%}" for fraction in self.requested_group_fractions
            )
        )
        plan_lines = (
            f"dataset: {self.dataset_name}@{self.dataset_version}",
            f"source: {self.source_uri}",
            f"artifact scope: {self.source_artifact}; {self.transform_protocol}",
            f"task: {self.task_id} ({self.prediction_unit} → {self.target})",
            f"protocol: {self.protocol_id}",
            (
                f"status: lifecycle={self.lifecycle}; "
                f"readiness={self.readiness.value}; "
                f"canary={str(self.is_canary).lower()}"
            ),
            f"readiness note: {self.readiness_note}",
            f"evidence basis: {', '.join(self.evidence_basis)}",
            (
                f"split: {self.strategy}; hold out {self.held_out_axis}; "
                f"group by {self.grouping_column}"
            ),
            f"target: {self.evaluation_target}; leakage unit: {self.leakage_unit}",
            f"required metadata: {', '.join(self.required_metadata)}",
            f"allocation: {fractions}; validation={self.validation_policy}",
            f"rule: {self.assignment_rule}",
            f"tie-break: {self.deterministic_tie_break}",
            f"seed policy: {self.seed_policy}",
            f"allocation policy: {self.allocation_policy}",
            f"group overlap invariant: {self.group_overlap_invariant}",
            f"fit scope: {'; '.join(self.preprocessing_fit_scope)}",
            f"limitations: {'; '.join(self.limitations)}",
        )
        return "\n".join(
            (*plan_lines, *_evidence_lines(self.evidence), *_receipt_lines(self))
        )


def _evidence_lines(
    evidence: tuple[ProtocolEvidenceInspection, ...],
) -> tuple[str, ...]:
    """Render every cited evidence record without hiding provenance."""
    return tuple(
        line
        for record in evidence
        for line in (
            f"evidence [{record.basis}] fit scope: {record.fit_scope}",
            f"evidence [{record.basis}] caveat: {record.leakage_caveat}",
            *tuple(
                f"citation [{record.basis}]: {citation.title} — {citation.uri}"
                for citation in record.citations
            ),
        )
    )


def _receipt_lines(report: ProtocolInspection) -> tuple[str, ...]:
    """Render only receipts the caller supplied to this read-only inspection."""
    assignment_lines = _assignment_lines(report.realized_assignment)
    concordance_lines = _concordance_lines(report.concordance)
    return (*assignment_lines, *concordance_lines)


def _assignment_lines(
    assignment: RealizedAssignmentInspection | None,
) -> tuple[str, ...]:
    """Render a verified assignment summary or state that it was not supplied."""
    if assignment is None:
        return ("realized assignment: absent",)
    return (
        f"realized assignment: {assignment.identity}; seed={assignment.seed}",
        (
            "realized observations: "
            f"train={assignment.train_observation_count}; "
            f"validation={assignment.validation_observation_count}; "
            f"test={assignment.test_observation_count}; "
            f"total={assignment.observation_count}"
        ),
        (
            "realized groups: "
            f"train={assignment.train_group_count}; "
            f"validation={assignment.validation_group_count}; "
            f"test={assignment.test_group_count}; total={assignment.group_count}"
        ),
        f"realized test groups: {', '.join(assignment.test_group_ids)}",
        (
            "realized cross-partition groups: "
            f"{', '.join(assignment.cross_partition_group_ids) or 'none'}"
        ),
    )


def _concordance_lines(
    concordance: ConcordanceInspection | None,
) -> tuple[str, ...]:
    """Render a supplied concordance identity and exact outcome counts."""
    if concordance is None:
        return ("concordance: absent",)
    return (
        (
            f"concordance: {concordance.identity}; "
            f"match={concordance.match_count}; "
            f"mismatch={concordance.mismatch_count}; "
            f"not_reported={concordance.not_reported_count}"
        ),
    )
