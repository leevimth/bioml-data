"""Adapter from the pancreas sparse envelope to the canonical cell contract."""

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from typing import override
from zipfile import BadZipFile, ZipFile

import numpy as np
from pydantic import TypeAdapter, ValidationError

from bioml_data._artifacts import ArtifactReceipt, TransformProtocolId
from bioml_data._single_cell import (
    CanonicalFeature,
    CanonicalObservation,
    CanonicalSingleCellDataset,
    CellId,
    DatasetMaterializationId,
    DonorId,
    FeatureId,
    MatrixShape,
    SingleCellSourcePin,
    SparseCountMatrix,
    SparseFormat,
    StudyId,
)
from bioml_data._verified_artifact import VerifiedArtifactInput
from bioml_data.datasets.pancreas._identity import (
    PANCREAS_SNAPSHOT,
    PANCREAS_TRANSFORM_PARAMETERS,
    PANCREAS_TRANSFORM_PROTOCOL,
)
from bioml_data.datasets.pancreas._interchange import PancreasPayload

PANCREAS_SOURCE = SingleCellSourcePin(
    source_uri="https://zenodo.org/records/3357167",
    figshare_article="zenodo-record-3357167",
    figshare_release="record-3357167",
    geo_accession="not-reported",
    filename="scRNAseq_Benchmark_datasets.zip",
)
_INTEGER_TUPLE = TypeAdapter(tuple[int, ...])
_FLOAT_TUPLE = TypeAdapter(tuple[float, ...])


@dataclass(frozen=True, slots=True)
class InvalidPancreasSchemaError(Exception):
    """Raised when the local artifact is not the expected sparse envelope."""

    artifact_id: str

    @override
    def __str__(self) -> str:
        return f"artifact {self.artifact_id} is not valid pancreas sparse data"


@dataclass(frozen=True, slots=True)
class UnlinkedPancreasArtifactError(Exception):
    """Raised when a prepared artifact has a different transform declaration."""

    artifact_id: str
    protocol: TransformProtocolId | None

    @override
    def __str__(self) -> str:
        return (
            f"artifact {self.artifact_id} must be derived with "
            f"{PANCREAS_TRANSFORM_PROTOCOL}; received {self.protocol}"
        )


def load_pancreas(
    artifact: ArtifactReceipt | VerifiedArtifactInput,
) -> CanonicalSingleCellDataset:
    """Load a verified prepared pancreas envelope into canonical sparse rows."""
    verified = (
        artifact
        if isinstance(artifact, VerifiedArtifactInput)
        else VerifiedArtifactInput.from_receipt(artifact)
    )
    _require_derivation(verified)
    try:
        with ZipFile(BytesIO(verified.read_bytes())) as archive:
            payload = PancreasPayload.model_validate_json(archive.read("metadata.json"))
            values = _floats(archive, "data.npy")
            indices = _integers(archive, "indices.npy")
            offsets = _integers(archive, "indptr.npy")
    except (BadZipFile, KeyError, ValidationError, ValueError) as error:
        raise InvalidPancreasSchemaError(
            artifact_id=str(verified.artifact_id)
        ) from error
    observations = tuple(
        CanonicalObservation(
            cell_id=CellId(item.cell_id),
            donor_id=DonorId(item.study_id),
            study_id=StudyId(item.study_id),
            assay=None,
            tissue="pancreas",
            cell_type=item.cell_type,
        )
        for item in payload.observations
    )
    features = tuple(
        CanonicalFeature(feature_id=FeatureId(item), feature_name=item)
        for item in payload.features
    )
    counts = SparseCountMatrix(
        format=SparseFormat.CSR,
        shape=MatrixShape(observations=len(observations), features=len(features)),
        values=values,
        column_indices=indices,
        row_offsets=offsets,
    )
    identity_input = (
        f"{PANCREAS_SNAPSHOT.name}\0{PANCREAS_SNAPSHOT.version}\0"
        f"{verified.artifact_id}\0{PANCREAS_TRANSFORM_PROTOCOL}"
    )
    return CanonicalSingleCellDataset(
        identity=DatasetMaterializationId(sha256(identity_input.encode()).hexdigest()),
        snapshot=PANCREAS_SNAPSHOT,
        source=PANCREAS_SOURCE,
        artifact=verified.manifest,
        observations=observations,
        features=features,
        counts=counts,
    )


def _require_derivation(verified: VerifiedArtifactInput) -> None:
    derivation = verified.manifest.derivation
    if (
        derivation is None
        or derivation.transform_protocol != PANCREAS_TRANSFORM_PROTOCOL
        or derivation.parameters != PANCREAS_TRANSFORM_PARAMETERS
    ):
        protocol = None if derivation is None else derivation.transform_protocol
        raise UnlinkedPancreasArtifactError(
            artifact_id=str(verified.artifact_id),
            protocol=protocol,
        )


def _integers(archive: ZipFile, name: str) -> tuple[int, ...]:
    return _INTEGER_TUPLE.validate_python(
        np.load(BytesIO(archive.read(name)), allow_pickle=False)
    )


def _floats(archive: ZipFile, name: str) -> tuple[float, ...]:
    return _FLOAT_TUPLE.validate_python(
        np.load(BytesIO(archive.read(name)), allow_pickle=False)
    )
