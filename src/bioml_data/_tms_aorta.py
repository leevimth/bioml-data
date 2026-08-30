"""Tabula Muris Senis FACS Aorta adapter."""

from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, ClassVar, Final, Literal, override

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, ValidationError

from bioml_data._artifacts import (
    ArtifactId,
    ArtifactReceipt,
    TransformProtocolId,
)
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
)
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

TMS_AORTA_TRANSFORM_PROTOCOL: Final = TransformProtocolId("tms-aorta-csr-v1")
TMS_AORTA_SOURCE: Final = SingleCellSourcePin(
    source_uri="https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728",
    figshare_article="12654728",
    figshare_release="v1",
    geo_accession="GSE149590",
    filename="tabula-muris-senis-facs-processed-official-annotations-Aorta.h5ad",
)
_TMS_AORTA_SNAPSHOT: Final = DatasetSnapshotIdentity(
    name=DatasetName("tms-aorta"),
    version=DatasetVersion("figshare-project-64982"),
)
_TMS_STUDY_ID: Final = StudyId("GSE149590")


class _BoundaryModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        populate_by_name=True,
        strict=True,
    )


class _TmsObservation(_BoundaryModel):
    cell_id: str
    mouse_id: str = Field(alias="mouse.id")
    method: str
    tissue: str
    cell_ontology_class: str


class _TmsFeature(_BoundaryModel):
    feature_id: str
    feature_name: str


class _CsrCounts(_BoundaryModel):
    format: Literal["csr"]
    data: tuple[NonNegativeInt, ...]
    indices: tuple[NonNegativeInt, ...]
    indptr: tuple[NonNegativeInt, ...]
    shape: tuple[NonNegativeInt, NonNegativeInt]


class _TmsAortaPayload(_BoundaryModel):
    schema_version: Literal["tms-aorta-csr-v1"]
    observations: Annotated[tuple[_TmsObservation, ...], Field(min_length=1)]
    features: Annotated[tuple[_TmsFeature, ...], Field(min_length=1)]
    counts: _CsrCounts


@dataclass(frozen=True, slots=True)
class InvalidTmsSchemaError(Exception):
    """Raised when a local artifact is not the pinned sparse interchange schema."""

    artifact_id: ArtifactId

    @override
    def __str__(self) -> str:
        return f"artifact {self.artifact_id} is not valid TMS Aorta sparse data"


@dataclass(frozen=True, slots=True)
class UnlinkedTmsArtifactError(Exception):
    """Raised when a processed artifact lacks the expected raw-parent edge."""

    artifact_id: ArtifactId
    protocol: TransformProtocolId | None

    @override
    def __str__(self) -> str:
        return (
            f"artifact {self.artifact_id} must be derived with "
            f"{TMS_AORTA_TRANSFORM_PROTOCOL}; received {self.protocol}"
        )


def load_tms_aorta(artifact: ArtifactReceipt) -> CanonicalSingleCellDataset:
    """Map a pinned sparse export into the canonical single-cell contract."""
    derivation = artifact.manifest.derivation
    if derivation is None:
        raise UnlinkedTmsArtifactError(
            artifact_id=artifact.artifact_id,
            protocol=None,
        )
    if derivation.transform_protocol != TMS_AORTA_TRANSFORM_PROTOCOL:
        raise UnlinkedTmsArtifactError(
            artifact_id=artifact.artifact_id,
            protocol=derivation.transform_protocol,
        )

    try:
        payload = _TmsAortaPayload.model_validate_json(
            artifact.content_path.read_text(encoding="utf-8"),
        )
    except (UnicodeDecodeError, ValidationError) as error:
        raise InvalidTmsSchemaError(artifact_id=artifact.artifact_id) from error

    observations = tuple(
        CanonicalObservation(
            cell_id=CellId(item.cell_id),
            donor_id=DonorId(item.mouse_id),
            study_id=_TMS_STUDY_ID,
            assay=item.method,
            tissue=item.tissue,
            cell_type=item.cell_ontology_class,
        )
        for item in payload.observations
    )
    features = tuple(
        CanonicalFeature(
            feature_id=FeatureId(item.feature_id),
            feature_name=item.feature_name,
        )
        for item in payload.features
    )
    counts = SparseCountMatrix(
        format=SparseFormat.CSR,
        shape=MatrixShape(
            observations=payload.counts.shape[0],
            features=payload.counts.shape[1],
        ),
        values=payload.counts.data,
        column_indices=payload.counts.indices,
        row_offsets=payload.counts.indptr,
    )
    identity_input = (
        f"{_TMS_AORTA_SNAPSHOT.name}\0{_TMS_AORTA_SNAPSHOT.version}\0"
        f"{artifact.artifact_id}\0{TMS_AORTA_TRANSFORM_PROTOCOL}"
    )
    identity = DatasetMaterializationId(sha256(identity_input.encode()).hexdigest())
    return CanonicalSingleCellDataset(
        identity=identity,
        snapshot=_TMS_AORTA_SNAPSHOT,
        source=TMS_AORTA_SOURCE,
        artifact=artifact.manifest,
        observations=observations,
        features=features,
        counts=counts,
    )
