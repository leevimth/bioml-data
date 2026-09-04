"""Exact-enum public receipt boundary scenarios."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data.preparation_execution as execution

from ._execution_receipt_fixtures import execution_context, record


class _ReceiptSubclass(execution.PreparationExecutionReceipt):
    """Hostile subclass used to prove the exact public receipt root boundary."""


class _DecodedObject(dict[str, str]):
    """Untyped decoded root that deliberately is not an execution receipt."""


def _rehashed(
    receipt: execution.PreparationExecutionReceipt,
) -> execution.PreparationExecutionReceipt:
    """Rebuild the public identity after a hostile in-memory mutation."""
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


def _subclassed(
    receipt: execution.PreparationExecutionReceipt,
) -> execution.PreparationExecutionReceipt:
    """Return a structurally complete receipt with a hostile runtime subclass."""
    return _ReceiptSubclass(
        receipt_identity=receipt.receipt_identity,
        dataset=receipt.dataset,
        task=receipt.task,
        input_artifact_identity=receipt.input_artifact_identity,
        canonical_artifact_identity=receipt.canonical_artifact_identity,
        materialization_parent_artifact_identities=(
            receipt.materialization_parent_artifact_identities
        ),
        materialization_outcome=receipt.materialization_outcome,
        preparation_protocol_id=receipt.preparation_protocol_id,
        preparation_protocol_version=receipt.preparation_protocol_version,
        preparation_protocol_semantic_identity=(
            receipt.preparation_protocol_semantic_identity
        ),
        semantic_parameters=receipt.semantic_parameters,
        expression_input=receipt.expression_input,
        canonical_materialization_fit_scope=(
            receipt.canonical_materialization_fit_scope
        ),
        prepared_fit_scope=receipt.prepared_fit_scope,
        split_protocol=receipt.split_protocol,
        split_assignment_identity=receipt.split_assignment_identity,
        seed=receipt.seed,
        prepared_benchmark_receipt_identity=(
            receipt.prepared_benchmark_receipt_identity
        ),
        prepared_output_artifact_identity=receipt.prepared_output_artifact_identity,
        fitted_state_identity=receipt.fitted_state_identity,
        runtime=receipt.runtime,
        metadata_concordance=receipt.metadata_concordance,
    )


def test_public_receipt_boundaries_reject_subclassed_receipt_root(
    tmp_path: Path,
) -> None:
    """Public validation, identity, and rendering require the exact receipt type."""
    # Given: a structurally complete execution receipt represented by a subclass.
    forged = _subclassed(record(execution_context(tmp_path)))

    # When: each public receipt boundary receives the subclass.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as checked:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(
        execution.PreparationExecutionReceiptMismatchError
    ) as identified:
        _ = execution.preparation_execution_receipt_identity(forged)
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as rendered:
        _ = forged.to_json()

    # Then: all stop at the root before nested traversal or canonical rendering.
    assert checked.value.field == "preparation_execution_receipt"
    assert identified.value.field == "preparation_execution_receipt"
    assert rendered.value.field == "preparation_execution_receipt"


@pytest.mark.parametrize("hostile", ["hostile-receipt", None, _DecodedObject()])
def test_public_receipt_boundaries_reject_nonreceipt_roots(
    hostile: str | _DecodedObject | None,
) -> None:
    """Public receipt entry points reject scalar, none, and object roots first."""
    # Given: one dynamically decoded value that is not an execution receipt.
    # When: the identity or validation entry point receives the hostile root.
    with pytest.raises(
        execution.PreparationExecutionReceiptMismatchError
    ) as identified:
        _ = execution.preparation_execution_receipt_identity(hostile)
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as checked:
        _ = execution.validate_preparation_execution_receipt(hostile)

    # Then: both reject the root without attempting to read receipt fields.
    assert identified.value.field == "preparation_execution_receipt"
    assert checked.value.field == "preparation_execution_receipt"


def test_public_receipt_rejects_rehashed_plain_string_expression_input(
    tmp_path: Path,
) -> None:
    """In-memory validation requires enum instances, not enum-coercible strings."""
    # Given: a receipt rehashed after expression input is bypass-mutated to text.
    receipt = record(execution_context(tmp_path))
    object.__setattr__(receipt, "expression_input", "raw.X")
    forged = _rehashed(receipt)

    # When: either public receipt consumer receives the forged object.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as checked:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as rendered:
        _ = forged.to_json()

    # Then: both require the exact closed enum at the in-memory boundary.
    assert checked.value.field == "expression_input"
    assert rendered.value.field == "expression_input"


@pytest.mark.parametrize(
    ("field", "value", "error_field"),
    [
        ("materialization_outcome", "transformed", "materialization_outcome"),
        (
            "canonical_materialization_fit_scope",
            "none",
            "canonical_materialization_fit_scope",
        ),
        ("prepared_fit_scope", "train_only", "prepared_fit_scope"),
    ],
)
def test_public_receipt_rejects_rehashed_plain_string_enum_fields(
    tmp_path: Path,
    field: str,
    value: str,
    error_field: str,
) -> None:
    """Every public enum field rejects a string that merely has the right value."""
    # Given: a receipt rehashed after one enum field is bypass-mutated to text.
    receipt = record(execution_context(tmp_path))
    object.__setattr__(receipt, field, value)
    forged = _rehashed(receipt)

    # When: either public receipt consumer receives the forged object.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as checked:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as rendered:
        _ = forged.to_json()

    # Then: both require the exact enum instance.
    assert checked.value.field == error_field
    assert rendered.value.field == error_field


def test_public_receipt_rejects_rehashed_plain_string_attachment_status(
    tmp_path: Path,
) -> None:
    """Optional concordance attachments use the same exact-enum boundary."""
    # Given: a receipt whose nested attachment status was bypass-mutated to text.
    receipt = record(execution_context(tmp_path))
    attachment = receipt.metadata_concordance
    assert attachment is not None
    object.__setattr__(attachment, "status", "not_reported")
    forged = _rehashed(receipt)

    # When: public receipt validation or rendering consumes the mutation.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as checked:
        execution.validate_preparation_execution_receipt(forged)
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as rendered:
        _ = forged.to_json()

    # Then: the nested enum is not coerced from its wire representation.
    assert checked.value.field == "metadata_concordance_status"
    assert rendered.value.field == "metadata_concordance_status"
