"""Versioned JSON boundary for preparation-execution receipts."""

from dataclasses import dataclass
from typing import ClassVar, Final, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
)

from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)

MAX_RECEIPT_JSON_BYTES: Final = 2 * 1024 * 1024
MAX_RECEIPT_JSON_NESTING: Final = 32
_QUOTE_BYTE: Final = ord('"')
_ESCAPE_BYTE: Final = ord("\\")
_OPEN_ARRAY_BYTE: Final = ord("[")
_OPEN_OBJECT_BYTE: Final = ord("{")
_CLOSE_ARRAY_BYTE: Final = ord("]")
_CLOSE_OBJECT_BYTE: Final = ord("}")


class _JsonModel(BaseModel):
    """Reject coercion and unknown fields at the serialized receipt boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class _DatasetPayload(_JsonModel):
    name: StrictStr
    version: StrictStr


class _SemanticParametersPayload(_JsonModel):
    minimum_cell_count: StrictInt
    minimum_feature_cells: StrictInt
    alignment_feature_ids: tuple[StrictStr, ...]
    alignment_feature_count: StrictInt
    alignment_feature_identity: StrictStr
    normalization_target_sum: StrictFloat | StrictInt
    max_features: StrictInt | None


class _RuntimeDependencyPayload(_JsonModel):
    component: Literal["anndata", "numpy", "scipy"]
    version: StrictStr


class _RuntimePayload(_JsonModel):
    toolkit_version: StrictStr
    dependencies: tuple[_RuntimeDependencyPayload, ...]


class _MetadataConcordancePayload(_JsonModel):
    report_identity: StrictStr
    status: Literal["match", "mismatch", "not_reported", "mixed"]


class PreparationExecutionReceiptJsonPayload(_JsonModel):
    receipt_format_version: Literal["v1"]
    receipt_identity: StrictStr
    dataset: _DatasetPayload
    task: StrictStr
    input_artifact_identity: StrictStr
    canonical_artifact_identity: StrictStr
    materialization_parent_artifact_identities: tuple[StrictStr, ...]
    materialization_outcome: Literal["cache_hit", "transformed"]
    preparation_protocol_id: StrictStr
    preparation_protocol_version: StrictStr
    preparation_protocol_semantic_identity: StrictStr
    semantic_parameters: _SemanticParametersPayload
    expression_input: Literal["raw.X"]
    canonical_materialization_fit_scope: Literal["none", "train_only"]
    prepared_fit_scope: Literal["none", "train_only"]
    split_protocol: StrictStr
    split_assignment_identity: StrictStr
    seed: StrictInt
    prepared_benchmark_receipt_identity: StrictStr
    prepared_output_artifact_identity: StrictStr
    fitted_state_identity: StrictStr
    runtime: _RuntimePayload
    metadata_concordance: _MetadataConcordancePayload | None


@dataclass(frozen=True, slots=True)
class _JsonNestingState:
    """Minimal lexical state used only to bound hostile JSON nesting."""

    depth: int
    in_string: bool
    escaped: bool


def parse_preparation_execution_receipt_payload(
    payload: str | bytes,
) -> PreparationExecutionReceiptJsonPayload:
    """Parse one supported, bounded v1 payload before domain construction."""
    _validate_payload_bounds(payload)
    try:
        decoded = PreparationExecutionReceiptJsonPayload.model_validate_json(payload)
    except ValidationError:
        raise PreparationExecutionReceiptMismatchError(
            field="receipt_json",
            expected="valid preparation-execution receipt JSON v1",
            actual="invalid",
        ) from None
    return decoded


def _validate_payload_bounds(payload: str | bytes) -> None:
    """Reject oversized or deeply nested JSON before a parser allocates models."""
    match payload:
        case str():
            _validate_text_payload(payload)
        case bytes():
            _validate_bytes_payload(payload)


def _validate_text_payload(payload: str) -> None:
    """Apply a conservative character and nesting bound to text JSON."""
    if len(payload) > MAX_RECEIPT_JSON_BYTES:
        _raise_payload_size()
    _validate_nesting(_text_nesting_state(payload))


def _validate_bytes_payload(payload: bytes) -> None:
    """Apply the same bounded nesting check without decoding untrusted bytes."""
    if len(payload) > MAX_RECEIPT_JSON_BYTES:
        _raise_payload_size()
    _validate_nesting(_bytes_nesting_state(payload))


def _text_nesting_state(payload: str) -> _JsonNestingState:
    """Scan JSON punctuation outside quoted text without interpreting values."""
    state = _JsonNestingState(depth=0, in_string=False, escaped=False)
    for character in payload:
        state = _next_text_state(state, character)
        _validate_nesting(state)
    return state


def _bytes_nesting_state(payload: bytes) -> _JsonNestingState:
    """Scan JSON punctuation outside quoted bytes without decoding them."""
    state = _JsonNestingState(depth=0, in_string=False, escaped=False)
    for character in payload:
        state = _next_byte_state(state, character)
        _validate_nesting(state)
    return state


def _next_text_state(state: _JsonNestingState, character: str) -> _JsonNestingState:
    """Advance lexical nesting state for one text character."""
    return _next_nesting_state(
        state,
        is_quote=character == '"',
        is_escape=character == "\\",
        is_open=character in "{[",
        is_close=character in "}]",
    )


def _next_byte_state(state: _JsonNestingState, character: int) -> _JsonNestingState:
    """Advance lexical nesting state for one byte character."""
    return _next_nesting_state(
        state,
        is_quote=character == _QUOTE_BYTE,
        is_escape=character == _ESCAPE_BYTE,
        is_open=character in (_OPEN_ARRAY_BYTE, _OPEN_OBJECT_BYTE),
        is_close=character in (_CLOSE_ARRAY_BYTE, _CLOSE_OBJECT_BYTE),
    )


def _next_nesting_state(
    state: _JsonNestingState,
    *,
    is_quote: bool,
    is_escape: bool,
    is_open: bool,
    is_close: bool,
) -> _JsonNestingState:
    """Advance a state machine that deliberately leaves JSON syntax to Pydantic."""
    next_state = state
    if state.in_string:
        if state.escaped:
            next_state = _JsonNestingState(
                depth=state.depth, in_string=True, escaped=False
            )
        elif is_escape:
            next_state = _JsonNestingState(
                depth=state.depth, in_string=True, escaped=True
            )
        elif is_quote:
            next_state = _JsonNestingState(
                depth=state.depth, in_string=False, escaped=False
            )
    elif is_quote:
        next_state = _JsonNestingState(depth=state.depth, in_string=True, escaped=False)
    elif is_open:
        next_state = _JsonNestingState(
            depth=state.depth + 1, in_string=False, escaped=False
        )
    elif is_close:
        next_state = _JsonNestingState(
            depth=state.depth - 1, in_string=False, escaped=False
        )
    return next_state


def _validate_nesting(state: _JsonNestingState) -> None:
    """Reject nesting beyond the bounded parser contract."""
    if state.depth > MAX_RECEIPT_JSON_NESTING:
        raise PreparationExecutionReceiptMismatchError(
            field="receipt_json",
            expected="JSON nesting at most 32 levels",
            actual="too_deep",
        )


def _raise_payload_size() -> None:
    raise PreparationExecutionReceiptMismatchError(
        field="receipt_json",
        expected="JSON payload up to 2 MiB",
        actual="oversized",
    )
