"""Structural validation for caller-supplied inspection attachments."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import assert_never

from bioml_data._domain import DatasetSnapshotIdentity, SplitStrategy
from bioml_data._group_held_out_rules import (
    GROUP_HELD_OUT_ALLOCATION_RULE,
    group_held_out_partition_assignments,
    group_held_out_partition_counts,
)
from bioml_data._protocol_inspection_models import (
    ProtocolInspectionReceiptMismatchError,
)
from bioml_data._split import (
    PartitionFractions,
    PartitionGroupCounts,
    SplitAssignmentReceipt,
    SplitPartition,
    assignment_receipt_identity,
)
from bioml_data._split_capability_models import SplitCapability


@dataclass(frozen=True, slots=True)
class InspectionAttachmentContract:
    """Registered contract to which optional caller evidence must conform."""

    dataset: DatasetSnapshotIdentity
    task: str
    protocol: str
    capability: SplitCapability


@unique
class _Field(StrEnum):
    ASSIGNMENT_IDENTITY = "assignment_identity"
    ASSIGNMENT_DATASET = "assignment_dataset"
    ASSIGNMENT_TASK = "assignment_task"
    ASSIGNMENT_PROTOCOL = "assignment_protocol"
    ASSIGNMENT_STRATEGY = "assignment_strategy"
    DUPLICATE_OBSERVATION_ID = "duplicate_observation_id"
    GROUP_PARTITION = "group_partition"
    REQUESTED_FRACTIONS = "requested_group_fractions"
    OBSERVATION_COUNT = "observation_count"
    GROUP_COUNT = "group_count"
    REALIZED_GROUP_COUNTS = "realized_group_counts"
    REGISTERED_ALLOCATION = "registered_allocation"


def validate_assignment_attachment(
    contract: InspectionAttachmentContract,
    assignment: SplitAssignmentReceipt | None,
) -> None:
    """Replay the structural allocation in an optional caller receipt."""
    if assignment is not None:
        _validate_assignment(contract, assignment)


def _validate_assignment(
    contract: InspectionAttachmentContract,
    assignment: SplitAssignmentReceipt,
) -> None:
    identity = assignment_receipt_identity(assignment)
    if assignment.assignment_identity != identity:
        raise _mismatch(
            _Field.ASSIGNMENT_IDENTITY,
            str(identity),
            str(assignment.assignment_identity),
        )
    for field, expected, actual in (
        (_Field.ASSIGNMENT_DATASET, str(contract.dataset), str(assignment.dataset)),
        (_Field.ASSIGNMENT_TASK, contract.task, str(assignment.task)),
        (_Field.ASSIGNMENT_PROTOCOL, contract.protocol, str(assignment.protocol)),
    ):
        if expected != actual:
            raise _mismatch(field, expected, actual)
    match contract.capability.strategy:
        case SplitStrategy.GROUP_HELD_OUT:
            _validate_group_held_out_assignment(assignment)
        case unreachable:
            if unreachable is SplitStrategy.LEAVE_ONE_STUDY_OUT:
                raise _mismatch(
                    _Field.ASSIGNMENT_STRATEGY,
                    SplitStrategy.GROUP_HELD_OUT.value,
                    unreachable.value,
                )
            if unreachable is None:
                raise _mismatch(
                    _Field.ASSIGNMENT_STRATEGY,
                    SplitStrategy.GROUP_HELD_OUT.value,
                    "absent",
                )
            assert_never(unreachable)


def _validate_group_held_out_assignment(assignment: SplitAssignmentReceipt) -> None:
    expected_fractions = _expected_fractions()
    if assignment.requested_group_fractions != expected_fractions:
        raise _mismatch(
            _Field.REQUESTED_FRACTIONS,
            str(expected_fractions),
            str(assignment.requested_group_fractions),
        )
    observed_by_group = _observed_partitions_by_group(assignment)
    groups = tuple(sorted(observed_by_group))
    _validate_receipt_counts(assignment, observed_by_group)
    if len(groups) < GROUP_HELD_OUT_ALLOCATION_RULE.minimum_group_count:
        raise _mismatch(
            _Field.GROUP_COUNT,
            f">={GROUP_HELD_OUT_ALLOCATION_RULE.minimum_group_count}",
            str(len(groups)),
        )
    expected_by_group = dict(
        group_held_out_partition_assignments(groups, seed=assignment.seed)
    )
    if observed_by_group != expected_by_group:
        raise _mismatch(
            _Field.REGISTERED_ALLOCATION,
            str(expected_by_group),
            str(observed_by_group),
        )


def _expected_fractions() -> PartitionFractions:
    rule = GROUP_HELD_OUT_ALLOCATION_RULE
    return PartitionFractions(
        train=rule.train_weight / rule.total_weight,
        validation=rule.validation_weight / rule.total_weight,
        test=rule.test_weight / rule.total_weight,
    )


def _observed_partitions_by_group(
    assignment: SplitAssignmentReceipt,
) -> Mapping[str, str]:
    observed_ids: set[str] = set()
    observed_by_group: dict[str, str] = {}
    for item in assignment.assignments:
        observation_id = str(item.observation_id)
        if observation_id in observed_ids:
            raise _mismatch(_Field.DUPLICATE_OBSERVATION_ID, "unique", observation_id)
        observed_ids.add(observation_id)
        if type(item.partition) is not SplitPartition:
            raise _mismatch(
                _Field.GROUP_PARTITION,
                "registered partition",
                str(item.partition),
            )
        group = str(item.group)
        partition = item.partition.value
        prior = observed_by_group.setdefault(group, partition)
        if prior != partition:
            raise _mismatch(_Field.GROUP_PARTITION, "one partition per group", group)
    return observed_by_group


def _validate_receipt_counts(
    assignment: SplitAssignmentReceipt,
    observed_by_group: Mapping[str, str],
) -> None:
    if assignment.observation_count != len(assignment.assignments):
        raise _mismatch(
            _Field.OBSERVATION_COUNT,
            str(len(assignment.assignments)),
            str(assignment.observation_count),
        )
    if assignment.group_count != len(observed_by_group):
        raise _mismatch(
            _Field.GROUP_COUNT,
            str(len(observed_by_group)),
            str(assignment.group_count),
        )
    replayed_counts = group_held_out_partition_counts(len(observed_by_group))
    expected_counts = PartitionGroupCounts(
        train=replayed_counts.train,
        validation=replayed_counts.validation,
        test=replayed_counts.test,
    )
    actual_counts = PartitionGroupCounts(
        train=tuple(observed_by_group.values()).count(SplitPartition.TRAIN.value),
        validation=tuple(observed_by_group.values()).count(
            SplitPartition.VALIDATION.value
        ),
        test=tuple(observed_by_group.values()).count(SplitPartition.TEST.value),
    )
    if assignment.realized_group_counts != actual_counts:
        raise _mismatch(
            _Field.REALIZED_GROUP_COUNTS,
            str(actual_counts),
            str(assignment.realized_group_counts),
        )
    if actual_counts != expected_counts:
        raise _mismatch(
            _Field.REALIZED_GROUP_COUNTS,
            str(expected_counts),
            str(actual_counts),
        )


def _mismatch(
    field: _Field,
    expected: str,
    actual: str,
) -> ProtocolInspectionReceiptMismatchError:
    return ProtocolInspectionReceiptMismatchError(
        field=field.value, expected=expected, actual=actual
    )
