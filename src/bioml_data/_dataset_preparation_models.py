"""Public receipts and errors for dataset artifact preparation."""

from dataclasses import dataclass
from enum import StrEnum, unique
from pathlib import Path
from typing import final, override

from bioml_data._artifacts import ArtifactReceipt


@unique
class DatasetPreparationOutcome(StrEnum):
    """Whether preparation transformed bytes or reused verified output."""

    CACHE_HIT = "cache_hit"
    TRANSFORMED = "transformed"


@dataclass(frozen=True, slots=True)
class DatasetPreparationReceipt:
    """One canonical artifact preparation outcome."""

    artifact: ArtifactReceipt
    outcome: DatasetPreparationOutcome


@final
class PreparedDatasetCacheError(Exception):
    """Raised when a prepared-artifact locator or target fails verification."""

    __slots__ = ("locator_path",)

    locator_path: Path

    def __init__(self, locator_path: Path) -> None:
        super().__init__(locator_path)
        self.locator_path = locator_path

    @override
    def __str__(self) -> str:
        return f"prepared dataset cache is invalid at {self.locator_path}"
