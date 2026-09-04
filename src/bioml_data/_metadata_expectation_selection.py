"""Selection and coverage checks for publication metadata expectations."""

from bioml_data._metadata_concordance_models import (
    MetadataExpectationScopeMismatchError,
    MetadataFoldId,
)
from bioml_data._metadata_expectations import PublicationMetadataExpectation
from bioml_data._split import SplitPartition


def require_scoped_expectations(
    expectations: tuple[PublicationMetadataExpectation, ...],
    *,
    partition: SplitPartition | None,
    fold: MetadataFoldId | None,
) -> tuple[PublicationMetadataExpectation, ...]:
    """Return explicit evidence for one realized comparison target."""
    selected = tuple(
        expectation
        for expectation in expectations
        if expectation.partition is partition and expectation.fold == fold
    )
    if not selected:
        _raise_missing_expectations(partition)
    return selected


def _raise_missing_expectations(partition: SplitPartition | None) -> None:
    if partition is None:
        field = "dataset_expectations"
        expected = "at least one whole-dataset expectation"
    else:
        field = "partition_expectations"
        expected = f"at least one {partition.value} partition expectation"
    raise MetadataExpectationScopeMismatchError(
        field=field,
        expected=expected,
        actual="none",
    )
