"""Construction and validation of publication metadata expectations."""

from dataclasses import dataclass

from bioml_data._metadata_concordance_models import (
    InvalidMetadataExpectationError,
    MetadataCount,
    MetadataExpectationKind,
    MetadataExpectationScope,
    MetadataFoldId,
    MetadataMetric,
)
from bioml_data._metadata_normalization import (
    canonical_distribution,
    canonical_values,
    validate_metadata_values,
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
        object.__setattr__(self, "values", canonical_values(self.values))
        object.__setattr__(
            self,
            "expected_distribution",
            canonical_distribution(self.expected_distribution),
        )
        _validate_shape(self)
        validate_metadata_values(
            (
                self.expected_count,
                self.lower_bound,
                self.upper_bound,
                self.tolerance,
            ),
            self.values,
        )


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
            valid = _valid_exact(expectation, scalar, distribution)
        case MetadataExpectationKind.SET:
            valid = (
                not scalar
                and not distribution
                and bool(expectation.values)
                and _empty_numeric_fields(expectation)
                and not expectation.expected_distribution
            )
        case MetadataExpectationKind.NOT_REPORTED:
            valid = _empty_expectation(expectation)
        case MetadataExpectationKind.RANGE:
            valid = _valid_range(expectation, scalar)
        case MetadataExpectationKind.APPROXIMATE:
            valid = _valid_approximation(expectation, scalar)
    if not valid:
        raise InvalidMetadataExpectationError(
            detail=(
                f"invalid {expectation.kind.value} expectation for "
                f"{expectation.metric.value}"
            )
        )


def _empty_expectation(expectation: PublicationMetadataExpectation) -> bool:
    return (
        _empty_numeric_fields(expectation)
        and not expectation.values
        and not expectation.expected_distribution
    )


def _empty_numeric_fields(expectation: PublicationMetadataExpectation) -> bool:
    return (
        expectation.expected_count is None
        and expectation.lower_bound is None
        and expectation.upper_bound is None
        and expectation.tolerance is None
    )


def _valid_exact(
    expectation: PublicationMetadataExpectation,
    scalar: bool,
    distribution: bool,
) -> bool:
    scalar_claim = (
        scalar
        and expectation.expected_count is not None
        and expectation.lower_bound is None
        and expectation.upper_bound is None
        and expectation.tolerance is None
        and not expectation.values
        and not expectation.expected_distribution
    )
    distribution_claim = (
        distribution
        and bool(expectation.expected_distribution)
        and _empty_numeric_fields(expectation)
        and not expectation.values
    )
    return scalar_claim or distribution_claim


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
