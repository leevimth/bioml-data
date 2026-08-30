"""Post-split leakage evidence report tests."""

from __future__ import annotations

from dataclasses import replace

from bioml_data import _leakage_audit as audit
from bioml_data import _leakage_audit_models as audit_models
from bioml_data._domain import DatasetName, DatasetVersion, ProtocolId
from bioml_data._split import (
    AssignmentIdentity,
    MetadataColumn,
    SplitPartition,
)
from tests._single_cell_fixtures import make_dataset, make_split


def _check(report: audit.LeakageAuditReport, axis: str) -> audit.OverlapCheck:
    return next(check for check in report.checks if check.axis == axis)


def test_leakage_facade_preserves_consumed_model_bindings() -> None:
    # Given: model contracts consumed through the leakage-audit facade.

    # When: the consumed bindings are resolved from both module surfaces.

    # Then: the facade preserves the exact model objects.
    assert audit.LeakageAuditReport is audit_models.LeakageAuditReport
    assert audit.OverlapCheck is audit_models.OverlapCheck
    assert audit.LeakageAuditRequest is audit_models.LeakageAuditRequest
    assert audit.AuditStatus is audit_models.AuditStatus
    assert audit.AuditSupport is audit_models.AuditSupport


def test_tms_canary_reports_group_overlap_and_metadata_coverage() -> None:
    # Given: canonical TMS-like rows assigned by whole animal.
    dataset = make_dataset()
    request = audit.LeakageAuditRequest.from_dataset(dataset, make_split(dataset))

    # When: the post-split audit evaluates declared and informative axes.
    report = audit.audit_split(request)

    # Then: animal isolation passes while other evidence remains visible.
    donor = _check(report, "donor_animal")
    study = _check(report, "study")
    library_batch = _check(report, "library_batch")
    assert donor.status is audit.AuditStatus.PASS
    assert donor.coverage.present == donor.coverage.total == 6
    assert donor.overlapping_values == ()
    assert study.status is audit.AuditStatus.WARN
    assert study.overlapping_values == ("GSE149590",)
    assert library_batch.status is audit.AuditStatus.UNKNOWN
    assert library_batch.coverage.present == 0


def test_missing_leakage_metadata_is_not_treated_as_safe() -> None:
    # Given: a supported receipt but donor metadata is absent from one row.
    dataset = make_dataset()
    request = audit.LeakageAuditRequest.from_dataset(dataset, make_split(dataset))
    first = request.observations[0]
    incomplete = replace(
        first,
        metadata=tuple(
            item for item in first.metadata if item.column != MetadataColumn("donor_id")
        ),
    )

    # When: the audit sees incomplete coverage of the declared leakage unit.
    report = audit.audit_split(
        replace(request, observations=(incomplete, *request.observations[1:])),
    )

    # Then: the donor check is unknown rather than passing by absence.
    donor = _check(report, "donor_animal")
    assert donor.status is audit.AuditStatus.UNKNOWN
    assert donor.coverage.present == 5
    assert donor.coverage.total == 6


def test_exact_duplicates_and_cross_partition_rows_fail() -> None:
    # Given: one repeated canonical row and a second partition for its cell ID.
    dataset = make_dataset()
    split = make_split(dataset)
    original = split.assignments[0]
    other_partition = next(
        partition for partition in SplitPartition if partition is not original.partition
    )
    request = audit.LeakageAuditRequest.from_dataset(dataset, split)
    duplicated = replace(
        request,
        observations=(request.observations[0], *request.observations),
        assignment=replace(
            split,
            assignments=(
                *split.assignments,
                replace(original, partition=other_partition),
            ),
            assignment_identity=AssignmentIdentity("forged-duplicate"),
        ),
    )

    # When: exact-identity evidence is audited.
    report = audit.audit_split(duplicated)

    # Then: both duplicate modes are explicit and fail the required check.
    assert report.status is audit.AuditStatus.FAIL
    assert report.duplicates.repeated_observation_ids == (original.observation_id,)
    assert report.duplicates.cross_partition_observation_ids == (
        original.observation_id,
    )
    assert _check(report, "observation_id").status is audit.AuditStatus.FAIL


def test_unsupported_unknown_and_actual_overlap_are_distinct() -> None:
    # Given: an unsupported protocol, an unassessed dataset, and forged donor leakage.
    dataset = make_dataset()
    split = make_split(dataset)
    request = audit.LeakageAuditRequest.from_dataset(dataset, split)
    unsupported = replace(
        request,
        assignment=replace(split, protocol=ProtocolId("random-cell-v1")),
    )
    unknown = replace(
        request,
        dataset=replace(
            request.dataset,
            name=DatasetName("future-dataset"),
            version=DatasetVersion("v1"),
        ),
        assignment=replace(
            split,
            dataset=replace(
                split.dataset,
                name=DatasetName("future-dataset"),
                version=DatasetVersion("v1"),
            ),
        ),
    )
    leaked_assignments = tuple(
        replace(
            assignment,
            partition=SplitPartition.TEST,
        )
        if assignment.observation_id == "cell-2"
        else assignment
        for assignment in split.assignments
    )
    leaked = replace(
        request,
        assignment=replace(
            split,
            assignments=leaked_assignments,
            assignment_identity=AssignmentIdentity("forged-overlap"),
        ),
    )

    # When: each distinct state is audited.
    unsupported_report = audit.audit_split(unsupported)
    unknown_report = audit.audit_split(unknown)
    leaked_report = audit.audit_split(leaked)

    # Then: support state and evidence status do not collapse together.
    assert unsupported_report.support is audit.AuditSupport.UNSUPPORTED
    assert unsupported_report.status is audit.AuditStatus.UNKNOWN
    assert unknown_report.support is audit.AuditSupport.UNKNOWN
    assert unknown_report.status is audit.AuditStatus.UNKNOWN
    assert leaked_report.support is audit.AuditSupport.SUPPORTED
    assert leaked_report.status is audit.AuditStatus.FAIL
    assert _check(leaked_report, "donor_animal").status is audit.AuditStatus.FAIL


def test_audit_report_has_deterministic_json_and_human_surfaces() -> None:
    # Given: one supported TMS canary audit request.
    dataset = make_dataset()
    request = audit.LeakageAuditRequest.from_dataset(dataset, make_split(dataset))

    # When: the report is rendered twice through both surfaces.
    report = audit.audit_split(request)
    json_first = report.to_json()
    json_second = audit.audit_split(request).to_json()
    text_first = report.to_text()
    text_second = audit.audit_split(request).to_text()

    # Then: identities and serialized evidence are deterministic and self-identifying.
    restored = audit.LeakageAuditReport.model_validate_json(json_first)
    assert json_first == json_second
    assert text_first == text_second
    assert restored.report_identity == report.report_identity
    assert restored.dataset == dataset.snapshot
    assert restored.artifact_identity == dataset.artifact.artifact_id
    assert restored.protocol == "animal-held-out-v1"
