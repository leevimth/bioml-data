"""Shared closed preparation semantics independent of execution receipt rendering."""

from enum import StrEnum, unique


@unique
class ExpressionInput(StrEnum):
    """Matrix selected by the canonical dataset transform."""

    RAW_X = "raw.X"


@unique
class PreparationFitScope(StrEnum):
    """Scope from which a preparation stage may learn statistics."""

    NONE = "none"
    TRAIN_ONLY = "train_only"
