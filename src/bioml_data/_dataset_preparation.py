"""Public dataset preparation facade."""

from dataclasses import dataclass
from pathlib import Path
from typing import final, override

from bioml_data._artifact_receipts import (
    ArtifactReceiptFailure,
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifacts import ArtifactReceipt
from bioml_data._dataset_downloads import provider_target_for_pin
from bioml_data._dataset_preparation_models import DatasetPreparationReceipt
from bioml_data.datasets._registry import DATASET_REGISTRY
from bioml_data.datasets.pancreas._identity import PANCREAS_SNAPSHOT
from bioml_data.datasets.pancreas._materialization import prepare_pancreas
from bioml_data.datasets.pancreas._source import PANCREAS_ZENODO_ARCHIVE
from bioml_data.datasets.tms_aorta._definition import TMS_AORTA_DOWNLOAD_PIN
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


@final
@dataclass(frozen=True, slots=True)
class UnexpectedDatasetSourceError(Exception):
    """Raised when preparation input is not the dataset's exact pinned source."""

    name: str

    @override
    def __str__(self) -> str:
        return f"artifact does not match the pinned source for {self.name!r}"


def prepare_dataset(
    name: str,
    *,
    artifact: ArtifactReceipt,
    data_dir: Path,
    version: str | None = None,
) -> DatasetPreparationReceipt:
    """Transform a verified upstream artifact into a canonical artifact."""
    registration = DATASET_REGISTRY.resolve(name, version=version)
    verified = load_artifact_receipt(artifact.manifest_path)
    if verified.artifact_id != artifact.artifact_id:
        raise ArtifactReceiptLoadError(
            manifest_path=artifact.manifest_path,
            reason=ArtifactReceiptFailure.CONTENT_INTEGRITY,
        )
    if registration.definition.snapshot == PANCREAS_SNAPSHOT:
        _require_pancreas_source(verified, name=name)
        return prepare_pancreas(verified, data_dir=data_dir)
    if registration.definition.snapshot != TMS_AORTA_SNAPSHOT:
        raise DatasetPreparationUnavailableError(name=name)
    manifest = verified.manifest
    target = provider_target_for_pin(TMS_AORTA_DOWNLOAD_PIN)
    expectation = target.artifact_expectation
    source_matches = (
        manifest.artifact_id == target.scientific_identity.artifact_id
        and manifest.sha256 == expectation.sha256
        and manifest.byte_size == expectation.byte_size
        and manifest.logical_name == expectation.logical_name
        and manifest.source_uri == expectation.source_uri
        and manifest.accession == expectation.accession
        and manifest.release == expectation.release
        and manifest.derivation == expectation.derivation
    )
    if not source_matches:
        raise UnexpectedDatasetSourceError(name=name)
    return prepare_tms_aorta(verified, data_dir=data_dir)


def _require_pancreas_source(artifact: ArtifactReceipt, *, name: str) -> None:
    pin = PANCREAS_ZENODO_ARCHIVE
    manifest = artifact.manifest
    matches = (
        manifest.sha256 == pin.sha256
        and manifest.byte_size == pin.byte_size
        and manifest.logical_name == pin.filename
        and manifest.source_uri == pin.source_uri
        and manifest.accession == f"zenodo-record-{pin.record_id}:file-{pin.file_id}"
        and manifest.release == f"record-{pin.record_id}"
        and manifest.derivation is None
    )
    if not matches:
        raise UnexpectedDatasetSourceError(name=name)
