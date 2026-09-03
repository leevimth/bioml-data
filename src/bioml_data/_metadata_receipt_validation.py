"""Integrity checks for deterministic metadata split receipts."""

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
    expected = SplitAssigner(
        dataset=dataset.snapshot,
        task=assignment.task,
        observations=dataset.split_observations,
    ).split(protocol=str(assignment.protocol), seed=assignment.seed)
    if assignment != expected:
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
