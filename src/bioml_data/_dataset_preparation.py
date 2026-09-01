"""Public dataset preparation facade."""

from dataclasses import dataclass
from pathlib import Path
from typing import final, override

from bioml_data._artifacts import ArtifactReceipt
from bioml_data._dataset_preparation_models import DatasetPreparationReceipt
from bioml_data.datasets._registry import DATASET_REGISTRY
from bioml_data.datasets.tms_aorta._identity import TMS_AORTA_SNAPSHOT
from bioml_data.datasets.tms_aorta._transform import prepare_tms_aorta


@final
@dataclass(frozen=True, slots=True)
class DatasetPreparationUnavailableError(Exception):
    """Raised when a registered snapshot has no canonical transform."""

    name: str

    @override
    def __str__(self) -> str:
        return f"dataset preparation is unavailable for {self.name!r}"


def prepare_dataset(
    name: str,
    *,
    artifact: ArtifactReceipt,
    data_dir: Path,
    version: str | None = None,
) -> DatasetPreparationReceipt:
    """Transform a verified upstream artifact into a canonical artifact."""
    registration = DATASET_REGISTRY.resolve(name, version=version)
    if registration.definition.snapshot != TMS_AORTA_SNAPSHOT:
        raise DatasetPreparationUnavailableError(name=name)
    return prepare_tms_aorta(artifact, data_dir=data_dir)
