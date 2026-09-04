"""Immutable, path-free scientific preparation-execution receipts."""

from dataclasses import dataclass
from enum import StrEnum, unique
from hashlib import sha256
from math import isfinite
from typing import Final, NewType

from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_tokens import (
    validate_safe_identifier,
    validate_sha256,
)

PreparationExecutionReceiptIdentity = NewType(
    "PreparationExecutionReceiptIdentity", str
)
MAX_ALIGNMENT_FEATURE_IDS: Final = 50_000


@unique
class ExpressionInput(StrEnum):
    """Matrix selected by the canonical dataset transform."""

    RAW_X = "raw.X"


@unique
class PreparationFitScope(StrEnum):
    """Scope from which a preparation stage may learn statistics."""

    NONE = "none"
    TRAIN_ONLY = "train_only"


@unique
class MetadataConcordanceAttachmentStatus(StrEnum):
    """Collapsed status of a full optional concordance report."""

    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_REPORTED = "not_reported"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class PreparationSemanticParameters:
    """Compact semantic parameters, excluding paths and host-local state."""

    minimum_cell_count: int
    minimum_feature_cells: int
    alignment_feature_ids: tuple[str, ...]
    alignment_feature_count: int
    alignment_feature_identity: str
    normalization_target_sum: float
    max_features: int | None

    def __post_init__(self) -> None:
        """Keep rendered preparation semantics finite, bounded, and canonical."""
        validate_semantic_parameters(self)


@dataclass(frozen=True, slots=True)
class MetadataConcordanceAttachment:
    """Identity and aggregate outcome for an attached concordance report."""

    report_identity: str
    status: MetadataConcordanceAttachmentStatus


def validate_semantic_parameters(parameters: PreparationSemanticParameters) -> None:
    """Reject values that cannot be safely and reproducibly rendered to JSON."""
    _require_positive_integer("minimum_cell_count", parameters.minimum_cell_count)
    _require_positive_integer("minimum_feature_cells", parameters.minimum_feature_cells)
    feature_ids = _feature_ids(parameters.alignment_feature_ids)
    _require_non_negative_integer(
        "alignment_feature_count", parameters.alignment_feature_count
    )
    if parameters.alignment_feature_count != len(feature_ids):
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_count",
            expected=str(len(feature_ids)),
            actual=str(parameters.alignment_feature_count),
        )
    _ = validate_sha256(
        field="alignment_feature_identity",
        value=parameters.alignment_feature_identity,
        prefixed=False,
    )
    _require_finite_number(
        "normalization_target_sum", parameters.normalization_target_sum
    )
    _require_optional_positive_integer("max_features", parameters.max_features)
    expected_identity = sha256("\0".join(feature_ids).encode()).hexdigest()
    if parameters.alignment_feature_identity != expected_identity:
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_identity",
            expected=expected_identity,
            actual=parameters.alignment_feature_identity,
        )


def _feature_ids(value: tuple[str, ...]) -> tuple[str, ...]:
    """Parse bounded, ordered feature identifiers from a hostile receipt field."""
    if type(value) is not tuple:
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_ids",
            expected="tuple of feature identifiers",
            actual=type(value).__name__,
        )
    if len(value) > MAX_ALIGNMENT_FEATURE_IDS:
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_ids",
            expected=f"at most {MAX_ALIGNMENT_FEATURE_IDS} feature identifiers",
            actual=str(len(value)),
        )
    if len(value) != len(set(value)):
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_ids",
            expected="unique feature identifiers in preparation order",
            actual=str(len(value)),
        )
    for feature_id in value:
        _ = validate_safe_identifier(
            field="alignment_feature_id",
            value=feature_id,
        )
    return value


def _require_positive_integer(field: str, value: int) -> None:
    """Require an exact positive integer rather than bool or a numeric lookalike."""
    if type(value) is not int or value < 1:
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected="positive integer",
            actual=type(value).__name__,
        )


def _require_non_negative_integer(field: str, value: int) -> None:
    """Require an exact non-negative integer count."""
    if type(value) is not int or value < 0:
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected="non-negative integer",
            actual=type(value).__name__,
        )


def _require_finite_number(field: str, value: float) -> None:
    """Reject booleans, text, and non-finite numeric renderings."""
    if type(value) not in (int, float) or not isfinite(value):
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected="finite number",
            actual=type(value).__name__,
        )


def _require_optional_positive_integer(field: str, value: int | None) -> None:
    """Require a feature cap to be absent or an exact positive integer."""
    if value is not None and (type(value) is not int or value < 1):
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected="positive integer or none",
            actual=type(value).__name__,
        )
