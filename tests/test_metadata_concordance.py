"""Publication-scoped metadata concordance scenarios."""

from dataclasses import replace

import pytest

import bioml_data as bio
from bioml_data._artifacts import ArtifactDerivation, TransformProtocolId
from bioml_data._domain import DatasetName, DatasetSnapshotIdentity, DatasetVersion
from bioml_data._split import (
    PartitionGroupCounts,
    SplitAssignment,
    SplitPartition,
    assignment_receipt_identity,
)
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


def test_tms_aorta_artifact_expectations_cover_each_realized_partition() -> None:
    # Given: the source-audit expectation tuple and a valid grouped split receipt.
    dataset = _dataset()
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


def test_compare_omits_empty_validation_partition_from_receipt_report() -> None:
    # Given: a valid five-train, one-test receipt with no validation observations.
    dataset = _dataset()
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
        receipt,
        assignment_identity=assignment_receipt_identity(receipt),
    )
    expectations = (
        bio.PublicationMetadataExpectation.not_reported(
            scope=_scope(),
            partition=SplitPartition.TRAIN,
            metric=bio.MetadataMetric.LABEL_COUNTS,
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=_scope(),
            partition=SplitPartition.VALIDATION,
            metric=bio.MetadataMetric.LABEL_COUNTS,
        ),
        bio.PublicationMetadataExpectation.not_reported(
            scope=_scope(),
            partition=SplitPartition.TEST,
            metric=bio.MetadataMetric.LABEL_COUNTS,
        ),
    )

    # When: concordance reports only partitions realized by the receipt.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=expectations,
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
    receipt = replace(
        original,
        assignments=assignments,
        realized_group_counts=PartitionGroupCounts(train=3, validation=1, test=2),
    )
    split_groups = replace(
        receipt,
        assignment_identity=assignment_receipt_identity(receipt),
    )
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


def test_compare_reports_each_group_once_when_multiple_cells_share_a_mouse() -> None:
    # Given: a train partition containing both cells from mouse-a.
    dataset = _dataset()
    assignment = make_split(dataset)
    expectation = bio.PublicationMetadataExpectation.not_reported(
        scope=_scope(),
        partition=SplitPartition.TRAIN,
        metric=bio.MetadataMetric.GROUP_IDS,
    )

    # When: a partition report is materialized from the grouped receipt.
    report = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=(expectation,),
    )

    # Then: held-out/group identifiers are distinct, sorted biological groups.
    train = next(
        item
        for item in report.partition_reports
        if item.partition is SplitPartition.TRAIN
    )
    assert train.group_ids == tuple(sorted(set(train.group_ids)))
    assert train.group_ids.count("mouse-a") == 1


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


@pytest.mark.parametrize(
    "uri",
    [
        "https://user:password@example.org/source",
        "https://example.org/source?token=secret",
        "https://example.org/source#section",
        "https://127.0.0.1/source",
        "https://localhost/source",
        "https://example.org/%zz",
    ],
)
def test_metadata_citation_rejects_non_public_or_credentialed_uri(uri: str) -> None:
    # Given: a metadata citation URI that cannot safely identify public evidence.

    # When: the citation is parsed at the metadata expectation boundary.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        _ = bio.MetadataCitation(title="Evidence", uri=uri)

    # Then: no unsafe endpoint becomes a publication-bound expectation.


def test_metadata_expectation_rejects_ignored_contradictory_fields() -> None:
    # Given: an exact count claim with an unrelated tolerance field.

    # When: the ambiguous expectation is constructed directly.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        _ = bio.PublicationMetadataExpectation(
            scope=_scope(),
            partition=None,
            fold=None,
            metric=bio.MetadataMetric.OBSERVATION_COUNT,
            kind=bio.MetadataExpectationKind.EXACT,
            expected_count=6,
            tolerance=1,
        )

    # Then: no field is silently discarded by a comparison kind.


def test_metadata_expectation_canonicalizes_unordered_values() -> None:
    # Given: semantically equivalent unordered categories with repeated input values.
    set_expectation = bio.PublicationMetadataExpectation(
        scope=_scope(),
        partition=None,
        fold=None,
        metric=bio.MetadataMetric.TISSUE_VALUES,
        kind=bio.MetadataExpectationKind.SET,
        values=("Aorta", "Aorta", "Heart"),
    )
    distribution_expectation = bio.PublicationMetadataExpectation(
        scope=_scope(),
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

    # When: the immutable expectation values are normalized at construction.

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

    # When: its construction validation is applied to the runtime value.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        expectation.__post_init__()

    # Then: booleans and floats cannot stand in for metadata integer fields.


@pytest.mark.parametrize("value", [True, 6.0])
def test_metadata_count_rejects_non_exact_runtime_integer(
    value: float | bool,
) -> None:
    # Given: a valid categorical count changed by an untyped runtime boundary.
    count = bio.MetadataCount(value="endothelial", count=1)
    object.__setattr__(count, "count", value)

    # When: count validation is reapplied.
    with pytest.raises(bio.InvalidMetadataExpectationError):
        count.__post_init__()

    # Then: a categorical count remains an exact non-negative integer.


def test_compare_rejects_expectations_for_a_different_fold() -> None:
    # Given: evidence scoped to a named fold and a different requested fold.
    dataset = _dataset()
    assignment = make_split(dataset)
    expectation = bio.PublicationMetadataExpectation(
        scope=_scope(),
        partition=None,
        fold=bio.MetadataFoldId("fold-1"),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        kind=bio.MetadataExpectationKind.EXACT,
        expected_count=6,
    )

    # When: concordance would otherwise filter the evidence to no comparisons.
    with pytest.raises(bio.MetadataExpectationScopeMismatchError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset,
            assignment,
            expectations=(expectation,),
            fold=bio.MetadataFoldId("fold-2"),
        )

    # Then: a fold mismatch is explicit instead of a silently empty report.
    assert captured.value.field == "fold"


def _expectation_for_numeric_field(
    field: str,
) -> bio.PublicationMetadataExpectation:
    match field:
        case "expected_count":
            return bio.PublicationMetadataExpectation.count(
                scope=_scope(),
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                expected=6,
            )
        case "tolerance":
            return bio.PublicationMetadataExpectation.approximate(
                scope=_scope(),
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                expected=6,
                tolerance=1,
            )
        case "lower_bound":
            return bio.PublicationMetadataExpectation.within_range(
                scope=_scope(),
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                lower_bound=5,
                upper_bound=7,
            )
        case "upper_bound":
            return bio.PublicationMetadataExpectation.within_range(
                scope=_scope(),
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
                lower_bound=5,
                upper_bound=7,
            )
        case _:  # pragma: no cover - parameter fixture is the closed boundary.
            pytest.fail("unsupported numeric field")


def test_compare_rejects_stale_assignment_identity() -> None:
    # Given: a receipt whose header seed changed after its identity was recorded.
    dataset = _dataset()
    stale = replace(make_split(dataset), seed=99)
    expectation = bio.PublicationMetadataExpectation.count(
        scope=_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: metadata concordance consumes the stale receipt.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset,
            stale,
            expectations=(expectation,),
        )

    # Then: snapshot/protocol/seed-bound receipt identity cannot be forged stale.
    assert captured.value.violation is bio.MetadataPartitionViolation.IDENTITY


def test_compare_rejects_assignment_group_not_in_canonical_grouping_column() -> None:
    # Given: a receipt with a recomputed identity but forged donor group membership.
    dataset = _dataset()
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
    forged = replace(
        receipt,
        assignment_identity=assignment_receipt_identity(receipt),
    )
    expectation = bio.PublicationMetadataExpectation.count(
        scope=_scope(),
        metric=bio.MetadataMetric.OBSERVATION_COUNT,
        expected=6,
    )

    # When: concordance validates the assignment against canonical split metadata.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = bio.compare_metadata_concordance(
            dataset,
            forged,
            expectations=(expectation,),
        )

    # Then: receipt rows cannot substitute arbitrary biological groups.
    assert captured.value.violation is bio.MetadataPartitionViolation.GROUPING
