"""Integrity checks for deterministic metadata split receipts."""

from bioml_data._domain import SplitStrategy
from bioml_data._metadata_concordance_models import (
    InvalidMetadataPartitionError,
    MetadataPartitionViolation,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import (
    PartitionGroupCounts,
    SplitAssigner,
    SplitAssignmentReceipt,
    SplitPartition,
    assignment_receipt_identity,
)
from bioml_data._split_capability import SplitCapabilityQuery, query_split_capability


def validate_receipt_integrity(
    dataset: CanonicalSingleCellDataset,
    assignment: SplitAssignmentReceipt,
) -> None:
    """Reject stale or forged receipts by replaying the named allocation."""
    if assignment.assignment_identity != assignment_receipt_identity(assignment):
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.IDENTITY
        )
    actual_counts = _partition_group_counts(assignment)
    if (
        assignment.observation_count != len(assignment.assignments)
        or assignment.group_count
        != len({item.group for item in assignment.assignments})
        or assignment.realized_group_counts != actual_counts
    ):
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.RECEIPT_COUNTS
        )
    capability = query_split_capability(
        SplitCapabilityQuery(
            dataset=dataset.snapshot,
            task=assignment.task,
            protocol=str(assignment.protocol),
        )
    ).require_supported()
    if capability.strategy is SplitStrategy.LEAVE_ONE_STUDY_OUT:
        _validate_leave_one_study_out(assignment)
        return
    expected = SplitAssigner(
        dataset=dataset.snapshot,
        task=assignment.task,
        observations=dataset.split_observations,
    ).split(protocol=str(assignment.protocol), seed=assignment.seed)
    if assignment != expected:
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.ALLOCATION
        )


def _validate_leave_one_study_out(assignment: SplitAssignmentReceipt) -> None:
    """Require exactly one complete source study in test and nothing in validation."""
    test_groups = {
        item.group
        for item in assignment.assignments
        if item.partition is SplitPartition.TEST
    }
    is_valid = len(test_groups) == 1 and all(
        item.partition
        is (SplitPartition.TEST if item.group in test_groups else SplitPartition.TRAIN)
        for item in assignment.assignments
    )
    if not is_valid:
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.ALLOCATION
        )


def _partition_group_counts(
    assignment: SplitAssignmentReceipt,
) -> PartitionGroupCounts:
    """Count the distinct groups realized by each receipt partition."""
    return PartitionGroupCounts(
        train=_group_count(assignment, SplitPartition.TRAIN),
        validation=_group_count(assignment, SplitPartition.VALIDATION),
        test=_group_count(assignment, SplitPartition.TEST),
    )


def _group_count(
    assignment: SplitAssignmentReceipt,
    partition: SplitPartition,
) -> int:
    return len(
        {item.group for item in assignment.assignments if item.partition is partition}
    )
