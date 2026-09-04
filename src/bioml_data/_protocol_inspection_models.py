"""Immutable public values used by protocol inspection."""

import json
from dataclasses import asdict, dataclass
from typing import override

from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._split import SplitAssignmentReceipt


@dataclass(frozen=True, slots=True)
class ProtocolInspectionRequest:
    """Explicit optional realized evidence attached to a plan-time request."""

    version: str | None = None
    assignment: SplitAssignmentReceipt | None = None
    concordance: MetadataConcordanceReport | None = None


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
        return "\n".join(
            (
                f"{self.dataset_name}@{self.dataset_version} · {self.protocol_id}",
                f"task: {self.task_id} ({self.prediction_unit} → {self.target})",
                f"source: {self.source_uri}",
                (
                    f"status: lifecycle={self.lifecycle}; "
                    f"canary={str(self.is_canary).lower()}"
                ),
                (
                    f"split: {self.strategy}; hold out {self.held_out_axis}; "
                    f"group by {self.grouping_column}"
                ),
                f"target: {self.evaluation_target}; leakage unit: {self.leakage_unit}",
                f"allocation: {fractions}; validation={self.validation_policy}",
                f"rule: {self.assignment_rule}",
                f"tie-break: {self.deterministic_tie_break}",
                f"fit scope: {'; '.join(self.preprocessing_fit_scope)}",
                f"limitations: {'; '.join(self.limitations)}",
            )
        )
