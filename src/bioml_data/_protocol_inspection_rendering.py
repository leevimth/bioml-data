"""Human-readable rendering for immutable protocol inspection reports."""

from enum import StrEnum
from typing import Protocol


class _Citation(Protocol):
    @property
    def title(self) -> str: ...
    @property
    def uri(self) -> str: ...


class _Evidence(Protocol):
    @property
    def basis(self) -> str: ...
    @property
    def citations(self) -> tuple[_Citation, ...]: ...
    @property
    def fit_scope(self) -> str: ...
    @property
    def leakage_caveat(self) -> str: ...


class _Assignment(Protocol):
    @property
    def caller_supplied(self) -> bool: ...
    @property
    def validation_scope(self) -> str: ...
    @property
    def identity(self) -> str: ...
    @property
    def seed(self) -> int: ...
    @property
    def observation_count(self) -> int: ...
    @property
    def group_count(self) -> int: ...
    @property
    def train_observation_count(self) -> int: ...
    @property
    def validation_observation_count(self) -> int: ...
    @property
    def test_observation_count(self) -> int: ...
    @property
    def train_group_count(self) -> int: ...
    @property
    def validation_group_count(self) -> int: ...
    @property
    def test_group_count(self) -> int: ...
    @property
    def test_group_ids(self) -> tuple[str, ...]: ...
    @property
    def cross_partition_group_ids(self) -> tuple[str, ...]: ...


class _Concordance(Protocol):
    @property
    def caller_supplied(self) -> bool: ...
    @property
    def validation_scope(self) -> str: ...
    @property
    def verification(self) -> StrEnum: ...
    @property
    def identity(self) -> str: ...
    @property
    def match_count(self) -> int: ...
    @property
    def mismatch_count(self) -> int: ...
    @property
    def not_reported_count(self) -> int: ...


class _Inspection(Protocol):
    @property
    def dataset_name(self) -> str: ...
    @property
    def dataset_version(self) -> str: ...
    @property
    def source_uri(self) -> str: ...
    @property
    def source_artifact(self) -> str: ...
    @property
    def transform_protocol(self) -> str: ...
    @property
    def task_id(self) -> str: ...
    @property
    def prediction_unit(self) -> str: ...
    @property
    def target(self) -> str: ...
    @property
    def protocol_id(self) -> str: ...
    @property
    def lifecycle(self) -> str: ...
    @property
    def readiness(self) -> StrEnum: ...
    @property
    def is_canary(self) -> bool: ...
    @property
    def readiness_note(self) -> str: ...
    @property
    def evidence_basis(self) -> tuple[str, ...]: ...
    @property
    def strategy(self) -> str: ...
    @property
    def held_out_axis(self) -> str: ...
    @property
    def grouping_column(self) -> str: ...
    @property
    def evaluation_target(self) -> str: ...
    @property
    def leakage_unit(self) -> str: ...
    @property
    def required_metadata(self) -> tuple[str, ...]: ...
    @property
    def requested_group_fractions(self) -> tuple[float, float, float] | None: ...
    @property
    def validation_policy(self) -> str: ...
    @property
    def assignment_rule(self) -> str: ...
    @property
    def deterministic_tie_break(self) -> str: ...
    @property
    def seed_policy(self) -> str: ...
    @property
    def allocation_policy(self) -> str: ...
    @property
    def group_overlap_invariant(self) -> str: ...
    @property
    def preprocessing_fit_scope(self) -> tuple[str, ...]: ...
    @property
    def limitations(self) -> tuple[str, ...]: ...
    @property
    def evidence(self) -> tuple[_Evidence, ...]: ...
    @property
    def realized_assignment(self) -> _Assignment | None: ...
    @property
    def concordance(self) -> _Concordance | None: ...


def render_protocol_inspection(report: _Inspection) -> str:
    """Render the full inspection contract without changing canonical JSON."""
    fractions = _fractions(report)
    plan_lines = (
        f"dataset: {report.dataset_name}@{report.dataset_version}",
        f"source: {report.source_uri}",
        f"artifact scope: {report.source_artifact}; {report.transform_protocol}",
        f"task: {report.task_id} ({report.prediction_unit} → {report.target})",
        f"protocol: {report.protocol_id}",
        (
            f"status: lifecycle={report.lifecycle}; "
            f"readiness={report.readiness.value}; "
            f"canary={str(report.is_canary).lower()}"
        ),
        f"readiness note: {report.readiness_note}",
        f"evidence basis: {', '.join(report.evidence_basis)}",
        (
            f"split: {report.strategy}; hold out {report.held_out_axis}; "
            f"group by {report.grouping_column}"
        ),
        f"target: {report.evaluation_target}; leakage unit: {report.leakage_unit}",
        f"required metadata: {', '.join(report.required_metadata)}",
        f"allocation: {fractions}; validation={report.validation_policy}",
        f"rule: {report.assignment_rule}",
        f"tie-break: {report.deterministic_tie_break}",
        f"seed policy: {report.seed_policy}",
        f"allocation policy: {report.allocation_policy}",
        f"group overlap invariant: {report.group_overlap_invariant}",
        f"fit scope: {'; '.join(report.preprocessing_fit_scope)}",
        f"limitations: {'; '.join(report.limitations)}",
    )
    return "\n".join(
        (*plan_lines, *_evidence_lines(report.evidence), *_receipt_lines(report))
    )


def _fractions(report: _Inspection) -> str:
    if report.requested_group_fractions is None:
        return "not applicable"
    return "/".join(f"{fraction:.0%}" for fraction in report.requested_group_fractions)


def _evidence_lines(
    evidence: tuple[_Evidence, ...],
) -> tuple[str, ...]:
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


def _receipt_lines(report: _Inspection) -> tuple[str, ...]:
    return (
        *_assignment_lines(report.realized_assignment),
        *_concordance_lines(report.concordance),
    )


def _assignment_lines(
    assignment: _Assignment | None,
) -> tuple[str, ...]:
    if assignment is None:
        return ("realized assignment: absent",)
    return (
        (
            "realized assignment "
            f"(caller_supplied={str(assignment.caller_supplied).lower()}; "
            f"validation_scope={assignment.validation_scope}): "
            f"{assignment.identity}; seed={assignment.seed}"
        ),
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
    concordance: _Concordance | None,
) -> tuple[str, ...]:
    if concordance is None:
        return ("concordance: absent",)
    return (
        (
            "concordance "
            f"(caller_supplied={str(concordance.caller_supplied).lower()}; "
            f"validation_scope={concordance.validation_scope}; "
            f"{concordance.verification.value}): {concordance.identity}; "
            f"match={concordance.match_count}; "
            f"mismatch={concordance.mismatch_count}; "
            f"not_reported={concordance.not_reported_count}"
        ),
    )
