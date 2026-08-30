"""Post-assignment leakage evidence reports."""

from collections import Counter
from dataclasses import dataclass
from typing import Final

import bioml_data._leakage_audit_models as _models
from bioml_data._leakage_audit_models import (
    DuplicateSummary,
    MetadataCoverage,
)
from bioml_data._leakage_audit_reporting import (
    LeakageAuditEvidence,
    build_report,
)
from bioml_data._split import SplitObservation, SplitPartition
from bioml_data._split_capability import (
    SplitCapabilityQuery,
    query_split_capability,
)

AuditStatus = _models.AuditStatus
AuditSupport = _models.AuditSupport
LeakageAuditReport = _models.LeakageAuditReport
LeakageAuditRequest = _models.LeakageAuditRequest
OverlapCheck = _models.OverlapCheck


@dataclass(frozen=True, slots=True)
class _Axis:
    name: str
    columns: tuple[str, ...]
    required: bool


_INFORMATIVE_AXES: Final = (
    _Axis(name="study", columns=("study_id",), required=False),
    _Axis(
        name="library_batch",
        columns=("library_id", "batch_id"),
        required=False,
    ),
    _Axis(name="assay", columns=("assay",), required=False),
    _Axis(name="tissue", columns=("tissue",), required=False),
    _Axis(name="label", columns=("cell_type",), required=False),
)
_STATUS_PRIORITY: Final = {
    AuditStatus.PASS: 0,
    AuditStatus.UNKNOWN: 1,
    AuditStatus.WARN: 2,
    AuditStatus.FAIL: 3,
}


def audit_split(request: LeakageAuditRequest) -> LeakageAuditReport:
    """Audit exact duplicates, declared leakage units, and metadata overlaps."""
    capability_result = query_split_capability(
        SplitCapabilityQuery(
            dataset=request.dataset,
            task=request.assignment.task,
            protocol=request.assignment.protocol,
        )
    )
    capability = capability_result.capability_or_none()
    support = AuditSupport(capability_result.availability)
    duplicates = _duplicate_summary(request)
    if capability is None:
        return build_report(
            request,
            LeakageAuditEvidence(
                support=support,
                status=AuditStatus.UNKNOWN,
                supported_protocols=capability_result.supported_protocols,
                duplicates=duplicates,
                checks=(),
            ),
        )

    checks = (
        _duplicate_check(request, duplicates),
        _axis_check(
            request,
            _Axis(
                name="donor_animal",
                columns=(capability.grouping_column,),
                required=True,
            ),
        ),
        *tuple(_axis_check(request, axis) for axis in _INFORMATIVE_AXES),
    )
    status = max(
        (check.status for check in checks),
        key=_STATUS_PRIORITY.__getitem__,
    )
    return build_report(
        request,
        LeakageAuditEvidence(
            support=support,
            status=status,
            supported_protocols=capability_result.supported_protocols,
            duplicates=duplicates,
            checks=checks,
        ),
    )


def _duplicate_summary(request: LeakageAuditRequest) -> DuplicateSummary:
    observation_counts = Counter(
        observation.observation_id for observation in request.observations
    )
    repeated = tuple(
        sorted(item for item, count in observation_counts.items() if count > 1)
    )
    partitions: dict[str, set[SplitPartition]] = {}
    for assignment in request.assignment.assignments:
        partitions.setdefault(assignment.observation_id, set()).add(
            assignment.partition
        )
    cross_partition = tuple(
        sorted(item for item, values in partitions.items() if len(values) > 1)
    )
    return DuplicateSummary(
        repeated_observation_ids=repeated,
        cross_partition_observation_ids=cross_partition,
    )


def _duplicate_check(
    request: LeakageAuditRequest,
    duplicates: DuplicateSummary,
) -> OverlapCheck:
    has_duplicates = bool(
        duplicates.repeated_observation_ids
        or duplicates.cross_partition_observation_ids
    )
    status = AuditStatus.FAIL if has_duplicates else AuditStatus.PASS
    overlaps = tuple(
        sorted(
            set(duplicates.repeated_observation_ids)
            | set(duplicates.cross_partition_observation_ids)
        )
    )
    return OverlapCheck(
        axis="observation_id",
        columns=("cell_id",),
        required=True,
        status=status,
        coverage=MetadataCoverage(
            present=len(request.observations),
            total=len(request.observations),
        ),
        overlapping_values=overlaps,
    )


def _axis_check(request: LeakageAuditRequest, axis: _Axis) -> OverlapCheck:
    assignment_by_observation = {
        assignment.observation_id: assignment.partition
        for assignment in request.assignment.assignments
    }
    value_partitions: dict[str, set[SplitPartition]] = {}
    present = 0
    for observation in request.observations:
        value = _metadata_value(observation, axis.columns)
        partition = assignment_by_observation.get(observation.observation_id)
        if value is not None and partition is not None:
            present += 1
            value_partitions.setdefault(value, set()).add(partition)
    overlaps = tuple(
        sorted(
            value
            for value, partitions in value_partitions.items()
            if len(partitions) > 1
        )
    )
    total = len(request.observations)
    if axis.required and overlaps:
        status = AuditStatus.FAIL
    elif present < total:
        status = AuditStatus.UNKNOWN
    elif overlaps:
        status = AuditStatus.WARN
    else:
        status = AuditStatus.PASS
    return OverlapCheck(
        axis=axis.name,
        columns=axis.columns,
        required=axis.required,
        status=status,
        coverage=MetadataCoverage(present=present, total=total),
        overlapping_values=overlaps,
    )


def _metadata_value(
    observation: SplitObservation,
    columns: tuple[str, ...],
) -> str | None:
    values = tuple(
        item.value for item in observation.metadata if item.column in columns
    )
    return values[0] if values else None
