"""Immutable, path-free scientific preparation-execution receipts."""

from dataclasses import dataclass
from enum import StrEnum, unique
from hashlib import sha256
from math import isfinite
from typing import Final, NewType

from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)

PreparationExecutionReceiptIdentity = NewType(
    "PreparationExecutionReceiptIdentity", str
)
MAX_ALIGNMENT_FEATURE_IDS: Final = 50_000


@unique
class ExpressionInput(StrEnum):
    """Matrix selected by the canonical dataset transform."""

    RAW_X = "raw.X"
    X = "X"


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
    if not isfinite(parameters.normalization_target_sum):
        raise PreparationExecutionReceiptMismatchError(
            field="normalization_target_sum",
            expected="finite float",
            actual=repr(parameters.normalization_target_sum),
        )
    feature_ids = parameters.alignment_feature_ids
    if len(feature_ids) > MAX_ALIGNMENT_FEATURE_IDS:
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_ids",
            expected=f"at most {MAX_ALIGNMENT_FEATURE_IDS} feature identifiers",
            actual=str(len(feature_ids)),
        )
    if parameters.alignment_feature_count != len(feature_ids):
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_count",
            expected=str(len(feature_ids)),
            actual=str(parameters.alignment_feature_count),
        )
    if len(feature_ids) != len(set(feature_ids)):
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_ids",
            expected="unique feature identifiers in preparation order",
            actual=str(len(feature_ids)),
        )
    expected_identity = sha256("\0".join(feature_ids).encode()).hexdigest()
    if parameters.alignment_feature_identity != expected_identity:
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_identity",
            expected=expected_identity,
            actual=parameters.alignment_feature_identity,
        )
