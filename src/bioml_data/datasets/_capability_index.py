"""One-shot immutable capability index for the validated built-in registry."""

from dataclasses import dataclass
from typing import override

from bioml_data._domain import DatasetSnapshotIdentity, TaskId
from bioml_data._split_capability_models import SplitCapability
from bioml_data.datasets._models import DatasetRegistration


@dataclass(frozen=True, slots=True)
class SplitCapabilityIndex:
    """Immutable projection used by low-dependency split lookup."""

    capabilities: tuple[SplitCapability, ...]
    assessed_scopes: frozenset[tuple[DatasetSnapshotIdentity, TaskId]]


@dataclass(frozen=True, slots=True)
class SplitCapabilityIndexAlreadyPublishedError(Exception):
    """Raised when startup code attempts to replace the built-in index."""

    @override
    def __str__(self) -> str:
        return "built-in split capability index is already published"


@dataclass(frozen=True, slots=True)
class SplitCapabilityIndexNotPublishedError(Exception):
    """Raised when capability lookup happens before package startup completes."""

    @override
    def __str__(self) -> str:
        return "built-in split capability index is not published"


class _IndexSlot:
    """Private one-shot slot preventing capability index replacement."""

    __slots__: tuple[str, ...] = ("_value",)

    _value: SplitCapabilityIndex | None

    def __init__(self) -> None:
        self._value = None

    def publish(self, value: SplitCapabilityIndex) -> None:
        """Publish exactly once during validated registry startup."""
        if self._value is not None:
            raise SplitCapabilityIndexAlreadyPublishedError
        self._value = value

    def get(self) -> SplitCapabilityIndex:
        """Return the published immutable index."""
        if self._value is None:
            raise SplitCapabilityIndexNotPublishedError
        return self._value


_INDEX_SLOT = _IndexSlot()


def publish_registry_capabilities(
    registrations: tuple[DatasetRegistration, ...],
) -> None:
    """Atomically publish capabilities from the validated built-in registry."""
    capabilities = tuple(
        capability
        for registration in registrations
        for capability in registration.split_capabilities
    )
    _INDEX_SLOT.publish(
        SplitCapabilityIndex(
            capabilities=capabilities,
            assessed_scopes=frozenset(
                (capability.dataset, capability.task) for capability in capabilities
            ),
        ),
    )


def get_split_capability_index() -> SplitCapabilityIndex:
    """Return the startup projection after registry validation completes."""
    return _INDEX_SLOT.get()
