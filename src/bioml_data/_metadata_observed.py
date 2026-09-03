"""Read-only metadata projections from prepared rows and split receipts."""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from bioml_data._metadata_concordance_models import (
    DistributionMetadataMetric,
    InvalidMetadataPartitionError,
    MetadataCount,
    MetadataMetric,
    MetadataPartitionViolation,
    ScalarMetadataMetric,
    ValueMetadataMetric,
)
from bioml_data._single_cell import CanonicalObservation, CanonicalSingleCellDataset
from bioml_data._split import (
    MetadataValue,
    PartitionGroupCounts,
    SplitAssigner,
    SplitAssignmentReceipt,
    SplitPartition,
    assignment_receipt_identity,
)
from bioml_data._split_capability import SplitCapabilityQuery, query_split_capability


@dataclass(frozen=True, slots=True)
class MetadataObservedValue:
    """One measured scalar, category set, or category distribution."""

    count: int | None = None
    values: tuple[str, ...] = ()
    distribution: tuple[MetadataCount, ...] = ()


@dataclass(frozen=True, slots=True)
class AssignedGroup:
    """One partition and group association from the immutable split receipt."""

    group: str
    partition: SplitPartition


def assignment_by_id(
    dataset: CanonicalSingleCellDataset,
    assignment: SplitAssignmentReceipt,
) -> dict[str, AssignedGroup]:
    """Validate complete row coverage and index each split assignment once."""
    if assignment.dataset != dataset.snapshot:
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.DATASET
        )
    observed_ids = tuple(str(item.cell_id) for item in dataset.observations)
    assignment_ids = tuple(str(item.observation_id) for item in assignment.assignments)
    if len(set(assignment_ids)) != len(assignment_ids):
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.DUPLICATE_OBSERVATION
        )
    if set(assignment_ids) != set(observed_ids):
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.COVERAGE
        )
    _validate_receipt_integrity(dataset, assignment)
    _validate_canonical_groups(dataset, assignment)
    return {
        str(item.observation_id): AssignedGroup(
            group=str(item.group),
            partition=item.partition,
        )
        for item in assignment.assignments
    }


def _validate_receipt_integrity(
    dataset: CanonicalSingleCellDataset,
    assignment: SplitAssignmentReceipt,
) -> None:
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
    return PartitionGroupCounts(
        train=len(
            {
                item.group
                for item in assignment.assignments
                if item.partition is SplitPartition.TRAIN
            }
        ),
        validation=len(
            {
                item.group
                for item in assignment.assignments
                if item.partition is SplitPartition.VALIDATION
            }
        ),
        test=len(
            {
                item.group
                for item in assignment.assignments
                if item.partition is SplitPartition.TEST
            }
        ),
    )


def _validate_canonical_groups(
    dataset: CanonicalSingleCellDataset,
    assignment: SplitAssignmentReceipt,
) -> None:
    capability = query_split_capability(
        SplitCapabilityQuery(
            dataset=dataset.snapshot,
            task=assignment.task,
            protocol=str(assignment.protocol),
        )
    ).require_supported()
    canonical_groups = {
        str(observation.observation_id): _group_value(
            observation.metadata,
            capability.grouping_column,
        )
        for observation in dataset.split_observations
    }
    if any(
        str(item.group) != canonical_groups[str(item.observation_id)]
        for item in assignment.assignments
    ):
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.GROUPING
        )


def _group_value(
    metadata: tuple[MetadataValue, ...],
    column: str,
) -> str:
    values = tuple(item.value for item in metadata if item.column == column)
    if len(values) != 1:
        raise InvalidMetadataPartitionError(
            violation=MetadataPartitionViolation.GROUPING
        )
    return values[0]


def partitioned_rows(
    dataset: CanonicalSingleCellDataset,
    assignments: dict[str, AssignedGroup],
) -> dict[SplitPartition, tuple[int, ...]]:
    """Return every actual partition, including empty ones, without inventing rows."""
    rows: dict[SplitPartition, list[int]] = {
        partition: [] for partition in SplitPartition
    }
    for position, observation in enumerate(dataset.observations):
        rows[assignments[str(observation.cell_id)].partition].append(position)
    return {partition: tuple(positions) for partition, positions in rows.items()}


def groups_by_partition(
    assignments: dict[str, AssignedGroup],
    partition: SplitPartition,
) -> tuple[str, ...]:
    """Return distinct groups assigned to one partition in stable order."""
    return tuple(
        sorted(
            {item.group for item in assignments.values() if item.partition is partition}
        )
    )


def cross_partition_groups(
    assignments: dict[str, AssignedGroup],
) -> tuple[str, ...]:
    """Expose group overlap without conflating it with a leakage-audit verdict."""
    partitions_by_group: dict[str, set[SplitPartition]] = {}
    for assignment in assignments.values():
        partitions_by_group.setdefault(assignment.group, set()).add(
            assignment.partition
        )
    return tuple(
        sorted(
            group
            for group, partitions in partitions_by_group.items()
            if len(partitions) > 1
        )
    )


def observed_value(
    dataset: CanonicalSingleCellDataset,
    rows: tuple[int, ...],
    assignments: dict[str, AssignedGroup],
    metric: MetadataMetric,
) -> MetadataObservedValue:
    """Project one supported metadata metric for a whole dataset or one partition."""
    observations = tuple(dataset.observations[position] for position in rows)
    match metric:
        case MetadataMetric.OBSERVATION_COUNT | MetadataMetric.FEATURE_COUNT:
            return _observed_count(dataset, observations, metric)
        case (
            MetadataMetric.STUDY_IDS
            | MetadataMetric.DONOR_IDS
            | MetadataMetric.GROUP_IDS
            | MetadataMetric.LABEL_VALUES
            | MetadataMetric.ASSAY_VALUES
            | MetadataMetric.TISSUE_VALUES
        ):
            return _observed_values(observations, assignments, metric)
        case MetadataMetric.LABEL_COUNTS | MetadataMetric.OBSERVATIONS_PER_GROUP:
            return _observed_distribution(observations, assignments, metric)


def _observed_count(
    dataset: CanonicalSingleCellDataset,
    observations: tuple[CanonicalObservation, ...],
    metric: ScalarMetadataMetric,
) -> MetadataObservedValue:
    match metric:
        case MetadataMetric.OBSERVATION_COUNT:
            return MetadataObservedValue(count=len(observations))
        case MetadataMetric.FEATURE_COUNT:
            return MetadataObservedValue(count=len(dataset.features))


def _observed_values(
    observations: tuple[CanonicalObservation, ...],
    assignments: dict[str, AssignedGroup],
    metric: ValueMetadataMetric,
) -> MetadataObservedValue:
    match metric:
        case MetadataMetric.STUDY_IDS:
            values = (item.study_id for item in observations)
        case MetadataMetric.DONOR_IDS:
            values = (item.donor_id for item in observations)
        case MetadataMetric.GROUP_IDS:
            values = (assignments[str(item.cell_id)].group for item in observations)
        case MetadataMetric.LABEL_VALUES:
            values = (item.cell_type for item in observations)
        case MetadataMetric.ASSAY_VALUES:
            values = (item.assay for item in observations if item.assay is not None)
        case MetadataMetric.TISSUE_VALUES:
            values = (item.tissue for item in observations)
    return MetadataObservedValue(values=tuple(sorted(set(values))))


def _observed_distribution(
    observations: tuple[CanonicalObservation, ...],
    assignments: dict[str, AssignedGroup],
    metric: DistributionMetadataMetric,
) -> MetadataObservedValue:
    match metric:
        case MetadataMetric.LABEL_COUNTS:
            values = (item.cell_type for item in observations)
        case MetadataMetric.OBSERVATIONS_PER_GROUP:
            values = (assignments[str(item.cell_id)].group for item in observations)
    return MetadataObservedValue(distribution=_counts(values))


def _counts(values: Iterable[str]) -> tuple[MetadataCount, ...]:
    return tuple(
        MetadataCount(value=value, count=count)
        for value, count in sorted(Counter(values).items())
    )
