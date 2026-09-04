"""Typed preparation lifecycle failures."""

from dataclasses import dataclass
from typing import override


@dataclass(frozen=True, slots=True)
class SplitAssignmentRequiredError(Exception):
    """Raised when train-fitted preprocessing is attempted before splitting."""

    protocol_id: str

    @override
    def __str__(self) -> str:
        return f"split assignment required before fitting {self.protocol_id!r}"


@dataclass(frozen=True, slots=True)
class InsufficientPreparationDataError(Exception):
    """Raised when preparation filters leave no usable rows or features."""

    phase: str

    @override
    def __str__(self) -> str:
        return f"preparation has no usable data after {self.phase}"


@dataclass(frozen=True, slots=True)
class InvalidNormalizationTargetError(Exception):
    """Raised when library-size normalization cannot be represented safely."""

    target_sum: float

    @override
    def __str__(self) -> str:
        return f"normalization target must be finite; received {self.target_sum!r}"


@dataclass(frozen=True, slots=True)
class InvalidPreparedValueError(Exception):
    """Raised when sparse prepared values cannot be represented safely."""

    value: float

    @override
    def __str__(self) -> str:
        return f"prepared value must be finite; received {self.value!r}"


@dataclass(frozen=True, slots=True)
class UnknownAlignmentFeatureError(Exception):
    """Raised when a fixed alignment requests a feature absent from the input."""

    feature_id: str

    @override
    def __str__(self) -> str:
        return f"alignment feature {self.feature_id!r} is absent"


@dataclass(frozen=True, slots=True)
class FittedStateMismatchError(Exception):
    """Raised when fitted state is applied to a different prepared artifact."""

    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        return f"fitted state expects {self.expected}; received {self.actual}"


@dataclass(frozen=True, slots=True)
class FittedSplitMismatchError(Exception):
    """Raised when fitted state is applied under a different split receipt."""

    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        return f"fitted state expects split {self.expected}; received {self.actual}"


@dataclass(frozen=True, slots=True)
class FittedProtocolSemanticMismatchError(Exception):
    """Raised when fitted state belongs to another protocol semantic identity."""

    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        return (
            f"fitted state expects protocol semantics {self.expected}; "
            f"received {self.actual}"
        )
