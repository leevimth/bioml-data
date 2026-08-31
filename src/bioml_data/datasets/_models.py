"""Typed contracts shared by built-in dataset registrations."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from bioml_data._artifacts import ArtifactManifest, ArtifactReceipt
from bioml_data._domain import DatasetDefinition, DatasetSnapshotIdentity
from bioml_data._split_capability_models import SplitCapability


class DatasetMaterialization(Protocol):
    """Minimum common surface returned by a registered dataset adapter."""

    @property
    def snapshot(self) -> DatasetSnapshotIdentity:
        """Return the immutable dataset snapshot identity."""
        ...

    @property
    def artifact(self) -> ArtifactManifest:
        """Return the materialization's input artifact manifest."""
        ...


type DatasetAdapter = Callable[[ArtifactReceipt], DatasetMaterialization]


@dataclass(frozen=True, slots=True)
class DatasetRegistration:
    """One catalog definition and the implementations owned by its dataset."""

    definition: DatasetDefinition
    materialize: DatasetAdapter
    split_capabilities: tuple[SplitCapability, ...]
