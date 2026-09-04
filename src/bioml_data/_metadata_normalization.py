"""Deterministic normalization for unordered metadata expectation values."""

from typing import Protocol

from bioml_data._metadata_concordance_models import (
    InvalidMetadataExpectationError,
    MetadataCount,
)


class NumericMetadataExpectation(Protocol):
    """Numeric fields required to validate range and approximation evidence."""

    @property
    def expected_count(self) -> int | None: ...

    @property
    def lower_bound(self) -> int | None: ...

    @property
    def upper_bound(self) -> int | None: ...

    @property
    def tolerance(self) -> int | None: ...

    @property
    def values(self) -> tuple[str, ...]: ...

    @property
    def expected_distribution(self) -> tuple[MetadataCount, ...]: ...


def canonical_values(values: tuple[str, ...]) -> tuple[str, ...]:
    """Sort and deduplicate unordered categorical values."""
    return tuple(sorted(set(values)))


def canonical_distribution(
    values: tuple[MetadataCount, ...],
) -> tuple[MetadataCount, ...]:
    """Sort category counts after combining duplicate category declarations."""
    counts: dict[str, int] = {}
    for item in values:
        counts[item.value] = counts.get(item.value, 0) + item.count
    return tuple(
        MetadataCount(value=value, count=count)
        for value, count in sorted(counts.items())
    )


def validate_metadata_values(
    counts: tuple[int | None, ...],
    categories: tuple[str, ...],
) -> None:
    """Reject negative numeric values and blank categorical declarations."""
    if any(value is not None and type(value) is not int for value in counts):
        raise InvalidMetadataExpectationError(
            detail="metadata count bounds and tolerance must be exact integers"
        )
    if any(value is not None and value < 0 for value in counts):
        raise InvalidMetadataExpectationError(
            detail="metadata count bounds and tolerance must be non-negative"
        )
    if any(not value.strip() for value in categories):
        raise InvalidMetadataExpectationError(
            detail="metadata set values must be non-empty"
        )


def valid_numeric_range(
    expectation: NumericMetadataExpectation,
    scalar: bool,
) -> bool:
    """Validate a bounded scalar expectation without importing its model."""
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


def valid_numeric_approximation(
    expectation: NumericMetadataExpectation,
    scalar: bool,
) -> bool:
    """Validate an approximate scalar expectation without importing its model."""
    return (
        scalar
        and expectation.expected_count is not None
        and expectation.tolerance is not None
        and expectation.lower_bound is None
        and expectation.upper_bound is None
        and not expectation.values
        and not expectation.expected_distribution
    )
