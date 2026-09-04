"""Structural binding for caller-supplied concordance attachments."""

from enum import StrEnum, unique

from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._protocol_inspection_models import (
    ProtocolInspectionReceiptMismatchError,
)
from bioml_data._protocol_inspection_validation import InspectionAttachmentContract
from bioml_data._split import SplitAssignmentReceipt, SplitPartition


@unique
class _Field(StrEnum):
    DATASET = "concordance_dataset"
    TASK = "concordance_task"
    PROTOCOL = "concordance_protocol"
    ASSIGNMENT = "concordance_assignment"
    ASSIGNMENT_IDENTITY = "concordance_assignment_identity"
    COVERED_COUNT = "concordance_covered_observation_count"
    OVERLAP = "concordance_cross_partition_groups"
    PARTITIONS = "concordance_partitions"
    PARTITION_OBSERVATIONS = "concordance_partition_observations"
    PARTITION_GROUPS = "concordance_partition_groups"
    HELD_OUT_GROUPS = "concordance_held_out_groups"


def validate_concordance_attachment(
    contract: InspectionAttachmentContract,
    assignment: SplitAssignmentReceipt | None,
    concordance: MetadataConcordanceReport,
) -> None:
    """Require exact receipt binding and consistent partition metadata."""
    for field, expected, actual in (
        (_Field.DATASET, str(contract.dataset), str(concordance.scope.dataset)),
        (_Field.TASK, contract.task, str(concordance.scope.task)),
        (_Field.PROTOCOL, contract.protocol, str(concordance.scope.protocol)),
    ):
        if expected != actual:
            raise _mismatch(field, expected, actual)
    if assignment is None:
        raise _mismatch(_Field.ASSIGNMENT, "supplied assignment receipt", "absent")
    if concordance.assignment_identity != assignment.assignment_identity:
        raise _mismatch(
            _Field.ASSIGNMENT_IDENTITY,
            str(assignment.assignment_identity),
            str(concordance.assignment_identity),
        )
    _validate_structure(assignment, concordance)


def _validate_structure(
    assignment: SplitAssignmentReceipt,
    concordance: MetadataConcordanceReport,
) -> None:
    rows = {
        partition: tuple(
            item for item in assignment.assignments if item.partition is partition
        )
        for partition in SplitPartition
    }
    expected_groups = {
        partition: tuple(sorted({str(item.group) for item in rows[partition]}))
        for partition in SplitPartition
    }
    if concordance.covered_observation_count != assignment.observation_count:
        raise _mismatch(
            _Field.COVERED_COUNT,
            str(assignment.observation_count),
            str(concordance.covered_observation_count),
        )
    if concordance.cross_partition_groups:
        raise _mismatch(_Field.OVERLAP, "()", str(concordance.cross_partition_groups))
    reports = {report.partition: report for report in concordance.partition_reports}
    expected_partitions = {partition for partition in SplitPartition if rows[partition]}
    if set(reports) != expected_partitions or len(reports) != len(
        concordance.partition_reports
    ):
        raise _mismatch(
            _Field.PARTITIONS,
            str(expected_partitions),
            str(set(reports)),
        )
    for partition, report in reports.items():
        if report.observation_count != len(rows[partition]):
            raise _mismatch(
                _Field.PARTITION_OBSERVATIONS,
                str(len(rows[partition])),
                str(report.observation_count),
            )
        if report.group_ids != expected_groups[partition]:
            raise _mismatch(
                _Field.PARTITION_GROUPS,
                str(expected_groups[partition]),
                str(report.group_ids),
            )
        expected_held_out = (
            expected_groups[partition] if partition is SplitPartition.TEST else ()
        )
        if report.held_out_groups != expected_held_out:
            raise _mismatch(
                _Field.HELD_OUT_GROUPS,
                str(expected_held_out),
                str(report.held_out_groups),
            )


def _mismatch(
    field: _Field,
    expected: str,
    actual: str,
) -> ProtocolInspectionReceiptMismatchError:
    return ProtocolInspectionReceiptMismatchError(
        field=field.value, expected=expected, actual=actual
    )
