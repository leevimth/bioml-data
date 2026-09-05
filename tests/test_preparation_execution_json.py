"""Serialized preparation-execution receipt boundary scenarios."""

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter

import bioml_data.preparation_execution as execution
from bioml_data._preparation_execution_json import (
    MAX_RECEIPT_JSON_BYTES,
    MAX_RECEIPT_JSON_NESTING,
)

from ._execution_receipt_fixtures import execution_context, record

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
type Mutation = Callable[[dict[str, JsonValue]], JsonValue | None]


def _payload(receipt: execution.PreparationExecutionReceipt) -> dict[str, JsonValue]:
    """Decode a canonical receipt only for localized adversarial mutations."""
    return _JSON_OBJECT.validate_json(receipt.to_json())


def _encoded(payload: dict[str, JsonValue]) -> str:
    """Render a mutated JSON fixture without depending on receipt internals."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _remove_runtime(payload: dict[str, JsonValue]) -> JsonValue:
    """Remove one required field from a valid receipt payload."""
    return payload.pop("runtime")


def _add_extra_field(payload: dict[str, JsonValue]) -> None:
    """Add one forbidden root field to a valid receipt payload."""
    payload["unexpected"] = "value"


def _replace_expression_input(payload: dict[str, JsonValue]) -> None:
    """Substitute an unsupported expression-input enum value."""
    payload["expression_input"] = "log1p"


def _replace_input_artifact_hash(payload: dict[str, JsonValue]) -> None:
    """Substitute an invalid artifact identifier."""
    payload["input_artifact_identity"] = "bad"


def _replace_format_version(payload: dict[str, JsonValue]) -> None:
    """Substitute an unsupported serialized receipt version."""
    payload["receipt_format_version"] = "v2"


def _replace_receipt_identity(payload: dict[str, JsonValue]) -> None:
    """Substitute a syntactically valid but stale outer identity."""
    payload["receipt_identity"] = "0" * 64


_INVALID_PAYLOAD_MUTATIONS: tuple[tuple[str, Mutation], ...] = (
    ("receipt_json", _remove_runtime),
    ("receipt_json", _add_extra_field),
    ("receipt_json", _replace_expression_input),
    ("input_artifact_identity", _replace_input_artifact_hash),
    ("receipt_json", _replace_format_version),
    ("receipt_identity", _replace_receipt_identity),
)


def test_execution_receipt_from_json_round_trips_canonical_identity(
    tmp_path: Path,
) -> None:
    """A versioned receipt can be reopened without changing its identity."""
    # Given: one public receipt rendered as canonical versioned JSON.
    receipt = record(execution_context(tmp_path))

    # When: a consumer parses the JSON at the public boundary.
    restored = execution.PreparationExecutionReceipt.from_json(receipt.to_json())
    restored_by_function = execution.preparation_execution_receipt_from_json(
        receipt.to_json()
    )

    # Then: the exact scientific receipt and its identity are preserved.
    assert restored == receipt
    assert restored_by_function == receipt
    assert restored.receipt_identity == receipt.receipt_identity
    assert restored.to_json() == receipt.to_json()


def test_execution_receipt_from_json_rejects_malformed_payload() -> None:
    """Invalid JSON never reaches the typed receipt constructor."""
    # Given: a syntactically malformed serialized receipt.
    # When: a consumer attempts to deserialize it.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.PreparationExecutionReceipt.from_json("{")

    # Then: the boundary returns the typed redacted error.
    assert captured.value.field == "receipt_json"


@pytest.mark.parametrize(
    ("field", "mutation"),
    _INVALID_PAYLOAD_MUTATIONS,
)
def test_execution_receipt_from_json_rejects_invalid_serialized_fields(
    tmp_path: Path,
    field: str,
    mutation: Mutation,
) -> None:
    """Structural, semantic, version, and identity violations remain typed errors."""
    # Given: a valid canonical receipt with one serialized field mutated.
    receipt = record(execution_context(tmp_path))
    payload = _payload(receipt)
    _ = mutation(payload)

    # When: a consumer parses the altered payload.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.PreparationExecutionReceipt.from_json(_encoded(payload))

    # Then: the violation never returns a partial receipt.
    assert captured.value.field == field


def test_execution_receipt_from_json_redacts_hostile_payload_text() -> None:
    """Invalid serialized input cannot echo a supplied secret in the typed error."""
    # Given: a malformed JSON field name containing a credential-like token.
    marker = "opaque-input-marker"

    # When: the parser rejects the hostile JSON payload.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.PreparationExecutionReceipt.from_json(
            f'{{"receipt_format_version":"v1","{marker}":"value"}}'
        )

    # Then: the public error omits that untrusted value.
    assert marker not in str(captured.value)
    assert marker not in repr(captured.value)


@pytest.mark.parametrize(
    "payload",
    [
        " " * (MAX_RECEIPT_JSON_BYTES + 1),
        "[" * (MAX_RECEIPT_JSON_NESTING + 1),
    ],
)
def test_execution_receipt_from_json_rejects_resource_exhaustion_payloads(
    payload: str,
) -> None:
    """The public parser rejects unreasonable size and nesting before decoding."""
    # Given: serialized input that exceeds one documented parser resource bound.

    # When: a consumer attempts to deserialize the payload.
    with pytest.raises(execution.PreparationExecutionReceiptMismatchError) as captured:
        _ = execution.PreparationExecutionReceipt.from_json(payload)

    # Then: no model is returned and the error stays at the JSON boundary.
    assert captured.value.field == "receipt_json"
