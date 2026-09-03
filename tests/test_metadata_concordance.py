"""Publication-scoped metadata concordance scenarios."""

from dataclasses import replace

import pytest

import bioml_data as bio
from bioml_data._artifacts import ArtifactDerivation, TransformProtocolId
from bioml_data._domain import DatasetName, DatasetSnapshotIdentity, DatasetVersion
from bioml_data._split import SplitAssignment, SplitPartition
from bioml_data.datasets.tms_aorta._identity import (
    TMS_AORTA_ARTIFACT_SCOPE,
    TMS_AORTA_SOURCE_ARTIFACT,
)
from bioml_data.datasets.tms_aorta._metadata_expectations import (
    TMS_AORTA_ARTIFACT_AUDIT_EXPECTATIONS,
)

from ._single_cell_fixtures import make_dataset, make_split


def _scope() -> bio.MetadataExpectationScope:
    """Return the exact fixture protocol scope with a stable evidence citation."""
    return bio.MetadataExpectationScope(
        dataset=make_dataset().snapshot,
        artifact=TMS_AORTA_ARTIFACT_SCOPE,
        task=make_split(make_dataset()).task,
        protocol=make_split(make_dataset()).protocol,
        citation=bio.MetadataCitation(
            title="Tabula Muris Senis data objects",
            uri="https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728",
        ),
    )


def _dataset() -> bio.CanonicalSingleCellDataset:
    """Return the fixture with the exact raw-parent and transform scope attached."""
    dataset = make_dataset()
    return replace(
        dataset,
        artifact=dataset.artifact.model_copy(
            update={
                "derivation": ArtifactDerivation(
                    parent_artifacts=(TMS_AORTA_SOURCE_ARTIFACT,),
                    transform_protocol=TransformProtocolId("tms-aorta-csr-v1"),
                )
            }
        ),
    )


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


def test_compare_reports_whole_dataset_and_each_realized_partition() -> None:
    # Given: exact-scope expectations for the complete artifact and held-out test set.
    dataset = _dataset()
    assignment = make_split(dataset)
    scope = _scope()
    expectations = (
        bio.PublicationMetadataExpectation.count(
            scope=scope,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            expected=6,
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

    # When: the prepared data and the realized split are compared with the evidence.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=expectations,
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


def test_compare_rejects_publication_expectation_from_global_dataset_scope() -> None:
    # Given: a whole-atlas expectation that names a different snapshot identity.
    dataset = _dataset()
    assignment = make_split(dataset)
    global_scope = replace(
        _scope(),
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
            dataset,
            assignment,
            expectations=(expectation,),
        )

    # Then: the specific snapshot mismatch is visible instead of becoming a false fail.
    assert captured.value.field == "dataset"


def test_compare_marks_not_reported_metadata_as_unknown_not_a_match() -> None:
    # Given: evidence that does not report a partition's assay metadata.
    dataset = _dataset()
    assignment = make_split(dataset)
    expectation = bio.PublicationMetadataExpectation.not_reported(
        scope=_scope(),
        partition=SplitPartition.TEST,
        metric=bio.MetadataMetric.ASSAY_VALUES,
    )

    # When: the unknown evidence is rendered in a concordance report.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=(expectation,),
    )

    # Then: it remains explicit unknown evidence and never counts as a pass.
    comparison = report.partition_reports[-1].comparisons[0]
    assert comparison.status is bio.MetadataConcordance.NOT_REPORTED
    assert comparison.observed.values == ("FACS",)


def test_compare_supports_range_and_approximate_count_evidence() -> None:
    # Given: two count claims reported with bounded rather than exact precision.
    dataset = _dataset()
    assignment = make_split(dataset)
    expectations = (
        bio.PublicationMetadataExpectation.within_range(
            scope=_scope(),
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            lower_bound=5,
            upper_bound=7,
        ),
        bio.PublicationMetadataExpectation.approximate(
            scope=_scope(),
            metric=bio.MetadataMetric.FEATURE_COUNT,
            expected=4,
            tolerance=1,
        ),
    )

    # When: the complete prepared data are compared against both precision types.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=expectations,
    )

    # Then: each precision type preserves its reported tolerance rather than guessing.
    assert tuple(item.status for item in report.dataset_comparisons) == (
        bio.MetadataConcordance.MATCH,
        bio.MetadataConcordance.MATCH,
    )


def test_compare_enforces_partition_coverage_and_reports_group_overlap() -> None:
    # Given: an assignment that covers every cell but splits one mouse.
    dataset = _dataset()
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
    split_groups = replace(original, assignments=assignments)
    expectation = bio.PublicationMetadataExpectation.count(
        scope=_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: the independent metadata check receives the split receipt.
    report = bio.compare_metadata_concordance(
        dataset,
        split_groups,
        expectations=(expectation,),
    )

    # Then: coverage holds, while group overlap stays visible for the leakage audit.
    assert report.covered_observation_count == 6
    assert report.cross_partition_groups == ("mouse-a",)


def test_compare_rejects_assignment_that_does_not_cover_prepared_rows() -> None:
    # Given: a receipt with one prepared cell removed from the partition assignment.
    dataset = _dataset()
    original = make_split(dataset)
    incomplete = replace(original, assignments=original.assignments[:-1])
    expectation = bio.PublicationMetadataExpectation.count(
        scope=_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: concordance is requested against an incomplete partition receipt.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset,
            incomplete,
            expectations=(expectation,),
        )

    # Then: no partial train/test comparison is emitted.
    assert captured.value.violation is bio.MetadataPartitionViolation.COVERAGE
