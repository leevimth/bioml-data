"""BIO-33 publication metadata comparison scenarios."""

import bioml_data as bio
from bioml_data._split import SplitPartition
from bioml_data.datasets.pancreas import (
    PANCREAS_LODO_BENCHMARK_METADATA,
    PANCREAS_LODO_COHORT_METADATA,
)

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
    assert tuple(item.sample_count for item in PANCREAS_LODO_BENCHMARK_METADATA) == (
        5_707,
        1_554,
        1_440,
        1_449,
    )
    assert tuple(
        tuple(label.count for label in item.label_counts)
        for item in PANCREAS_LODO_BENCHMARK_METADATA
    ) == (
        (2_326, 2_525, 601, 255),
        (812, 448, 193, 101),
        (872, 263, 110, 195),
        (855, 466, 46, 82),
    )


def _expectations(
    scope: bio.MetadataExpectationScope,
    *,
    sample_count: int,
    test_sample_count: int = 1,
) -> tuple[bio.PublicationMetadataExpectation, ...]:
    """Build whole claims, direct test evidence, and unknown fold evidence."""
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
        for partition in (SplitPartition.TRAIN, SplitPartition.VALIDATION)
        for metric in (
            bio.MetadataMetric.OBSERVATION_COUNT,
            bio.MetadataMetric.FEATURE_COUNT,
            bio.MetadataMetric.LABEL_COUNTS,
        )
    )
    direct_test = (
        bio.PublicationMetadataExpectation.count(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            expected=test_sample_count,
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.FEATURE_COUNT,
        ),
        bio.PublicationMetadataExpectation.distribution(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.LABEL_COUNTS,
            expected=(bio.MetadataCount(value="fibroblast", count=1),),
        ),
    )
    return whole + unknown_partitions + direct_test


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

    # Then: whole and directly reported test values match; fold features are unknown.
    assert (
        tuple(item.status for item in report.dataset_comparisons)
        == (bio.MetadataConcordance.MATCH,) * 3
    )
    assert {item.partition for item in report.partition_reports} == set(SplitPartition)
    train_and_validation = tuple(
        partition
        for partition in report.partition_reports
        if partition.partition is not SplitPartition.TEST
    )
    assert all(
        comparison.status is bio.MetadataConcordance.NOT_REPORTED
        for partition in train_and_validation
        for comparison in partition.comparisons
    )
    test = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TEST
    )
    assert tuple(item.status for item in test.comparisons) == (
        bio.MetadataConcordance.MATCH,
        bio.MetadataConcordance.NOT_REPORTED,
        bio.MetadataConcordance.MATCH,
    )


def test_bio33_marks_test_sample_mismatch_without_deriving_fold_metadata() -> None:
    # Given: a test-sample claim that disagrees with the synthetic test fixture.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    scope = metadata_scope()

    # When: the mismatching test sample count is compared.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=_expectations(scope, sample_count=6, test_sample_count=99),
    )

    # Then: only the direct test sample claim mismatches; train stays unknown.
    test = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TEST
    )
    assert test.comparisons[0].status is bio.MetadataConcordance.MISMATCH
    assert all(
        comparison.status is bio.MetadataConcordance.NOT_REPORTED
        for partition in report.partition_reports
        if partition.partition is not SplitPartition.TEST
        for comparison in partition.comparisons
    )
