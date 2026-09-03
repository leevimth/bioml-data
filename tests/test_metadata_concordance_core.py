"""Core whole-dataset and realized-partition concordance scenarios."""

from dataclasses import replace

import bioml_data as bio
from bioml_data._split import (
    PartitionGroupCounts,
    SplitPartition,
    assignment_receipt_identity,
)
from bioml_data.datasets.tms_aorta._identity import TMS_AORTA_ARTIFACT_SCOPE
from bioml_data.datasets.tms_aorta._metadata_expectations import (
    TMS_AORTA_ARTIFACT_AUDIT_EXPECTATIONS,
)

from ._metadata_concordance_helpers import metadata_dataset, metadata_scope
from ._single_cell_fixtures import make_split


def test_tms_aorta_artifact_expectations_are_slice_scoped() -> None:
    # Given: source-audit metadata for the pinned TMS Aorta artifact.
    expectations = TMS_AORTA_ARTIFACT_AUDIT_EXPECTATIONS

    # When: their scope and cardinality claims are inspected.
    scope = expectations[0].scope

    # Then: the 906-by-22,966 statistics cannot stand in for the full TMS atlas.
    assert scope.dataset.name == "tms-aorta"
    assert scope.artifact == TMS_AORTA_ARTIFACT_SCOPE
    assert expectations[0].expected_count == 906
    assert expectations[1].expected_count == 22_966


def test_tms_aorta_artifact_expectations_cover_each_realized_partition() -> None:
    # Given: the source-audit expectation tuple and a valid grouped split receipt.
    dataset = metadata_dataset()
    assignment = make_split(dataset)

    # When: a caller compares the exact-scope tuple against each realized partition.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=TMS_AORTA_ARTIFACT_AUDIT_EXPECTATIONS,
    )

    # Then: no train, validation, or test report has silently empty evidence.
    assert all(item.comparisons for item in report.partition_reports)
    assert all(
        item.comparisons[0].status is bio.MetadataConcordance.NOT_REPORTED
        for item in report.partition_reports
    )


def test_compare_reports_whole_dataset_and_each_realized_partition() -> None:
    # Given: exact-scope expectations for the complete artifact and held-out test set.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    scope = metadata_scope()
    expectations = (
        bio.PublicationMetadataExpectation.count(
            scope=scope, metric=bio.MetadataMetric.OBSERVATION_COUNT, expected=6
        ),
        bio.PublicationMetadataExpectation.count(
            scope=scope, metric=bio.MetadataMetric.FEATURE_COUNT, expected=3
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
        bio.PublicationMetadataExpectation.count(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            expected=1,
        ),
        bio.PublicationMetadataExpectation.set_values(
            scope=scope,
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.GROUP_IDS,
            expected=("mouse-c",),
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=scope,
            partition=SplitPartition.VALIDATION,
            metric=bio.MetadataMetric.LABEL_COUNTS,
        ),
    )

    # When: the prepared data and realized split are compared with the evidence.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=expectations
    )

    # Then: whole-data and train/validation/test outputs are separated and explicit.
    assert report.dataset_comparisons[0].status is bio.MetadataConcordance.MATCH
    assert {item.partition for item in report.partition_reports} == {
        SplitPartition.TRAIN,
        SplitPartition.VALIDATION,
        SplitPartition.TEST,
    }
    test = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TEST
    )
    assert test.observation_count == 1
    assert test.held_out_groups == ("mouse-c",)
    validation = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.VALIDATION
    )
    assert validation.comparisons[0].status is bio.MetadataConcordance.NOT_REPORTED
    assert report.cross_partition_groups == ()
    assert report.covered_observation_count == 6


def test_compare_omits_empty_validation_partition_from_receipt_report() -> None:
    # Given: a valid five-train, one-test receipt with no validation observations.
    dataset = metadata_dataset()
    original = make_split(dataset)
    assignments = tuple(
        replace(
            item,
            partition=(
                SplitPartition.TEST
                if item.observation_id == "cell-6"
                else SplitPartition.TRAIN
            ),
        )
        for item in original.assignments
    )
    receipt = replace(
        original,
        assignments=assignments,
        realized_group_counts=PartitionGroupCounts(train=4, validation=0, test=1),
    )
    assignment = replace(
        receipt, assignment_identity=assignment_receipt_identity(receipt)
    )
    expectations = tuple(
        bio.PublicationMetadataExpectation.not_reported(
            scope=metadata_scope(),
            partition=partition,
            metric=bio.MetadataMetric.LABEL_COUNTS,
        )
        for partition in SplitPartition
    )

    # When: concordance reports only partitions realized by the receipt.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=expectations
    )

    # Then: no empty validation report or comparison is synthesized.
    assert tuple(item.partition for item in report.partition_reports) == (
        SplitPartition.TRAIN,
        SplitPartition.TEST,
    )
    assert all(
        item.partition is not SplitPartition.VALIDATION
        for item in report.partition_reports
    )


def test_compare_marks_not_reported_metadata_as_unknown_not_a_match() -> None:
    # Given: evidence that does not report a partition's assay metadata.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    expectation = bio.PublicationMetadataExpectation.not_reported(
        scope=metadata_scope(),
        partition=SplitPartition.TEST,
        metric=bio.MetadataMetric.ASSAY_VALUES,
    )

    # When: the unknown evidence is rendered in a concordance report.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=(expectation,)
    )

    # Then: it remains explicit unknown evidence and never counts as a pass.
    comparison = report.partition_reports[-1].comparisons[0]
    assert comparison.status is bio.MetadataConcordance.NOT_REPORTED
    assert comparison.observed.values == ("FACS",)


def test_compare_supports_range_and_approximate_count_evidence() -> None:
    # Given: two count claims reported with bounded rather than exact precision.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    expectations = (
        bio.PublicationMetadataExpectation.within_range(
            scope=metadata_scope(),
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            lower_bound=5,
            upper_bound=7,
        ),
        bio.PublicationMetadataExpectation.approximate(
            scope=metadata_scope(),
            metric=bio.MetadataMetric.FEATURE_COUNT,
            expected=4,
            tolerance=1,
        ),
    )

    # When: complete prepared data are compared against both precision types.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=expectations
    )

    # Then: each precision type preserves reported tolerance rather than guessing.
    assert tuple(item.status for item in report.dataset_comparisons) == (
        bio.MetadataConcordance.MATCH,
        bio.MetadataConcordance.MATCH,
    )
