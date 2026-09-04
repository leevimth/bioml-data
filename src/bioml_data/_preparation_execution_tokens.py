"""Safe bounded identifiers accepted by preparation-execution receipts."""

import re
from typing import Final

from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)

_SAFE_IDENTIFIER: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,127}$")


def validate_safe_identifier(*, field: str, value: str) -> str:
    """Reject host-local, URI, control, environment, and command-like strings."""
    if type(value) is not str or _SAFE_IDENTIFIER.fullmatch(value) is None:
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected="safe identifier syntax up to 128 characters",
            actual=type(value).__name__,
        )
    return value


def validate_sha256(*, field: str, value: str, prefixed: bool) -> str:
    """Validate one derived receipt digest or immutable artifact reference."""
    prefix = "sha256:" if prefixed else ""
    pattern = rf"^{re.escape(prefix)}[0-9a-f]{{64}}$"
    if type(value) is not str or re.fullmatch(pattern, value) is None:
        raise PreparationExecutionReceiptMismatchError(
            field=field,
            expected=f"{prefix}64 lowercase hexadecimal characters",
            actual=type(value).__name__,
        )
    return value
