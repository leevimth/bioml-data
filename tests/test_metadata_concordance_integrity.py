"""Metadata concordance scope and split-receipt integrity scenarios."""

from dataclasses import replace

import pytest

import bioml_data as bio
from bioml_data._domain import DatasetName, DatasetSnapshotIdentity, DatasetVersion
from bioml_data._split import (
    PartitionGroupCounts,
    SplitAssignment,
    SplitPartition,
    assignment_receipt_identity,
)

from ._metadata_concordance_helpers import metadata_dataset, metadata_scope
from ._single_cell_fixtures import make_split


def test_compare_accepts_multiple_citations_for_one_scientific_scope() -> None:
    # Given: source-release and primary-paper citations for the same data scope.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    source_scope = metadata_scope()
    paper_scope = replace(
        source_scope,
        citation=bio.MetadataCitation(
            title="Tabula Muris Senis primary paper",
            uri="https://www.nature.com/articles/s41586-020-2496-1",
        ),
    )
    expectations = (
        bio.PublicationMetadataExpectation.count(
            scope=source_scope,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            expected=6,
        ),
        bio.PublicationMetadataExpectation.count(
            scope=paper_scope,
            metric=bio.MetadataMetric.FEATURE_COUNT,
            expected=3,
        ),
    )

    # When: both evidence statements are compared.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=expectations
    )

    # Then: citations remain provenance without blocking compatible evidence.
    assert tuple(item.status for item in report.dataset_comparisons) == (
        bio.MetadataConcordance.MATCH,
        bio.MetadataConcordance.MATCH,
    )


def test_compare_rejects_publication_expectation_from_global_dataset_scope() -> None:
    # Given: a whole-atlas expectation that names a different snapshot identity.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    global_scope = replace(
        metadata_scope(),
        dataset=DatasetSnapshotIdentity(
            name=DatasetName("tabula-muris-senis"),
            version=DatasetVersion("primary-paper"),
        ),
    )
    expectation = bio.PublicationMetadataExpectation.count(
        scope=global_scope,
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=356_213,
    )

    # When: the global expectation is applied to the Aorta slice.
    with pytest.raises(bio.MetadataExpectationScopeMismatchError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset, assignment, expectations=(expectation,)
        )

    # Then: specific snapshot mismatch is visible instead of becoming a false fail.
    assert captured.value.field == "dataset"


def test_compare_enforces_partition_coverage_and_reports_group_overlap() -> None:
    # Given: an assignment that covers every cell but splits one mouse.
    dataset = metadata_dataset()
    original = make_split(dataset)
    assignments = tuple(
        SplitAssignment(
            observation_id=item.observation_id,
            group=item.group,
            partition=(
                SplitPartition.TEST
                if item.observation_id == "cell-2"
                else item.partition
            ),
        )
        for item in original.assignments
    )
    receipt = replace(
        original,
        assignments=assignments,
        realized_group_counts=PartitionGroupCounts(train=3, validation=1, test=2),
    )
    split_groups = replace(
        receipt, assignment_identity=assignment_receipt_identity(receipt)
    )
    expectation = bio.PublicationMetadataExpectation.count(
        scope=metadata_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: independent metadata check receives the split receipt.
    report = bio.compare_metadata_concordance(
        dataset, split_groups, expectations=(expectation,)
    )

    # Then: coverage holds while group overlap stays visible for leakage audit.
    assert report.covered_observation_count == 6
    assert report.cross_partition_groups == ("mouse-a",)


def test_compare_reports_each_group_once_when_multiple_cells_share_a_mouse() -> None:
    # Given: a train partition containing both cells from mouse-a.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    expectation = bio.PublicationMetadataExpectation.not_reported(
        scope=metadata_scope(),
        partition=SplitPartition.TRAIN,
        metric=bio.MetadataMetric.GROUP_IDS,
    )

    # When: a partition report is materialized from the grouped receipt.
    report = bio.compare_metadata_concordance(
        dataset, assignment, expectations=(expectation,)
    )

    # Then: group identifiers are distinct, sorted biological groups.
    train = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TRAIN
    )
    assert train.group_ids == tuple(sorted(set(train.group_ids)))
    assert train.group_ids.count("mouse-a") == 1


def test_compare_rejects_assignment_that_does_not_cover_prepared_rows() -> None:
    # Given: a receipt with one prepared cell removed from partition assignment.
    dataset = metadata_dataset()
    original = make_split(dataset)
    incomplete = replace(original, assignments=original.assignments[:-1])
    expectation = bio.PublicationMetadataExpectation.count(
        scope=metadata_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: concordance receives an incomplete partition receipt.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset, incomplete, expectations=(expectation,)
        )

    # Then: no partial train/test comparison is emitted.
    assert captured.value.violation is bio.MetadataPartitionViolation.COVERAGE


def test_compare_rejects_stale_assignment_identity() -> None:
    # Given: a receipt whose header seed changed after its identity was recorded.
    dataset = metadata_dataset()
    stale = replace(make_split(dataset), seed=99)
    expectation = bio.PublicationMetadataExpectation.count(
        scope=metadata_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: metadata concordance consumes the stale receipt.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset, stale, expectations=(expectation,)
        )

    # Then: snapshot/protocol/seed-bound identity cannot be forged stale.
    assert captured.value.violation is bio.MetadataPartitionViolation.IDENTITY


def test_compare_rejects_assignment_group_not_in_canonical_grouping_column() -> None:
    # Given: a receipt with recomputed identity but forged donor group membership.
    dataset = metadata_dataset()
    original = make_split(dataset)
    assignments = tuple(
        replace(item, group="forged-group")
        if item.observation_id == "cell-1"
        else item
        for item in original.assignments
    )
    receipt = replace(
        original,
        assignments=assignments,
        realized_group_counts=PartitionGroupCounts(train=4, validation=1, test=1),
        group_count=6,
    )
    forged = replace(receipt, assignment_identity=assignment_receipt_identity(receipt))
    expectation = bio.PublicationMetadataExpectation.count(
        scope=metadata_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: concordance validates assignment against canonical split metadata.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset, forged, expectations=(expectation,)
        )

    # Then: receipt rows cannot substitute arbitrary biological groups.
    assert captured.value.violation is bio.MetadataPartitionViolation.GROUPING
