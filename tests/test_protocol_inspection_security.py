"""Adversarial trust-boundary scenarios for protocol inspection attachments."""

from dataclasses import replace

import pytest

import bioml_data as bio
from bioml_data._split import (
    PartitionGroupCounts,
    SplitAssignment,
    SplitPartition,
    assignment_receipt_identity,
)

from ._metadata_concordance_helpers import (
    explicit_partition_evidence,
    metadata_dataset,
    metadata_scope,
)
from ._single_cell_fixtures import make_split


def test_inspect_rejects_rehashed_all_test_receipt() -> None:
    """A self-consistent content identity cannot replace registered allocation."""
    # Given: a receipt whose every group was maliciously moved into test.
    original = make_split(metadata_dataset())
    forged = replace(
        original,
        assignments=tuple(
            SplitAssignment(item.observation_id, item.group, SplitPartition.TEST)
            for item in original.assignments
        ),
        realized_group_counts=PartitionGroupCounts(train=0, validation=0, test=5),
    )
    rehashed = replace(forged, assignment_identity=assignment_receipt_identity(forged))

    # When: inspection receives the rehashed adversarial receipt.
    with pytest.raises(bio.ProtocolInspectionReceiptMismatchError) as captured:
        _ = _inspect(assignment=rehashed)

    # Then: registered allocation replay rejects the forged group partitions.
    assert captured.value.field == "realized_group_counts"


def test_inspect_rejects_rehashed_invalid_fraction_and_count_receipts() -> None:
    """Rehashing cannot authorize protocol fractions or realized counts to drift."""
    # Given: one valid receipt with two independent protocol-field mutations.
    original = make_split(metadata_dataset())
    candidates = (
        replace(
            original,
            requested_group_fractions=replace(
                original.requested_group_fractions,
                train=0.7,
                validation=0.2,
            ),
        ),
        replace(
            original,
            realized_group_counts=PartitionGroupCounts(train=1, validation=1, test=3),
        ),
    )

    # When: each altered receipt is correctly rehashed by the caller.
    fields: list[str] = []
    for candidate in candidates:
        rehashed = replace(
            candidate,
            assignment_identity=assignment_receipt_identity(candidate),
        )
        with pytest.raises(bio.ProtocolInspectionReceiptMismatchError) as captured:
            _ = _inspect(assignment=rehashed)
        fields.append(captured.value.field)

    # Then: inspection checks registered semantics beyond a caller hash.
    assert fields == ["requested_group_fractions", "realized_group_counts"]


def test_inspect_labels_mutated_concordance_semantics_as_unverified() -> None:
    """Inspection must not represent attachment comparison statuses as verified."""
    # Given: a structurally valid report with a caller-mutated comparison status.
    assignment, concordance = _concordance()
    altered = replace(
        concordance,
        dataset_comparisons=(
            replace(
                concordance.dataset_comparisons[0],
                status=bio.MetadataConcordance.MATCH,
            ),
        ),
    )

    # When: the rehashed caller-supplied report is attached to matching receipt.
    report = _inspect(assignment=assignment, concordance=altered)

    # Then: structural joins hold, but outcome truth stays explicitly unverified.
    assert report.concordance is not None
    assert (
        report.concordance.verification
        is bio.ConcordanceVerification.CALLER_SUPPLIED_UNVERIFIED
    )
    assert report.concordance.caller_supplied
    assert report.concordance.validation_scope == (
        "structural-receipt-binding-only; outcomes-not-recomputed"
    )
    assert "caller-supplied-unverified" in report.to_text()
    assert "caller_supplied=true" in report.to_text()


def test_inspect_rejects_concordance_with_wrong_partition_coverage() -> None:
    """Concordance reports must structurally describe the bound assignment."""
    # Given: a valid report whose covered observation count is forged.
    assignment, concordance = _concordance()
    altered = replace(
        concordance,
        covered_observation_count=concordance.covered_observation_count + 1,
    )

    # When: the report is attached to its original split receipt.
    with pytest.raises(bio.ProtocolInspectionReceiptMismatchError) as captured:
        _ = _inspect(assignment=assignment, concordance=altered)

    # Then: inspection rejects the inconsistent partition metadata.
    assert captured.value.field == "concordance_covered_observation_count"


def _concordance() -> tuple[bio.SplitAssignmentReceipt, bio.MetadataConcordanceReport]:
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    concordance = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=(
            bio.PublicationMetadataExpectation.not_reported(
                scope=metadata_scope(),
                partition=None,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
            ),
            *explicit_partition_evidence(metadata_scope()),
        ),
    )
    return assignment, concordance


def _inspect(
    *,
    assignment: bio.SplitAssignmentReceipt | None = None,
    concordance: bio.MetadataConcordanceReport | None = None,
) -> bio.ProtocolInspection:
    return bio.inspect_protocol(
        "tms-aorta",
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
        request=bio.ProtocolInspectionRequest(
            assignment=assignment,
            concordance=concordance,
        ),
    )
