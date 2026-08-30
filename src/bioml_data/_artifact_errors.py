"""Typed failures for immutable content-addressed storage."""

from pathlib import Path
from typing import final, override

from bioml_data._artifact_types import ArtifactId, Sha256Hex


@final
class ChecksumMismatchError(Exception):
    """Raised when streamed bytes differ from the pinned SHA-256."""

    __slots__ = ("actual", "expected")

    actual: Sha256Hex
    expected: Sha256Hex

    def __init__(self, expected: Sha256Hex, actual: Sha256Hex) -> None:
        super().__init__(expected, actual)
        self.expected = expected
        self.actual = actual

    @override
    def __str__(self) -> str:
        return f"checksum mismatch: expected {self.expected}, received {self.actual}"


@final
class IncompleteDownloadError(Exception):
    """Raised when a stream ends before its declared byte size."""

    __slots__ = ("actual", "expected")

    actual: int
    expected: int

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(expected, actual)
        self.expected = expected
        self.actual = actual

    @override
    def __str__(self) -> str:
        return (
            f"incomplete download: expected {self.expected} bytes, "
            f"received {self.actual}"
        )


@final
class OversizedDownloadError(Exception):
    """Raised as soon as a stream exceeds its declared byte size."""

    __slots__ = ("actual", "expected")

    actual: int
    expected: int

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(expected, actual)
        self.expected = expected
        self.actual = actual

    @override
    def __str__(self) -> str:
        return (
            f"oversized download: expected {self.expected} bytes, "
            f"received at least {self.actual}"
        )


@final
class ArtifactCollisionError(Exception):
    """Raised when an occupied content address is not the expected artifact."""

    __slots__ = ("artifact_id", "path")

    artifact_id: ArtifactId
    path: Path

    def __init__(self, artifact_id: ArtifactId, path: Path) -> None:
        super().__init__(artifact_id, path)
        self.artifact_id = artifact_id
        self.path = path

    @override
    def __str__(self) -> str:
        return (
            f"artifact address {self.artifact_id} is occupied by invalid data "
            f"at {self.path}"
        )
