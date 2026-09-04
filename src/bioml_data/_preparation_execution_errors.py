"""Typed failures at the preparation-execution receipt boundary."""

from typing import final, override


@final
class PreparationExecutionReceiptMismatchError(Exception):
    """Raised when execution layers cannot be joined into one receipt."""

    __slots__ = ("actual", "expected", "field")

    field: str
    expected: str
    actual: str

    def __init__(self, field: str, expected: str, actual: str) -> None:
        super().__init__(field, expected, actual)
        self.field = field
        self.expected = expected
        self.actual = actual

    @override
    def __str__(self) -> str:
        return (
            f"preparation execution receipt mismatch for {self.field}: "
            f"expected {self.expected!r}, received {self.actual!r}"
        )
