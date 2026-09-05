"""Public facade over the built-in dataset registry."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, Never, overload, override

from bioml_data._artifact_lineage import ArtifactLineageReceipt
from bioml_data._artifacts import ArtifactReceipt
from bioml_data._dataset_definition import DatasetDefinition
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data.datasets._models import DatasetMaterialization
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
    name: Literal["tms-aorta", "pancreas-four-study"],
    *,
    version: str | None = None,
    artifact: ArtifactLineageReceipt,
) -> CanonicalSingleCellDataset: ...


@overload
def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: ArtifactLineageReceipt,
) -> DatasetMaterialization: ...


@overload
def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: ArtifactReceipt,
) -> Never: ...


def load_dataset(
    name: str,
    *,
    version: str | None = None,
    artifact: ArtifactLineageReceipt | ArtifactReceipt | None = None,
) -> DatasetDefinition | DatasetMaterialization:
    """Resolve a catalog definition or materialize its explicit local artifact."""
    registration = DATASET_REGISTRY.resolve(name, version=version)
    if artifact is None:
        return deepcopy(registration.definition)
    if isinstance(artifact, ArtifactReceipt):
        raise ArtifactLineageRequiredError(artifact=artifact)
    return DATASET_REGISTRY.materialize(name, artifact, version=version)


@dataclass(frozen=True, slots=True)
class ArtifactLineageRequiredError(Exception):
    """Raised when materialization omits verified parent receipts."""

    artifact: ArtifactReceipt

    @override
    def __str__(self) -> str:
        return f"artifact lineage receipts required for {self.artifact.artifact_id}"
