"""Adversarial metadata expectation and evidence validation scenarios."""

import pytest

import bioml_data as bio

from ._metadata_concordance_helpers import metadata_dataset, metadata_scope
from ._single_cell_fixtures import make_split


@pytest.mark.parametrize(
    "uri",
    [
        "https://user:password@example.org/source",
        "https://example.org/source?token=secret",
        "https://example.org/source#section",
        "https://127.0.0.1/source",
        "https://127.1/source",
        "https://127.0.1/source",
        "https://0x7f.0x0.0x0.0x1/source",
        "https://0X7F.0X0.0X0.0X1/source",
        "https://0177.00.00.01/source",
        "https://100.64.0.1/source",
        "https://169.254.1.1/source",
        "https://224.0.0.1/source",
        "https://240.0.0.1/source",
        "https://localhost/source",
        "https://example.org/%zz",
    ],
)
def test_metadata_citation_rejects_non_public_or_credentialed_uri(uri: str) -> None:
    # Given: a metadata citation URI that cannot safely identify public evidence.

    # When: citation is parsed at the metadata expectation boundary.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        _ = bio.MetadataCitation(title="Evidence", uri=uri)

    # Then: no unsafe endpoint becomes a publication-bound expectation.


def test_metadata_citation_accepts_public_dns_domain() -> None:
    # Given: a conventional public DNS citation host.

    # When: the citation is parsed at the metadata expectation boundary.
    citation = bio.MetadataCitation(
        title="Public evidence",
        uri="https://example.org/source",
    )

    # Then: syntactic numeric-IP protections do not reject DNS names.
    assert citation.uri == "https://example.org/source"


def test_metadata_expectation_rejects_ignored_contradictory_fields() -> None:
    # Given: an exact count claim with an unrelated tolerance field.

    # When: ambiguous expectation is constructed directly.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        _ = bio.PublicationMetadataExpectation(
            scope=metadata_scope(),
            partition=None,
            fold=None,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            kind=bio.MetadataExpectationKind.EXACT,
            expected_count=6,
            tolerance=1,
        )

    # Then: no field is silently discarded by a comparison kind.


def test_metadata_expectation_canonicalizes_unordered_values() -> None:
    # Given: equivalent unordered categories with repeated input values.
    set_expectation = bio.PublicationMetadataExpectation(
        scope=metadata_scope(),
        partition=None,
        fold=None,
        metric=bio.MetadataMetric.TISSUE_VALUES,
        kind=bio.MetadataExpectationKind.SET,
        values=("Aorta", "Aorta", "Heart"),
    )
    distribution_expectation = bio.PublicationMetadataExpectation(
        scope=metadata_scope(),
        partition=None,
        fold=None,
        metric=bio.MetadataMetric.LABEL_COUNTS,
        kind=bio.MetadataExpectationKind.EXACT,
        expected_distribution=(
            bio.MetadataCount(value="fibroblast", count=2),
            bio.MetadataCount(value="endothelial", count=1),
            bio.MetadataCount(value="fibroblast", count=3),
        ),
    )

    # When: immutable expectation values are normalized at construction.

    # Then: comparison does not depend on input order or duplicate representation.
    assert set_expectation.values == ("Aorta", "Heart")
    assert distribution_expectation.expected_distribution == (
        bio.MetadataCount(value="endothelial", count=1),
        bio.MetadataCount(value="fibroblast", count=5),
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("expected_count", 6.0),
        ("expected_count", True),
        ("tolerance", 1.0),
        ("tolerance", True),
        ("lower_bound", 0.0),
        ("lower_bound", True),
        ("upper_bound", 7.0),
        ("upper_bound", True),
    ],
)
def test_metadata_expectation_rejects_non_exact_runtime_integer(
    field: str,
    value: float | bool,
) -> None:
    # Given: a valid expectation changed by an untyped runtime boundary.
    expectation = _expectation_for_numeric_field(field)
    object.__setattr__(expectation, field, value)

    # When: construction validation is applied to the runtime value.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        expectation.__post_init__()

    # Then: booleans and floats cannot stand in for metadata integer fields.


@pytest.mark.parametrize("value", [True, 6.0])
def test_metadata_count_rejects_non_exact_runtime_integer(value: float | bool) -> None:
    # Given: a valid categorical count changed by an untyped runtime boundary.
    count = bio.MetadataCount(value="endothelial", count=1)
    object.__setattr__(count, "count", value)

    # When: count validation is reapplied.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        count.__post_init__()

    # Then: a categorical count remains an exact non-negative integer.


def test_compare_rejects_expectations_for_a_different_fold() -> None:
    # Given: evidence scoped to a named fold and a different requested fold.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    expectation = bio.PublicationMetadataExpectation(
        scope=metadata_scope(),
        partition=None,
        fold=bio.MetadataFoldId("fold-1"),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        kind=bio.MetadataExpectationKind.EXACT,
        expected_count=6,
    )

    # When: concordance would otherwise filter evidence to no comparisons.
    with pytest.raises(bio.MetadataExpectationScopeMismatchError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset,
            assignment,
            expectations=(expectation,),
            fold=bio.MetadataFoldId("fold-2"),
        )

    # Then: a fold mismatch is explicit instead of a silently empty report.
    assert captured.value.field == "fold"


def _expectation_for_numeric_field(field: str) -> bio.PublicationMetadataExpectation:
    match field:
        case "expected_count":
            return bio.PublicationMetadataExpectation.count(
                scope=metadata_scope(),
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                expected=6,
            )
        case "tolerance":
            return bio.PublicationMetadataExpectation.approximate(
                scope=metadata_scope(),
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                expected=6,
                tolerance=1,
            )
        case "lower_bound" | "upper_bound":
            return bio.PublicationMetadataExpectation.within_range(
                scope=metadata_scope(),
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                lower_bound=5,
                upper_bound=7,
            )
        case _:  # pragma: no cover - parameter fixture is the closed boundary.
            pytest.fail("unsupported numeric field")
