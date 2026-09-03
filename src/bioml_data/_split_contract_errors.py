"""Typed split-contract boundary errors."""

from dataclasses import dataclass
from typing import override


@dataclass(frozen=True, slots=True)
class InvalidSplitCanaryUsageError(Exception):
    """Raised when package canary usage is not an exact boolean."""

    protocol: str
    actual_type: str

    @override
    def __str__(self) -> str:
        return (
            f"canary usage for {self.protocol!r} must be bool, got {self.actual_type}"
        )


def require_exact_bool(
    value: bool | str | float | None,
    *,
    protocol: str,
) -> bool:
    """Parse public package-test usage into an exact boolean."""
    if type(value) is bool:
        return value
    raise InvalidSplitCanaryUsageError(
        protocol=protocol,
        actual_type=type(value).__name__,
    )


def require_exact_split_enum[T](
    value: T | None,
    *,
    expected_type: type[T],
    protocol: str,
    field: str,
) -> T | None:
    """Parse one closed split enum without accepting lookalike strings."""
    if value is None or type(value) is expected_type:
        return value
    if field == "role":
        raise InvalidSplitProtocolRoleError(
            protocol=protocol,
            actual_type=type(value).__name__,
        )
    raise InvalidSplitSemanticTypeError(
        protocol=protocol,
        field=field,
        expected_type=expected_type.__name__,
        actual_type=type(value).__name__,
    )


@dataclass(frozen=True, slots=True)
class InvalidSplitProtocolRoleError(Exception):
    """Raised when a legacy split role is not a declared enum member."""

    protocol: str
    actual_type: str

    @override
    def __str__(self) -> str:
        return (
            f"legacy split role for {self.protocol!r} must be "
            f"SplitProtocolRole, got {self.actual_type}"
        )


@dataclass(frozen=True, slots=True)
class InvalidSplitSemanticTypeError(Exception):
    """Raised when split basis or strategy is not its declared enum."""

    protocol: str
    field: str
    expected_type: str
    actual_type: str

    @override
    def __str__(self) -> str:
        return (
            f"split {self.field} for {self.protocol!r} must be {self.expected_type}, "
            f"got {self.actual_type}"
        )


@dataclass(frozen=True, slots=True)
class InvalidSplitRoleProjectionError(Exception):
    """Deprecated error retained after projection provenance became internal."""

    protocol: str
    actual_type: str

    @override
    def __str__(self) -> str:
        return (
            f"legacy role projection for {self.protocol!r} has invalid provenance "
            f"type {self.actual_type}"
        )


@dataclass(frozen=True, slots=True)
class MissingSplitContractFieldError(Exception):
    """Raised when a legacy-compatible constructor omits a required field."""

    contract: str
    field: str

    @override
    def __str__(self) -> str:
        return f"{self.contract} requires {self.field}"


def require_split_contract_field[T](
    value: T | None,
    *,
    field: str,
    contract: str = "split capability",
) -> T:
    """Narrow one required constructor value at the compatibility boundary."""
    if value is None:
        raise MissingSplitContractFieldError(contract=contract, field=field)
    return value
