"""Adversarial validation scenarios for preparation-execution receipts."""

from dataclasses import replace
from pathlib import Path

import pytest

import bioml_data as bio
from bioml_data._preparation_execution_models import MAX_ALIGNMENT_FEATURE_IDS
from bioml_data._split import (
    PartitionGroupCounts,
    SplitPartition,
    assignment_receipt_identity,
)

from ._execution_receipt_fixtures import execution_context, record


def test_record_rejects_stale_assignment_identity_before_consuming_it(
    tmp_path: Path,
) -> None:
    """An altered assignment body cannot retain its prior identity."""
    # Given: a valid deterministic split receipt with a modified assignment body.
    context = execution_context(tmp_path)
    changed = replace(
        context.assignment.assignments[0],
        partition=SplitPartition.TEST,
    )
    forged_assignment = replace(
        context.assignment,
        assignments=(changed, *context.assignment.assignments[1:]),
    )

    # When: execution recording is asked to consume the stale identity.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = record(replace(context, assignment=forged_assignment))

    # Then: split receipt integrity is checked before receipt construction.
    assert captured.value.violation is bio.MetadataPartitionViolation.IDENTITY


def test_record_rejects_rehashed_assignment_with_invalid_allocation(
    tmp_path: Path,
) -> None:
    """Rehashing a structurally coherent but invented split cannot bypass replay."""
    # Given: an attacker recomputes identity and counts after assigning all rows test.
    context = execution_context(tmp_path)
    all_test = tuple(
        replace(item, partition=SplitPartition.TEST)
        for item in context.assignment.assignments
    )
    altered = replace(
        context.assignment,
        assignments=all_test,
        realized_group_counts=PartitionGroupCounts(
            train=0,
            validation=0,
            test=context.assignment.group_count,
        ),
    )
    forged_assignment = replace(
        altered,
        assignment_identity=assignment_receipt_identity(altered),
    )

    # When: execution recording consumes the self-consistent forged receipt.
    with pytest.raises(bio.InvalidMetadataPartitionError) as captured:
        _ = record(replace(context, assignment=forged_assignment))

    # Then: the named allocation is replayed against canonical observations.
    assert captured.value.violation is bio.MetadataPartitionViolation.ALLOCATION


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_receipt_rejects_nonfinite_nested_semantic_parameter(
    tmp_path: Path,
    invalid: float,
) -> None:
    """No nested non-finite parameter can enter identity or canonical JSON."""
    # Given: a frozen receipt bypassed only to emulate hostile decoded input.
    receipt = record(execution_context(tmp_path))
    parameters = receipt.semantic_parameters
    object.__setattr__(parameters, "normalization_target_sum", invalid)
    forged = replace(receipt, semantic_parameters=parameters)

    # When: either identity validation or canonical JSON rendering is requested.
    with pytest.raises(bio.PreparationExecutionReceiptMismatchError) as identity_error:
        bio.validate_preparation_execution_receipt(forged)
    with pytest.raises(bio.PreparationExecutionReceiptMismatchError) as json_error:
        _ = forged.to_json()

    # Then: both public consumer boundaries reject the nested value.
    assert identity_error.value.field == "normalization_target_sum"
    assert json_error.value.field == "normalization_target_sum"


def test_receipt_records_explicit_canonical_alignment_feature_ids(
    tmp_path: Path,
) -> None:
    """Alignment is inspectable as a bounded sorted feature identifier list."""
    # Given: a completed fixture-scale preparation execution.
    receipt = record(execution_context(tmp_path))

    # Then: consumers can inspect exact canonical feature semantics, not just a hash.
    parameters = receipt.semantic_parameters
    assert parameters.alignment_feature_ids == ("gene-1", "gene-2", "gene-3")
    assert parameters.alignment_feature_count == len(parameters.alignment_feature_ids)
    assert (
        tuple(sorted(parameters.alignment_feature_ids))
        == parameters.alignment_feature_ids
    )


def test_receipt_rejects_excessive_alignment_feature_list(tmp_path: Path) -> None:
    """Feature identifiers remain bounded rather than becoming a raw data dump."""
    # Given: hostile decoded content that exceeds the receipt's documented bound.
    receipt = record(execution_context(tmp_path))
    parameters = receipt.semantic_parameters
    object.__setattr__(
        parameters,
        "alignment_feature_ids",
        tuple(f"gene-{index}" for index in range(MAX_ALIGNMENT_FEATURE_IDS + 1)),
    )
    object.__setattr__(
        parameters,
        "alignment_feature_count",
        MAX_ALIGNMENT_FEATURE_IDS + 1,
    )
    forged = replace(receipt, semantic_parameters=parameters)

    # When: a consumer validates the forged receipt.
    with pytest.raises(bio.PreparationExecutionReceiptMismatchError) as captured:
        bio.validate_preparation_execution_receipt(forged)

    # Then: bounded semantics fail before identity or output serialization.
    assert captured.value.field == "alignment_feature_ids"
