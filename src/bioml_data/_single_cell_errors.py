"""Typed canonical single-cell schema failures."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import override


@unique
class SparseMatrixViolation(StrEnum):
    """Structural invariant violated by sparse matrix arrays."""

    SHAPE = "shape"
    VALUE_INDEX_LENGTH = "value_index_length"
    ROW_OFFSETS = "row_offsets"
    COLUMN_INDEX = "column_index"
    DUPLICATE_COORDINATE = "duplicate_coordinate"
    NEGATIVE_COUNT = "negative_count"


@dataclass(frozen=True, slots=True)
class MissingIdentifierError(Exception):
    """Raised when a canonical identifier is empty."""

    field: str
    position: int

    @override
    def __str__(self) -> str:
        return f"missing {self.field} at position {self.position}"


@dataclass(frozen=True, slots=True)
class MissingMetadataError(Exception):
    """Raised when required non-identity metadata is empty."""

    field: str
    record_id: str

    @override
    def __str__(self) -> str:
        return f"missing {self.field} for record {self.record_id!r}"


@dataclass(frozen=True, slots=True)
class DuplicateIdentifierError(Exception):
    """Raised when canonical cell or feature identities are not unique."""

    field: str
    value: str

    @override
    def __str__(self) -> str:
        return f"duplicate {self.field} {self.value!r}"


@dataclass(frozen=True, slots=True)
class InvalidSparseMatrixError(Exception):
    """Raised when CSR arrays violate their structural contract."""

    violation: SparseMatrixViolation

    @override
    def __str__(self) -> str:
        return f"invalid sparse count matrix: {self.violation}"
