"""Deterministic four-study pancreas archive materialization."""

import csv
import math
from array import array
from hashlib import sha256
from importlib.metadata import version as package_version
from io import TextIOWrapper
from pathlib import Path
from typing import Final
from zipfile import BadZipFile, ZipFile

from bioml_data._artifact_receipts import (
    ArtifactReceiptFailure,
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactDerivation,
    ArtifactReceipt,
    ArtifactRequest,
)
from bioml_data._dataset_preparation_models import (
    DatasetPreparationOutcome,
    DatasetPreparationReceipt,
    PreparedDatasetCacheError,
)
from bioml_data.datasets.pancreas._identity import (
    PANCREAS_TRANSFORM_PARAMETERS,
    PANCREAS_TRANSFORM_PROTOCOL,
)
from bioml_data.datasets.pancreas._interchange import (
    PancreasObservationPayload,
    PancreasPayload,
    serialize_payload,
)

_COMBINED_MATRIX_MEMBER: Final = (
    "Inter-dataset/Pancreatic/Combined_HumanPancreas_data.csv"
)
_COMBINED_LABEL_MEMBER: Final = "Inter-dataset/Pancreatic/Labels.csv"
_STUDY_BOUNDARIES: Final = (
    ("Baron Human", 0, 5_707),
    ("Muraro", 5_707, 7_261),
    ("Segerstolpe", 7_261, 8_701),
    ("Xin", 8_701, 10_150),
)
_ELIGIBLE_LABELS: Final = frozenset(("alpha", "beta", "delta", "gamma"))
_HEADER_COLUMNS: Final = 2
_INVALID_HEADER: Final = "invalid pancreas matrix header"
_INVALID_ROW_COUNT: Final = "unexpected pancreas benchmark row count"
_INVALID_ROW: Final = "invalid pancreas combined matrix row"
_NEGATIVE_COUNT: Final = "negative count"
_INVALID_VALUE: Final = "non-finite expression value"
_EMPTY_OBSERVATIONS: Final = "no eligible pancreas observations"
_INVALID_LABEL: Final = "invalid pancreas label row"
_INVALID_ORDER: Final = "unexpected pancreas benchmark row order"


def prepare_pancreas(
    raw_artifact: ArtifactReceipt,
    *,
    data_dir: Path,
) -> DatasetPreparationReceipt:
    """Materialize or reuse the exact four-label pancreas CSR artifact."""
    raw = load_artifact_receipt(raw_artifact.manifest_path)
    if raw.artifact_id != raw_artifact.artifact_id:
        raise ArtifactReceiptLoadError(
            manifest_path=raw_artifact.manifest_path,
            reason=ArtifactReceiptFailure.CONTENT_INTEGRITY,
        )
    locator = _locator_path(data_dir, raw)
    cached = _cached(locator, data_dir=data_dir, raw=raw)
    if cached is not None:
        return DatasetPreparationReceipt(
            artifact=cached,
            parent_artifacts=(raw,),
            outcome=DatasetPreparationOutcome.CACHE_HIT,
        )
    content = _canonical_content(raw)
    request = ArtifactRequest(
        logical_name="pancreas-four-study-csr-v1.npz",
        source_uri=raw.manifest.source_uri,
        accession=f"{raw.manifest.accession}:pancreas-four-study-csr-v1",
        release=raw.manifest.release,
        retrieved_at=raw.manifest.retrieved_at,
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version=f"bioml-data/{package_version('bioml-data')}",
        derivation=_derivation(raw),
    )
    prepared = ArtifactCache(data_dir).store(request, (content,))
    _write_locator(locator, prepared)
    return DatasetPreparationReceipt(
        artifact=prepared,
        parent_artifacts=(raw,),
        outcome=DatasetPreparationOutcome.TRANSFORMED,
    )


def _canonical_content(raw: ArtifactReceipt) -> bytes:
    try:
        with ZipFile(raw.content_path) as archive:
            features = _header(archive)
            observations, values, indices, offsets = _rows(archive, features)
    except (BadZipFile, KeyError, UnicodeDecodeError, csv.Error, ValueError) as error:
        raise PreparedDatasetCacheError(raw.content_path) from error
    payload = PancreasPayload(
        schema_version="pancreas-four-study-csr-v1",
        observations=observations,
        features=features,
    )
    return serialize_payload(payload, values, indices, offsets)


def _header(archive: ZipFile) -> tuple[str, ...]:
    with archive.open(_COMBINED_MATRIX_MEMBER) as source:
        header = next(csv.reader(TextIOWrapper(source, encoding="utf-8", newline="")))
    if len(header) < _HEADER_COLUMNS or not all(item for item in header[1:]):
        raise csv.Error(_INVALID_HEADER)
    return tuple(header[1:])


def _rows(
    archive: ZipFile,
    features: tuple[str, ...],
) -> tuple[
    tuple[PancreasObservationPayload, ...],
    array[float],
    array[int],
    array[int],
]:
    observations: list[PancreasObservationPayload] = []
    values: array[float] = array("d")
    indices: array[int] = array("q")
    offsets: array[int] = array("q", (0,))
    labels = _labels(archive)
    if len(labels) != _STUDY_BOUNDARIES[-1][2]:
        raise csv.Error(_INVALID_ROW_COUNT)
    with archive.open(_COMBINED_MATRIX_MEMBER) as source:
        rows = csv.reader(TextIOWrapper(source, encoding="utf-8", newline=""))
        _ = next(rows)
        for row_number, (label, row) in enumerate(zip(labels, rows, strict=True)):
            valid = (
                label in _ELIGIBLE_LABELS
                and len(row) == len(features) + 1
                and bool(row[0])
            )
            if not valid:
                raise csv.Error(_INVALID_ROW)
            observations.append(
                PancreasObservationPayload(
                    cell_id=f"{_study_for(row_number)}:{row[0]}",
                    study_id=_study_for(row_number),
                    cell_type=label,
                )
            )
            for position, raw_value in enumerate(row[1:]):
                value = float(raw_value)
                if not math.isfinite(value):
                    raise ValueError(_INVALID_VALUE)
                if value < 0:
                    raise ValueError(_NEGATIVE_COUNT)
                if value:
                    values.append(value)
                    indices.append(position)
            offsets.append(len(values))
    if not observations:
        raise csv.Error(_EMPTY_OBSERVATIONS)
    return tuple(observations), values, indices, offsets


def _labels(archive: ZipFile) -> tuple[str, ...]:
    with archive.open(_COMBINED_LABEL_MEMBER) as source:
        rows = csv.reader(TextIOWrapper(source, encoding="utf-8", newline=""))
        _ = next(rows)
        return tuple(_normalized_label(row) for row in rows)


def _normalized_label(row: list[str]) -> str:
    if len(row) != 1:
        raise csv.Error(_INVALID_LABEL)
    return "gamma" if row[0] == "pp" else row[0]


def _study_for(row_number: int) -> str:
    for study, start, stop in _STUDY_BOUNDARIES:
        if start <= row_number < stop:
            return study
    raise csv.Error(_INVALID_ORDER)


def _derivation(raw: ArtifactReceipt) -> ArtifactDerivation:
    """Return the stable raw-parent transform edge for one prepared artifact."""
    return ArtifactDerivation(
        parent_artifacts=(raw.artifact_id,),
        transform_protocol=PANCREAS_TRANSFORM_PROTOCOL,
        parameters=PANCREAS_TRANSFORM_PARAMETERS,
    )


def _locator_path(data_dir: Path, raw: ArtifactReceipt) -> Path:
    return (
        data_dir
        / "prepared"
        / "pancreas-four-study"
        / raw.manifest.sha256
        / "pancreas-four-study-csr-v1.sha256"
    )


def _cached(
    locator: Path,
    *,
    data_dir: Path,
    raw: ArtifactReceipt,
) -> ArtifactReceipt | None:
    if not locator.exists():
        return None
    try:
        digest = locator.read_text(encoding="utf-8").strip()
        manifest = data_dir / "sha256" / digest[:2] / digest / "manifest.json"
        prepared = load_artifact_receipt(manifest)
    except (ArtifactReceiptLoadError, OSError):
        raise PreparedDatasetCacheError(locator) from None
    derivation = prepared.manifest.derivation
    if (
        derivation is None
        or derivation.parent_artifacts != (raw.artifact_id,)
        or derivation.transform_protocol != PANCREAS_TRANSFORM_PROTOCOL
        or derivation.parameters != PANCREAS_TRANSFORM_PARAMETERS
    ):
        raise PreparedDatasetCacheError(locator)
    return prepared


def _write_locator(locator: Path, prepared: ArtifactReceipt) -> None:
    locator.parent.mkdir(parents=True, exist_ok=True)
    try:
        _ = locator.write_text(prepared.manifest.sha256, encoding="utf-8")
    except OSError as error:
        raise PreparedDatasetCacheError(locator) from error
