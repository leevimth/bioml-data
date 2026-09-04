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


@unique
class ConcordanceVerification(StrEnum):
    """Trust boundary for a concordance attachment shown by inspection."""

    CALLER_SUPPLIED_UNVERIFIED = "caller-supplied-unverified"


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

    caller_supplied: bool
    validation_scope: str
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
    """Caller-supplied concordance identity and outcome counts."""

    caller_supplied: bool
    validation_scope: str
    verification: ConcordanceVerification
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
        from bioml_data._protocol_inspection_rendering import (  # noqa: PLC0415 - avoids model/render import cycle
            render_protocol_inspection,
        )

        return render_protocol_inspection(self)
