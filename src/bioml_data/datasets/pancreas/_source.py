"""Pinned local acquisition and byte-level inspection for the pancreas archive."""

import csv
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from io import TextIOWrapper
from pathlib import Path
from typing import BinaryIO, Final, final, override
from zipfile import BadZipFile, ZipFile

import httpx2

from bioml_data._artifact_paths import open_binary_nofollow
from bioml_data._artifact_receipts import (
    load_artifact_receipt,
)
from bioml_data._artifacts import ArtifactCache, ArtifactReceipt, ArtifactRequest
from bioml_data._dataset_download_models import DatasetDownloadOutcome
from bioml_data._http_artifacts import HttpArtifactDownload, download_artifact
from bioml_data._metadata_concordance_models import MetadataCount


@dataclass(frozen=True, slots=True)
class PancreasArchiveSourcePin:
    """One immutable Zenodo archive identity, including local SHA-256 evidence."""

    record_id: str
    file_id: str
    source_uri: str
    filename: str
    byte_size: int
    official_md5: str
    sha256: str
    license: str


PANCREAS_ZENODO_ARCHIVE: Final = PancreasArchiveSourcePin(
    record_id="3357167",
    file_id="4282cdc9-55cd-4b4d-aa13-2ff780c742bf",
    source_uri=(
        "https://zenodo.org/api/records/3357167/files/"
        "scRNAseq_Benchmark_datasets.zip/content"
    ),
    filename="scRNAseq_Benchmark_datasets.zip",
    byte_size=3_671_466_589,
    official_md5="b799a660b8bcaf5f3580a9b6f9372e5b",
    sha256="038d0a61ed3891c3d5f4ebd1dab5956465223e38b89859e1bf4792a9aeffbf06",
    license="CC-BY-4.0",
)


@dataclass(frozen=True, slots=True)
class PancreasArchiveReceipt:
    """Verified local archive receipt and whether this call transferred bytes."""

    artifact: ArtifactReceipt
    outcome: DatasetDownloadOutcome

    @property
    def cache_hit(self) -> bool:
        """Return whether this call reused fully verified local archive bytes."""
        return self.outcome is DatasetDownloadOutcome.CACHE_HIT

    @property
    def downloaded(self) -> bool:
        """Return whether this call transferred the pinned archive bytes."""
        return self.outcome is DatasetDownloadOutcome.DOWNLOADED


@dataclass(frozen=True, slots=True)
class PancreasStudyInspection:
    """Observed whole-study and four-label metadata from one archive member set."""

    study: str
    sample_count: int
    feature_dimension: int
    distinct_label_count: int
    four_label_counts: tuple[MetadataCount, ...]


@dataclass(frozen=True, slots=True)
class PancreasArchiveInspection:
    """The four evidence-bearing pancreas cohort observations in archive order."""

    artifact: ArtifactReceipt
    cohorts: tuple[PancreasStudyInspection, ...]


@dataclass(frozen=True, slots=True)
class _CohortLayout:
    """Fixed member locations for one cohort in Zenodo record 3357167."""

    study: str
    matrix_member: str

    @property
    def labels_member(self) -> str:
        return f"Intra-dataset/Pancreatic_data/{self.study}/Labels.csv"


_COHORT_LAYOUTS: Final = (
    _CohortLayout(
        study="Baron Human",
        matrix_member=(
            "Intra-dataset/Pancreatic_data/Baron Human/"
            "Filtered_Baron_HumanPancreas_data.csv"
        ),
    ),
    _CohortLayout(
        study="Muraro",
        matrix_member=(
            "Intra-dataset/Pancreatic_data/Muraro/"
            "Filtered_Muraro_HumanPancreas_data.csv"
        ),
    ),
    _CohortLayout(
        study="Segerstolpe",
        matrix_member=(
            "Intra-dataset/Pancreatic_data/Segerstolpe/"
            "Filtered_Segerstolpe_HumanPancreas_data.csv"
        ),
    ),
    _CohortLayout(
        study="Xin",
        matrix_member=(
            "Intra-dataset/Pancreatic_data/Xin/Filtered_Xin_HumanPancreas_data.csv"
        ),
    ),
)
_FOUR_LABELS: Final = ("alpha", "beta", "delta", "gamma")
_MINIMUM_MATRIX_HEADER_COLUMNS: Final = 2
_INVALID_LABEL_ROW: Final = "expected exactly one label column"
_INVALID_MATRIX_HEADER: Final = "expected cell-index and feature columns"


@final
class UnexpectedPancreasArchiveError(Exception):
    """Raised when an archive receipt differs from the exact Zenodo source pin."""

    __slots__ = ("artifact",)

    artifact: ArtifactReceipt

    def __init__(self, artifact: ArtifactReceipt) -> None:
        super().__init__(artifact.artifact_id)
        self.artifact = artifact

    @override
    def __str__(self) -> str:
        return (
            f"artifact {self.artifact.artifact_id} is not the pinned pancreas archive"
        )


@final
class InvalidPancreasArchiveError(Exception):
    """Raised when the pinned archive lacks its required CSV member layout."""

    __slots__ = ("artifact",)

    artifact: ArtifactReceipt

    def __init__(self, artifact: ArtifactReceipt) -> None:
        super().__init__(artifact.artifact_id)
        self.artifact = artifact

    @override
    def __str__(self) -> str:
        return (
            "pinned pancreas archive has an invalid CSV member layout: "
            f"{self.artifact.artifact_id}"
        )


def fetch_pancreas_archive(
    *,
    data_dir: Path,
    transport: httpx2.BaseTransport | None = None,
) -> PancreasArchiveReceipt:
    """Fetch or fully verify the pinned archive in a caller-selected cache root."""
    request = _artifact_request(PANCREAS_ZENODO_ARCHIVE)
    cache = ArtifactCache(data_dir)
    cached = cache.lookup(request)
    if cached is not None:
        return PancreasArchiveReceipt(
            artifact=cached,
            outcome=DatasetDownloadOutcome.CACHE_HIT,
        )
    artifact = download_artifact(
        HttpArtifactDownload(request=request, cache=cache),
        transport=transport,
    )
    return PancreasArchiveReceipt(
        artifact=artifact,
        outcome=DatasetDownloadOutcome.DOWNLOADED,
    )


def cache_pancreas_archive(
    archive_path: Path,
    *,
    data_dir: Path,
) -> ArtifactReceipt:
    """Import already-fetched exact Zenodo bytes into the selected verified cache."""
    request = _artifact_request(PANCREAS_ZENODO_ARCHIVE)
    cache = ArtifactCache(data_dir)
    cached = cache.lookup(request)
    if cached is not None:
        return cached
    with open_binary_nofollow(archive_path) as source:
        return cache.store(request, _chunks(source))


def inspect_pancreas_archive(artifact: ArtifactReceipt) -> PancreasArchiveInspection:
    """Inspect labels and headers without extracting or materializing the archive."""
    verified = load_artifact_receipt(artifact.manifest_path)
    if (
        verified != artifact
        or verified.manifest.sha256 != PANCREAS_ZENODO_ARCHIVE.sha256
    ):
        raise UnexpectedPancreasArchiveError(artifact=artifact)
    try:
        with ZipFile(verified.content_path) as archive:
            cohorts = tuple(
                _inspect_cohort(archive, layout) for layout in _COHORT_LAYOUTS
            )
    except (BadZipFile, KeyError, UnicodeDecodeError, csv.Error) as error:
        raise InvalidPancreasArchiveError(artifact=verified) from error
    return PancreasArchiveInspection(artifact=verified, cohorts=cohorts)


def _artifact_request(pin: PancreasArchiveSourcePin) -> ArtifactRequest:
    return ArtifactRequest(
        logical_name=pin.filename,
        source_uri=pin.source_uri,
        accession=f"zenodo-record-{pin.record_id}:file-{pin.file_id}",
        release=f"record-{pin.record_id}",
        retrieved_at=datetime.now(tz=UTC),
        expected_byte_size=pin.byte_size,
        expected_sha256=pin.sha256,
        tool_version=f"bioml-data/{package_version('bioml-data')}",
    )


def _chunks(source: BinaryIO) -> Iterator[bytes]:
    while True:
        chunk = source.read(1024 * 1024)
        if not chunk:
            return
        yield chunk


def _inspect_cohort(archive: ZipFile, layout: _CohortLayout) -> PancreasStudyInspection:
    labels = tuple(_labels(archive, layout.labels_member))
    counts = Counter(_normalize_label(item) for item in labels)
    return PancreasStudyInspection(
        study=layout.study,
        sample_count=len(labels),
        feature_dimension=_feature_dimension(archive, layout.matrix_member),
        distinct_label_count=len(counts),
        four_label_counts=tuple(
            MetadataCount(value=label, count=counts[label])
            for label in _FOUR_LABELS
            if counts[label] > 0
        ),
    )


def _labels(archive: ZipFile, member: str) -> Iterator[str]:
    with archive.open(member) as source:
        reader = csv.reader(TextIOWrapper(source, encoding="utf-8", newline=""))
        _ = next(reader)
        for row in reader:
            if len(row) != 1:
                raise csv.Error(_INVALID_LABEL_ROW)
            yield row[0]


def _feature_dimension(archive: ZipFile, member: str) -> int:
    with archive.open(member) as source:
        reader = csv.reader(TextIOWrapper(source, encoding="utf-8", newline=""))
        header = next(reader)
    if len(header) < _MINIMUM_MATRIX_HEADER_COLUMNS:
        raise csv.Error(_INVALID_MATRIX_HEADER)
    return len(header) - 1


def _normalize_label(label: str) -> str:
    match label:
        case "pp":
            return "gamma"
        case _:
            return label
