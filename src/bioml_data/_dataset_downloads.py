"""Pinned dataset downloads with integrity-first cache reuse."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, unique
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Final, final, override

import httpx2

from bioml_data._artifacts import ArtifactCache, ArtifactReceipt, ArtifactRequest
from bioml_data._dataset_download_models import DatasetDownloadPin, Sha256Provenance
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data._http_artifacts import HttpArtifactDownload, download_artifact
from bioml_data.datasets._registry import DATASET_REGISTRY
from bioml_data.datasets.tms_aorta._definition import TMS_AORTA_DOWNLOAD_PIN

_DOWNLOAD_PINS: Final = (TMS_AORTA_DOWNLOAD_PIN,)


@unique
class DatasetDownloadOutcome(StrEnum):
    """Whether a dataset invocation transferred bytes or reused its cache."""

    CACHE_HIT = "cache_hit"
    DOWNLOADED = "downloaded"


@dataclass(frozen=True, slots=True)
class DatasetDownloadReceipt:
    """One dataset resolution outcome without duplicating artifact provenance."""

    artifact: ArtifactReceipt
    outcome: DatasetDownloadOutcome

    @property
    def cache_hit(self) -> bool:
        """Return whether the network was skipped after integrity verification."""
        return self.outcome is DatasetDownloadOutcome.CACHE_HIT

    @property
    def downloaded(self) -> bool:
        """Return whether this invocation transferred the pinned bytes."""
        return self.outcome is DatasetDownloadOutcome.DOWNLOADED


@final
class DatasetDownloadUnavailableError(Exception):
    """Raised when a catalog snapshot has no implemented download pin."""

    __slots__ = ("dataset",)

    dataset: DatasetSnapshotIdentity

    def __init__(self, dataset: DatasetSnapshotIdentity) -> None:
        super().__init__(dataset)
        self.dataset = dataset

    @override
    def __str__(self) -> str:
        return f"dataset download is unavailable for {self.dataset!r}"


@dataclass(frozen=True, slots=True)
class DuplicateDatasetDownloadPinError(Exception):
    """Raised when the compatibility index has ambiguous exact snapshot pins."""

    dataset: DatasetSnapshotIdentity

    @override
    def __str__(self) -> str:
        return f"duplicate dataset download pins for {self.dataset!r}"


def get_dataset_download_pin(
    name: str,
    *,
    version: str | None = None,
) -> DatasetDownloadPin:
    """Resolve the verified HTTP compatibility pin for an exact snapshot."""
    registration = DATASET_REGISTRY.resolve(name, version=version)
    matching = tuple(
        pin for pin in _DOWNLOAD_PINS if pin.dataset == registration.definition.snapshot
    )
    if len(matching) > 1:
        raise DuplicateDatasetDownloadPinError(dataset=registration.definition.snapshot)
    if not matching:
        raise DatasetDownloadUnavailableError(
            dataset=registration.definition.snapshot,
        )
    return matching[0]


def download_dataset(
    name: str,
    *,
    data_dir: Path,
    version: str | None = None,
) -> DatasetDownloadReceipt:
    """Download or integrity-check one dataset in a caller-selected cache root."""
    pin = get_dataset_download_pin(name, version=version)
    return download_pinned_dataset(pin, data_dir=data_dir)


def download_pinned_dataset(
    pin: DatasetDownloadPin,
    *,
    data_dir: Path,
    transport: httpx2.BaseTransport | None = None,
) -> DatasetDownloadReceipt:
    """Resolve one typed pin, with an injectable HTTP transport for CI."""
    request = ArtifactRequest(
        logical_name=pin.filename,
        source_uri=pin.source_uri,
        accession=f"figshare-file-{pin.file_id}",
        release=pin.release,
        retrieved_at=datetime.now(tz=UTC),
        expected_byte_size=pin.byte_size,
        expected_sha256=pin.sha256,
        tool_version=f"bioml-data/{package_version('bioml-data')}",
    )
    cache = ArtifactCache(data_dir)
    cached = cache.lookup(request)
    if cached is not None:
        return DatasetDownloadReceipt(
            artifact=cached,
            outcome=DatasetDownloadOutcome.CACHE_HIT,
        )
    artifact = download_artifact(
        HttpArtifactDownload(request=request, cache=cache),
        transport=transport,
    )
    return DatasetDownloadReceipt(
        artifact=artifact,
        outcome=DatasetDownloadOutcome.DOWNLOADED,
    )


__all__ = [
    "DatasetDownloadOutcome",
    "DatasetDownloadPin",
    "DatasetDownloadReceipt",
    "DatasetDownloadUnavailableError",
    "DuplicateDatasetDownloadPinError",
    "Sha256Provenance",
    "download_dataset",
    "download_pinned_dataset",
    "get_dataset_download_pin",
]
