"""Tabula Muris Senis FACS Aorta artifact adapter."""

from dataclasses import dataclass
from hashlib import sha256
from typing import override

from pydantic import ValidationError

from bioml_data._artifact_receipts import (
    ArtifactReceiptFailure,
    ArtifactReceiptLoadError,
    load_artifact_receipt,
    verified_artifact_copy,
)
from bioml_data._artifacts import ArtifactId, ArtifactReceipt, TransformProtocolId
from bioml_data._single_cell import (
    CanonicalFeature,
    CanonicalObservation,
    CanonicalSingleCellDataset,
    CellId,
    DatasetMaterializationId,
    DonorId,
    FeatureId,
    MatrixShape,
    SparseCountMatrix,
    SparseFormat,
)
from bioml_data.datasets.tms_aorta._definition import (
    TMS_AORTA_SOURCE,
    TMS_AORTA_STUDY_ID,
)
from bioml_data.datasets.tms_aorta._identity import (
    TMS_AORTA_SNAPSHOT,
    TMS_AORTA_TRANSFORM_PARAMETERS,
    TMS_AORTA_TRANSFORM_PROTOCOL,
)
from bioml_data.datasets.tms_aorta._interchange import TmsAortaPayload


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
    verified = load_artifact_receipt(artifact.manifest_path)
    if verified.artifact_id != artifact.artifact_id:
        raise ArtifactReceiptLoadError(
            manifest_path=artifact.manifest_path,
            reason=ArtifactReceiptFailure.CONTENT_INTEGRITY,
        )
    derivation = verified.manifest.derivation
    if derivation is None:
        raise UnlinkedTmsArtifactError(
            artifact_id=verified.artifact_id,
            protocol=None,
        )
    if (
        derivation.transform_protocol != TMS_AORTA_TRANSFORM_PROTOCOL
        or derivation.parameters != TMS_AORTA_TRANSFORM_PARAMETERS
    ):
        raise UnlinkedTmsArtifactError(
            artifact_id=verified.artifact_id,
            protocol=derivation.transform_protocol,
        )

    try:
        with verified_artifact_copy(verified) as copy_path:
            payload = TmsAortaPayload.model_validate_json(
                copy_path.read_text(encoding="utf-8"),
            )
    except (UnicodeDecodeError, ValidationError) as error:
        raise InvalidTmsSchemaError(artifact_id=verified.artifact_id) from error

    observations = tuple(
        CanonicalObservation(
            cell_id=CellId(item.cell_id),
            donor_id=DonorId(item.mouse_id),
            study_id=TMS_AORTA_STUDY_ID,
            assay=item.assay,
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
        f"{TMS_AORTA_SNAPSHOT.name}\0{TMS_AORTA_SNAPSHOT.version}\0"
        f"{verified.artifact_id}\0{TMS_AORTA_TRANSFORM_PROTOCOL}"
    )
    identity = DatasetMaterializationId(sha256(identity_input.encode()).hexdigest())
    return CanonicalSingleCellDataset(
        identity=identity,
        snapshot=TMS_AORTA_SNAPSHOT,
        source=TMS_AORTA_SOURCE,
        artifact=verified.manifest,
        observations=observations,
        features=features,
        counts=counts,
    )
