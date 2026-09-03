"""Deterministic normalization for unordered metadata expectation values."""

from bioml_data._metadata_concordance_models import MetadataCount


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
