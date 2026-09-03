"""Deterministic normalization for unordered metadata expectation values."""

from bioml_data._metadata_concordance_models import (
    InvalidMetadataExpectationError,
    MetadataCount,
)


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
    if any(value is not None and value < 0 for value in counts):
        raise InvalidMetadataExpectationError(
            detail="metadata count bounds and tolerance must be non-negative"
        )
    if any(not value.strip() for value in categories):
        raise InvalidMetadataExpectationError(
            detail="metadata set values must be non-empty"
        )
