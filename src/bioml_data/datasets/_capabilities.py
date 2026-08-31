"""Capability index bound from authoritative dataset registrations."""

from collections.abc import Iterator
from typing import Final

from bioml_data._domain import DatasetSnapshotIdentity, TaskId
from bioml_data._split_capability_models import SplitCapability
from bioml_data.datasets._models import DatasetRegistration


class _BoundIndex[T]:
    """Mutable binding breaks the registry/capability import cycle at startup."""

    __slots__: tuple[str, ...] = ("values",)

    values: tuple[T, ...]

    def __init__(self) -> None:
        self.values = ()

    def bind(self, values: tuple[T, ...]) -> None:
        """Bind values derived from the completed built-in registry."""
        self.values = values

    def __iter__(self) -> Iterator[T]:
        return iter(self.values)


BUILTIN_SPLIT_CAPABILITIES: Final = _BoundIndex[SplitCapability]()
ASSESSED_SPLIT_SCOPES: Final = _BoundIndex[tuple[DatasetSnapshotIdentity, TaskId]]()


def bind_registry_capabilities(
    registrations: tuple[DatasetRegistration, ...],
) -> None:
    """Project capability indexes from the authoritative registrations."""
    capabilities = tuple(
        capability
        for registration in registrations
        for capability in registration.split_capabilities
    )
    BUILTIN_SPLIT_CAPABILITIES.bind(capabilities)
    ASSESSED_SPLIT_SCOPES.bind(
        tuple(
            dict.fromkeys(
                (capability.dataset, capability.task) for capability in capabilities
            )
        )
    )
