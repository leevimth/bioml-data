"""Pinned dataset downloads with integrity-first cache reuse."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum, unique
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Final, final, override

import httpx2

from bioml_data._artifacts import ArtifactCache, ArtifactReceipt, ArtifactRequest
from bioml_data._catalog import load_dataset
from bioml_data._domain import DatasetName, DatasetSnapshotIdentity, DatasetVersion
from bioml_data._http_artifacts import HttpArtifactDownload, download_artifact


@unique
class Sha256Provenance(StrEnum):
    """Evidence source for a catalog SHA-256 value."""

    PROJECT_VERIFIED = "project_verified_against_official_size_and_md5"


@dataclass(frozen=True, slots=True)
class DatasetDownloadPin:
    """Immutable upstream file identity and checksum evidence."""

    dataset: DatasetSnapshotIdentity
    article_id: str
    article_doi: str
    release: str
    file_id: str
    source_uri: str
    filename: str
    byte_size: int
    official_md5: str
    sha256: str
    sha256_provenance: Sha256Provenance
    license: str


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


_TMS_AORTA_PIN: Final = DatasetDownloadPin(
    dataset=DatasetSnapshotIdentity(
        name=DatasetName("tms-aorta"),
        version=DatasetVersion("figshare-project-64982"),
    ),
    article_id="12654728",
    article_doi="10.6084/m9.figshare.12654728.v1",
    release="v1",
    file_id="23872460",
    source_uri="https://ndownloader.figshare.com/files/23872460",
    filename="tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad",
    byte_size=44_547_302,
    official_md5="4b1c150cf856a7406b3293ebdacd72c6",
    sha256=("0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3"),
    sha256_provenance=Sha256Provenance.PROJECT_VERIFIED,
    license="MIT",
)
_DOWNLOAD_PINS: Final = (_TMS_AORTA_PIN,)


def get_dataset_download_pin(
    name: str,
    *,
    version: str | None = None,
) -> DatasetDownloadPin:
    """Resolve the pinned upstream file for a catalog dataset snapshot."""
    definition = load_dataset(name, version=version)
    matching = tuple(
        pin for pin in _DOWNLOAD_PINS if pin.dataset == definition.snapshot
    )
    if not matching:
        raise DatasetDownloadUnavailableError(dataset=definition.snapshot)
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
