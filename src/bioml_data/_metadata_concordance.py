"""Deterministic metadata comparisons for prepared single-cell partitions."""

from dataclasses import dataclass

from bioml_data._metadata_concordance_models import (
    MetadataConcordance,
    MetadataExpectationKind,
    MetadataExpectationScope,
    MetadataExpectationScopeMismatchError,
    MetadataFoldId,
)
from bioml_data._metadata_expectations import PublicationMetadataExpectation
from bioml_data._metadata_observed import (
    AssignedGroup,
    MetadataObservedValue,
    assignment_by_id,
    cross_partition_groups,
    groups_by_partition,
    observed_value,
    partitioned_rows,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import SplitAssignmentReceipt, SplitPartition


@dataclass(frozen=True, slots=True)
class MetadataComparison:
    """One observed value and the precise evidence comparison outcome."""

    expectation: PublicationMetadataExpectation
    observed: MetadataObservedValue
    status: MetadataConcordance


@dataclass(frozen=True, slots=True)
class MetadataPartitionReport:
    """Metadata evidence for one realized partition; never synthesizes a split."""

    partition: SplitPartition
    observation_count: int
    feature_count: int
    group_ids: tuple[str, ...]
    held_out_groups: tuple[str, ...]
    comparisons: tuple[MetadataComparison, ...]


@dataclass(frozen=True, slots=True)
class MetadataConcordanceReport:
    """Whole-dataset and partition-level metadata evidence for one split receipt."""

    scope: MetadataExpectationScope
    fold: MetadataFoldId | None
    dataset_comparisons: tuple[MetadataComparison, ...]
    partition_reports: tuple[MetadataPartitionReport, ...]
    covered_observation_count: int
    cross_partition_groups: tuple[str, ...]


def compare_metadata_concordance(
    dataset: CanonicalSingleCellDataset,
    assignment: SplitAssignmentReceipt,
    *,
    expectations: tuple[PublicationMetadataExpectation, ...],
    fold: MetadataFoldId | None = None,
) -> MetadataConcordanceReport:
    """Compare exact-scope evidence to complete data and every realized partition."""
    scope = _shared_scope(expectations)
    _validate_fold(expectations, fold)
    _validate_scope(dataset, assignment, scope)
    assignments = assignment_by_id(dataset, assignment)
    datasets = partitioned_rows(dataset, assignments)
    dataset_expectations = _expectations_for(
        expectations,
        partition=None,
        fold=fold,
    )
    reports = tuple(
        _partition_report(
            dataset,
            partition,
            datasets[partition],
            assignments,
            _expectations_for(expectations, partition=partition, fold=fold),
        )
        for partition in SplitPartition
        if datasets[partition]
    )
    return MetadataConcordanceReport(
        scope=scope,
        fold=fold,
        dataset_comparisons=_compare(dataset, assignments, dataset_expectations),
        partition_reports=reports,
        covered_observation_count=len(assignments),
        cross_partition_groups=cross_partition_groups(assignments),
    )


def _shared_scope(
    expectations: tuple[PublicationMetadataExpectation, ...],
) -> MetadataExpectationScope:
    if not expectations:
        raise MetadataExpectationScopeMismatchError(
            field="expectations",
            expected="at least one scoped expectation",
            actual="none",
        )
    scope = expectations[0].scope
    for expectation in expectations[1:]:
        if expectation.scope != scope:
            raise MetadataExpectationScopeMismatchError(
                field="expectation_scope",
                expected=str(scope),
                actual=str(expectation.scope),
            )
    return scope


def _validate_fold(
    expectations: tuple[PublicationMetadataExpectation, ...],
    fold: MetadataFoldId | None,
) -> None:
    targeted_folds = {item.fold for item in expectations if item.fold is not None}
    if targeted_folds and targeted_folds != {fold}:
        raise MetadataExpectationScopeMismatchError(
            field="fold",
            expected=", ".join(sorted(targeted_folds)),
            actual=str(fold) if fold is not None else "none",
        )


def _validate_scope(
    dataset: CanonicalSingleCellDataset,
    assignment: SplitAssignmentReceipt,
    scope: MetadataExpectationScope,
) -> None:
    _require_equal("dataset", scope.dataset, dataset.snapshot)
    _require_equal("assignment_dataset", scope.dataset, assignment.dataset)
    _require_equal("task", scope.task, assignment.task)
    _require_equal("protocol", scope.protocol, assignment.protocol)
    derivation = dataset.artifact.derivation
    if derivation is None:
        raise MetadataExpectationScopeMismatchError(
            field="artifact_derivation",
            expected=str(scope.artifact),
            actual="none",
        )
    _require_equal(
        "source_artifacts",
        scope.artifact.parent_artifacts,
        derivation.parent_artifacts,
    )
    _require_equal(
        "transform_protocol",
        scope.artifact.transform_protocol,
        derivation.transform_protocol,
    )


def _require_equal(field: str, expected: object, actual: object) -> None:
    if expected != actual:
        raise MetadataExpectationScopeMismatchError(
            field=field,
            expected=str(expected),
            actual=str(actual),
        )


def _expectations_for(
    expectations: tuple[PublicationMetadataExpectation, ...],
    *,
    partition: SplitPartition | None,
    fold: MetadataFoldId | None,
) -> tuple[PublicationMetadataExpectation, ...]:
    return tuple(
        expectation
        for expectation in expectations
        if expectation.partition is partition and expectation.fold == fold
    )


def _partition_report(
    dataset: CanonicalSingleCellDataset,
    partition: SplitPartition,
    rows: tuple[int, ...],
    assignments: dict[str, AssignedGroup],
    expectations: tuple[PublicationMetadataExpectation, ...],
) -> MetadataPartitionReport:
    groups = groups_by_partition(assignments, partition)
    return MetadataPartitionReport(
        partition=partition,
        observation_count=len(rows),
        feature_count=len(dataset.features),
        group_ids=groups,
        held_out_groups=groups if partition is SplitPartition.TEST else (),
        comparisons=_compare_rows(dataset, rows, assignments, expectations),
    )


def _compare(
    dataset: CanonicalSingleCellDataset,
    assignments: dict[str, AssignedGroup],
    expectations: tuple[PublicationMetadataExpectation, ...],
) -> tuple[MetadataComparison, ...]:
    return _compare_rows(
        dataset,
        tuple(range(len(dataset.observations))),
        assignments,
        expectations,
    )


def _compare_rows(
    dataset: CanonicalSingleCellDataset,
    rows: tuple[int, ...],
    assignments: dict[str, AssignedGroup],
    expectations: tuple[PublicationMetadataExpectation, ...],
) -> tuple[MetadataComparison, ...]:
    return tuple(
        _comparison(
            expectation, observed_value(dataset, rows, assignments, expectation.metric)
        )
        for expectation in expectations
    )


def _comparison(
    expectation: PublicationMetadataExpectation,
    observed: MetadataObservedValue,
) -> MetadataComparison:
    match expectation.kind:
        case MetadataExpectationKind.NOT_REPORTED:
            status = MetadataConcordance.NOT_REPORTED
        case MetadataExpectationKind.EXACT:
            status = _exact_status(expectation, observed)
        case MetadataExpectationKind.SET:
            status = (
                MetadataConcordance.MATCH
                if expectation.values == observed.values
                else MetadataConcordance.MISMATCH
            )
        case MetadataExpectationKind.RANGE:
            status = _range_status(expectation, observed)
        case MetadataExpectationKind.APPROXIMATE:
            status = _approximate_status(expectation, observed)
    return MetadataComparison(expectation=expectation, observed=observed, status=status)


def _exact_status(
    expectation: PublicationMetadataExpectation,
    observed: MetadataObservedValue,
) -> MetadataConcordance:
    matches = (
        expectation.expected_count == observed.count
        if expectation.expected_count is not None
        else expectation.expected_distribution == observed.distribution
    )
    return MetadataConcordance.MATCH if matches else MetadataConcordance.MISMATCH


def _range_status(
    expectation: PublicationMetadataExpectation,
    observed: MetadataObservedValue,
) -> MetadataConcordance:
    if (
        observed.count is None
        or expectation.lower_bound is None
        or expectation.upper_bound is None
    ):
        return MetadataConcordance.MISMATCH
    matches = expectation.lower_bound <= observed.count <= expectation.upper_bound
    return MetadataConcordance.MATCH if matches else MetadataConcordance.MISMATCH


def _approximate_status(
    expectation: PublicationMetadataExpectation,
    observed: MetadataObservedValue,
) -> MetadataConcordance:
    if (
        observed.count is None
        or expectation.expected_count is None
        or expectation.tolerance is None
    ):
        return MetadataConcordance.MISMATCH
    matches = abs(observed.count - expectation.expected_count) <= expectation.tolerance
    return MetadataConcordance.MATCH if matches else MetadataConcordance.MISMATCH
