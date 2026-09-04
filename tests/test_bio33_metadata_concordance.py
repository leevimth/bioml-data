"""BIO-33 publication metadata comparison scenarios."""

import bioml_data as bio
from bioml_data._split import SplitPartition
from bioml_data.datasets.pancreas import PANCREAS_LODO_COHORT_METADATA

from ._metadata_concordance_helpers import metadata_dataset, metadata_scope
from ._single_cell_fixtures import make_split


def test_pancreas_lodo_whole_cohort_metadata_is_recorded() -> None:
    # Given: dimensions reported for the four historical pancreas cohorts.
    # When: the publication metadata is read from the package.

    # Then: only directly reported whole-cohort values are retained.
    assert [
        (item.study, item.observation_count) for item in PANCREAS_LODO_COHORT_METADATA
    ] == [
        ("Baron Human", 8_569),
        ("Muraro", 2_122),
        ("Segerstolpe", 2_133),
        ("Xin", 1_449),
    ]
    assert [item.feature_count for item in PANCREAS_LODO_COHORT_METADATA] == [
        17_499,
        18_915,
        22_757,
        33_889,
    ]
    assert [item.distinct_label_count for item in PANCREAS_LODO_COHORT_METADATA] == [
        14,
        9,
        13,
        4,
    ]


def test_bio33_compares_train_and_test_sample_dimension_and_labels() -> None:
    # Given: a canonical fixture and a realized train/validation/test assignment.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    scope = metadata_scope()
    expectations = (
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope, metric=bio.MetadataMetric.OBSERVATION_COUNT
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope, metric=bio.MetadataMetric.FEATURE_COUNT
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope, metric=bio.MetadataMetric.LABEL_COUNTS
        ),
        *(
            bio.PublicationMetadataExpectation.count(
                scope=scope,
                partition=partition,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                expected=expected,
            )
            for partition, expected in (
                (SplitPartition.TRAIN, 4),
                (SplitPartition.TEST, 1),
            )
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=SplitPartition.VALIDATION,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
        ),
        bio.PublicationMetadataExpectation.count(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.FEATURE_COUNT,
            expected=3,
        ),
        bio.PublicationMetadataExpectation.distribution(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.LABEL_COUNTS,
            expected=(bio.MetadataCount(value="fibroblast", count=1),),
        ),
        *(
            bio.PublicationMetadataExpectation.not_reported(
                scope=scope,
                partition=partition,
                metric=metric,
            )
            for partition in (SplitPartition.TRAIN, SplitPartition.VALIDATION)
            for metric in (
                bio.MetadataMetric.FEATURE_COUNT,
                bio.MetadataMetric.LABEL_COUNTS,
            )
        ),
    )

    # When: whole and realized partition metadata are compared.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=expectations
    )

    # Then: the published comparison distinguishes match and unknown evidence.
    train = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TRAIN
    )
    test = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TEST
    )
    assert train.comparisons[0].status is bio.MetadataConcordance.MATCH
    assert test.comparisons[0].status is bio.MetadataConcordance.MATCH
    assert test.comparisons[1].status is bio.MetadataConcordance.MATCH
    assert test.comparisons[2].status is bio.MetadataConcordance.MATCH
    assert all(
        comparison.status is bio.MetadataConcordance.NOT_REPORTED
        for comparison in train.comparisons[1:]
    )


def test_bio33_marks_a_partition_metadata_mismatch() -> None:
    # Given: a paper claim that disagrees with the realized test sample count.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    scope = metadata_scope()
    expectations = (
        bio.PublicationMetadataExpectation.not_reported(scope=scope, metric=metric)
        for metric in (
            bio.MetadataMetric.OBSERVATION_COUNT,
            bio.MetadataMetric.FEATURE_COUNT,
            bio.MetadataMetric.LABEL_COUNTS,
        )
    )
    all_expectations = (
        *expectations,
        *(
            bio.PublicationMetadataExpectation.not_reported(
                scope=scope, partition=partition, metric=metric
            )
            for partition in (SplitPartition.TRAIN, SplitPartition.VALIDATION)
            for metric in (
                bio.MetadataMetric.FEATURE_COUNT,
                bio.MetadataMetric.LABEL_COUNTS,
            )
        ),
        *(
            bio.PublicationMetadataExpectation.count(
                scope=scope,
                partition=partition,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                expected=99 if partition is SplitPartition.TEST else 4,
            )
            for partition in (SplitPartition.TRAIN, SplitPartition.TEST)
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=SplitPartition.VALIDATION,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.FEATURE_COUNT,
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.LABEL_COUNTS,
        ),
    )

    # When: the mismatching train/test metadata is compared.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=all_expectations
    )

    # Then: only the incorrect test claim is marked mismatch.
    test = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TEST
    )
    assert test.comparisons[0].status is bio.MetadataConcordance.MISMATCH
