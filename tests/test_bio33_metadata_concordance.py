"""BIO-33 publication metadata comparison scenarios."""

import bioml_data as bio
from bioml_data._split import SplitPartition
from bioml_data.datasets.pancreas import PANCREAS_LODO_COHORT_METADATA

from ._metadata_concordance_helpers import metadata_dataset, metadata_scope
from ._single_cell_fixtures import make_split


def test_pancreas_publication_cohort_metadata_is_exactly_recorded() -> None:
    # Given: the four whole-cohort dimensions explicitly reported by the paper.
    # When: the package publication definitions are read.
    actual = tuple(
        (
            item.study,
            item.sample_count,
            item.feature_dimension,
            item.distinct_label_count,
        )
        for item in PANCREAS_LODO_COHORT_METADATA
    )

    # Then: only those reported whole-cohort values are retained.
    assert actual == (
        ("Baron Human", 8_569, 17_499, 14),
        ("Muraro", 2_122, 18_915, 9),
        ("Segerstolpe", 2_133, 22_757, 13),
        ("Xin", 1_449, 33_889, 4),
    )


def _expectations(
    scope: bio.MetadataExpectationScope,
    *,
    sample_count: int,
) -> tuple[bio.PublicationMetadataExpectation, ...]:
    """Build whole-dataset claims and unknown evidence for all split slots."""
    whole = (
        bio.PublicationMetadataExpectation.count(
            scope=scope,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            expected=sample_count,
        ),
        bio.PublicationMetadataExpectation.count(
            scope=scope,
            metric=bio.MetadataMetric.FEATURE_COUNT,
            expected=3,
        ),
        bio.PublicationMetadataExpectation.distribution(
            scope=scope,
            metric=bio.MetadataMetric.LABEL_COUNTS,
            expected=(
                bio.MetadataCount(value="endothelial", count=2),
                bio.MetadataCount(value="fibroblast", count=2),
                bio.MetadataCount(value="smooth-muscle", count=2),
            ),
        ),
    )
    unknown_partitions = tuple(
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=partition,
            metric=metric,
        )
        for partition in SplitPartition
        for metric in (
            bio.MetadataMetric.OBSERVATION_COUNT,
            bio.MetadataMetric.FEATURE_COUNT,
            bio.MetadataMetric.LABEL_COUNTS,
        )
    )
    return whole + unknown_partitions


def test_bio33_matches_whole_fixture_and_keeps_partitions_not_reported() -> None:
    # Given: a package-created typed fixture, with no publication fold details.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    scope = metadata_scope()

    # When: whole and realized partition metadata are compared.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=_expectations(scope, sample_count=6),
    )

    # Then: whole values match, while train/test (and validation) stay unknown.
    assert (
        tuple(item.status for item in report.dataset_comparisons)
        == (bio.MetadataConcordance.MATCH,) * 3
    )
    assert {item.partition for item in report.partition_reports} == set(SplitPartition)
    assert all(
        comparison.status is bio.MetadataConcordance.NOT_REPORTED
        for partition in report.partition_reports
        for comparison in partition.comparisons
    )


def test_bio33_marks_whole_sample_mismatch_without_deriving_fold_metadata() -> None:
    # Given: a publication claim that disagrees with the synthetic whole fixture.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    scope = metadata_scope()

    # When: the mismatching whole sample count is compared.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=_expectations(scope, sample_count=99),
    )

    # Then: only the whole sample claim mismatches; every partition is unknown.
    assert report.dataset_comparisons[0].status is bio.MetadataConcordance.MISMATCH
    assert all(
        comparison.status is bio.MetadataConcordance.NOT_REPORTED
        for partition in report.partition_reports
        for comparison in partition.comparisons
    )
