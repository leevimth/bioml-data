"""Exact-enum public receipt boundary scenarios."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data.preparation_execution as execution

from ._execution_receipt_fixtures import execution_context, record


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
