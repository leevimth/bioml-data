"""Public facade over the built-in dataset registry."""

from typing import cast, overload

from bioml_data._artifacts import ArtifactReceipt
from bioml_data._domain import DatasetDefinition
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data.datasets._registry import DATASET_REGISTRY


@overload
def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: None = None,
) -> DatasetDefinition: ...


@overload
def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: ArtifactReceipt,
) -> CanonicalSingleCellDataset: ...


def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: ArtifactReceipt | None = None,
) -> DatasetDefinition | CanonicalSingleCellDataset:
    """Resolve a catalog definition or materialize its explicit local artifact."""
    registration = DATASET_REGISTRY.resolve(name, version=version)
    if artifact is None:
        return registration.definition
    return cast(
        "CanonicalSingleCellDataset",
        cast(
            "object",
            DATASET_REGISTRY.materialize(name, artifact, version=version),
        ),
    )
