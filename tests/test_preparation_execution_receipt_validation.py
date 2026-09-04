"""Adversarial validation scenarios for preparation-execution receipts."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data as bio
import bioml_data.preparation_execution as execution
from bioml_data._preparation_execution_models import MAX_ALIGNMENT_FEATURE_IDS
from bioml_data._preparation_models import FittedProtocolSemanticMismatchError
from bioml_data._split import (
    PartitionGroupCounts,
    SplitPartition,
    assignment_receipt_identity,
)

from ._execution_receipt_fixtures import execution_context, record


def _rehashed(
    receipt: execution.PreparationExecutionReceipt,
) -> execution.PreparationExecutionReceipt:
    """Emulate an attacker who knows the public receipt hash construction."""
    payload = asdict(receipt)
    del payload["receipt_identity"]
    identity = sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    return replace(
        receipt,
        receipt_identity=execution.PreparationExecutionReceiptIdentity(identity),
    )


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
    with pytest.raises(
        execution.PreparationExecutionReceiptMismatchError
    ) as identity_error:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(
        execution.PreparationExecutionReceiptMismatchError
    ) as json_error:
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
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        execution.validate_preparation_execution_receipt(forged)

    # Then: bounded semantics fail before identity or output serialization.
    assert captured.value.field == "alignment_feature_ids"


def test_public_boundaries_reject_rehashed_unsafe_runtime_metadata(
    tmp_path: Path,
) -> None:
    """A recomputed receipt hash cannot legitimize host-local runtime data."""
    # Given: frozen nested runtime metadata is bypassed and the outer hash rebuilt.
    receipt = record(execution_context(tmp_path))
    dependency = receipt.runtime.dependencies[0]
    object.__setattr__(receipt.runtime, "toolkit_version", "/Users/alice/secret")
    object.__setattr__(dependency, "component", "DATABASE_URL")
    object.__setattr__(dependency, "version", "postgres://alice:secret@host/db")
    forged = _rehashed(receipt)

    # When: either public consuming boundary receives the forged receipt.
    with pytest.raises(
        execution.PreparationExecutionReceiptMismatchError
    ) as validation_error:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(
        execution.PreparationExecutionReceiptMismatchError
    ) as json_error:
        _ = forged.to_json()

    # Then: both replay nested runtime parsing before using the outer hash.
    assert validation_error.value.field == "toolkit_version"
    assert json_error.value.field == "toolkit_version"


def test_record_rejects_protocol_semantics_not_bound_to_prepared_output(
    tmp_path: Path,
) -> None:
    """Protocol name/version cannot substitute for its actual preprocessing values."""
    # Given: a valid prepared output and another protocol with the same name/version.
    context = execution_context(tmp_path)
    changed_protocol = replace(
        context.protocol,
        normalization=replace(context.protocol.normalization, target_sum=999.0),
    )

    # When: execution recording tries to bind the changed protocol to old output.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, protocol=changed_protocol))

    # Then: the semantic protocol identity, not just its text label, must match.
    assert captured.value.field == "prepared_protocol_semantic_identity"


def test_record_rejects_each_changed_protocol_semantic_with_stale_output(
    tmp_path: Path,
) -> None:
    """Every fixed and train-fitted protocol input is bound to prepared output."""
    # Given: valid output and variants that retain only the protocol text label.
    context = execution_context(tmp_path)
    selection = context.protocol.feature_selection
    assert selection is not None
    variants = (
        replace(
            context.protocol,
            qc=replace(context.protocol.qc, minimum_cell_count=2),
        ),
        replace(
            context.protocol,
            qc=replace(context.protocol.qc, minimum_feature_cells=2),
        ),
        replace(
            context.protocol,
            alignment=replace(
                context.protocol.alignment,
                feature_ids=tuple(reversed(context.protocol.alignment.feature_ids)),
            ),
        ),
        replace(context.protocol, feature_selection=None),
        replace(
            context.protocol,
            feature_selection=replace(selection, max_features=2),
        ),
    )

    # When: each changed protocol is paired with the original prepared receipt.
    for variant in variants:
        with pytest.raises(
            execution.PreparationExecutionReceiptMismatchError
        ) as captured:
            _ = record(replace(context, protocol=variant))

        # Then: every variant fails at semantic lineage, not just name/version text.
        assert captured.value.field == "prepared_protocol_semantic_identity"


def test_record_rejects_stale_prepared_protocol_semantic_identity(
    tmp_path: Path,
) -> None:
    """Prepared-output lineage rejects a tampered semantic fingerprint."""
    # Given: one otherwise valid prepared receipt with a stale 64-hex fingerprint.
    context = execution_context(tmp_path)
    forged = replace(context.prepared, protocol_semantic_identity="0" * 64)

    # When: execution tries to bind that prepared output.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = record(replace(context, prepared=forged))

    # Then: the exact current protocol fingerprint is required.
    assert captured.value.field == "prepared_protocol_semantic_identity"


def test_apply_rejects_fitted_state_from_another_protocol_semantics(
    tmp_path: Path,
) -> None:
    """Fitted state cannot be applied after a current protocol semantic change."""
    # Given: fit state made from the fixture protocol and a changed normalization.
    context = execution_context(tmp_path)
    independent = bio.prepare_train_independent(
        context.dataset,
        protocol=context.protocol,
        seed=context.assignment.seed,
    )
    fitted = bio.fit_train_preprocessing(independent, split=context.assignment)
    changed = replace(
        independent,
        protocol=replace(
            independent.protocol,
            normalization=replace(independent.protocol.normalization, target_sum=999.0),
        ),
    )

    # When: current preparation tries to reuse the old fitted state.
    with pytest.raises(FittedProtocolSemanticMismatchError) as captured:
        _ = bio.apply_fitted_preprocessing(
            changed,
            fitted=fitted,
            split=context.assignment,
        )

    assert captured.value.expected != captured.value.actual


def test_ordered_feature_alignment_changes_execution_semantics(tmp_path: Path) -> None:
    """Operational feature order is retained rather than normalized as a set."""
    # Given: two protocols that differ only by their ordered alignment sequence.
    context = execution_context(tmp_path)
    reverse_protocol = replace(
        context.protocol,
        alignment=replace(
            context.protocol.alignment,
            feature_ids=tuple(reversed(context.protocol.alignment.feature_ids)),
        ),
    )
    reverse_prepared = bio.prepare_benchmark(
        bio.PreparationRequest(
            dataset=context.dataset,
            protocol=reverse_protocol,
            split=context.assignment,
            seed=context.assignment.seed,
        )
    )

    # When: the two executions are recorded from their corresponding outputs.
    forward = record(context)
    reverse = record(
        replace(context, protocol=reverse_protocol, prepared=reverse_prepared)
    )

    # Then: ordered feature semantics and their execution identities stay distinct.
    assert reverse.semantic_parameters.alignment_feature_ids == (
        "gene-3",
        "gene-2",
        "gene-1",
    )
    assert forward.semantic_parameters.alignment_feature_identity != (
        reverse.semantic_parameters.alignment_feature_identity
    )
    assert forward.receipt_identity != reverse.receipt_identity
