"""Construction and validation of publication metadata expectations."""

from dataclasses import dataclass
from typing import assert_never

from bioml_data._metadata_concordance_models import (
    InvalidMetadataExpectationError,
    MetadataCount,
    MetadataExpectationKind,
    MetadataExpectationScope,
    MetadataFoldId,
    MetadataMetric,
)
from bioml_data._split import SplitPartition


@dataclass(frozen=True, slots=True)
class PublicationMetadataExpectation:
    """One scoped claim from a publication or exact artifact evidence source."""

    scope: MetadataExpectationScope
    partition: SplitPartition | None
    fold: MetadataFoldId | None
    metric: MetadataMetric
    kind: MetadataExpectationKind
    expected_count: int | None = None
    lower_bound: int | None = None
    upper_bound: int | None = None
    tolerance: int | None = None
    values: tuple[str, ...] = ()
    expected_distribution: tuple[MetadataCount, ...] = ()

    @classmethod
    def count(
        cls,
        *,
        scope: MetadataExpectationScope,
        metric: MetadataMetric,
        expected: int,
        partition: SplitPartition | None = None,
    ) -> "PublicationMetadataExpectation":
        """Create an exact scalar expectation."""
        return cls(
            scope=scope,
            partition=partition,
            fold=None,
            metric=metric,
            kind=MetadataExpectationKind.EXACT,
            expected_count=expected,
        )

    @classmethod
    def distribution(
        cls,
        *,
        scope: MetadataExpectationScope,
        metric: MetadataMetric,
        expected: tuple[MetadataCount, ...],
        partition: SplitPartition | None = None,
    ) -> "PublicationMetadataExpectation":
        """Create an exact categorical-distribution expectation."""
        return cls(
            scope=scope,
            partition=partition,
            fold=None,
            metric=metric,
            kind=MetadataExpectationKind.EXACT,
            expected_distribution=expected,
        )

    @classmethod
    def set_values(
        cls,
        *,
        scope: MetadataExpectationScope,
        metric: MetadataMetric,
        expected: tuple[str, ...],
        partition: SplitPartition | None = None,
    ) -> "PublicationMetadataExpectation":
        """Create an exact unordered category-set expectation."""
        return cls(
            scope=scope,
            partition=partition,
            fold=None,
            metric=metric,
            kind=MetadataExpectationKind.SET,
            values=tuple(sorted(expected)),
        )

    @classmethod
    def within_range(
        cls,
        *,
        scope: MetadataExpectationScope,
        metric: MetadataMetric,
        lower_bound: int,
        upper_bound: int,
        partition: SplitPartition | None = None,
    ) -> "PublicationMetadataExpectation":
        """Create a bounded scalar expectation reported as a range."""
        return cls(
            scope=scope,
            partition=partition,
            fold=None,
            metric=metric,
            kind=MetadataExpectationKind.RANGE,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
        )

    @classmethod
    def approximate(
        cls,
        *,
        scope: MetadataExpectationScope,
        metric: MetadataMetric,
        expected: int,
        tolerance: int,
        partition: SplitPartition | None = None,
    ) -> "PublicationMetadataExpectation":
        """Create a scalar expectation with an explicit integer tolerance."""
        return cls(
            scope=scope,
            partition=partition,
            fold=None,
            metric=metric,
            kind=MetadataExpectationKind.APPROXIMATE,
            expected_count=expected,
            tolerance=tolerance,
        )

    @classmethod
    def not_reported(
        cls,
        *,
        scope: MetadataExpectationScope,
        metric: MetadataMetric,
        partition: SplitPartition | None = None,
    ) -> "PublicationMetadataExpectation":
        """Record that the evidence does not report a value for this metric."""
        return cls(
            scope=scope,
            partition=partition,
            fold=None,
            metric=metric,
            kind=MetadataExpectationKind.NOT_REPORTED,
        )

    def __post_init__(self) -> None:
        """Keep each evidence kind tied to one unambiguous value shape."""
        _validate_shape(self)
        _validate_nonnegative(self)


def _validate_shape(expectation: PublicationMetadataExpectation) -> None:
    scalar = expectation.metric in {
        MetadataMetric.OBSERVATION_COUNT,
        MetadataMetric.FEATURE_COUNT,
    }
    distribution = expectation.metric in {
        MetadataMetric.LABEL_COUNTS,
        MetadataMetric.OBSERVATIONS_PER_GROUP,
    }
    match expectation.kind:
        case MetadataExpectationKind.EXACT:
            valid = (scalar and expectation.expected_count is not None) or (
                distribution and bool(expectation.expected_distribution)
            )
        case MetadataExpectationKind.SET:
            valid = not scalar and not distribution and bool(expectation.values)
        case MetadataExpectationKind.NOT_REPORTED:
            valid = _empty_expectation(expectation)
        case MetadataExpectationKind.RANGE:
            valid = _valid_range(expectation, scalar)
        case MetadataExpectationKind.APPROXIMATE:
            valid = _valid_approximation(expectation, scalar)
        case unreachable:
            assert_never(unreachable)
    if not valid:
        raise InvalidMetadataExpectationError(
            detail=(
                f"invalid {expectation.kind.value} expectation for "
                f"{expectation.metric.value}"
            )
        )


def _empty_expectation(expectation: PublicationMetadataExpectation) -> bool:
    return (
        expectation.expected_count is None
        and not expectation.values
        and not expectation.expected_distribution
        and expectation.lower_bound is None
        and expectation.upper_bound is None
        and expectation.tolerance is None
    )


def _valid_range(expectation: PublicationMetadataExpectation, scalar: bool) -> bool:
    return (
        scalar
        and expectation.lower_bound is not None
        and expectation.upper_bound is not None
        and expectation.expected_count is None
        and expectation.tolerance is None
        and not expectation.values
        and not expectation.expected_distribution
        and expectation.lower_bound <= expectation.upper_bound
    )


def _valid_approximation(
    expectation: PublicationMetadataExpectation,
    scalar: bool,
) -> bool:
    return (
        scalar
        and expectation.expected_count is not None
        and expectation.tolerance is not None
        and expectation.lower_bound is None
        and expectation.upper_bound is None
        and not expectation.values
        and not expectation.expected_distribution
    )


def _validate_nonnegative(expectation: PublicationMetadataExpectation) -> None:
    values = (
        expectation.expected_count,
        expectation.lower_bound,
        expectation.upper_bound,
        expectation.tolerance,
    )
    if any(value is not None and value < 0 for value in values):
        raise InvalidMetadataExpectationError(
            detail="metadata count bounds and tolerance must be non-negative"
        )
    categories = tuple(item.value for item in expectation.expected_distribution)
    if len(set(categories)) != len(categories):
        raise InvalidMetadataExpectationError(
            detail="expected distribution categories must be unique"
        )
