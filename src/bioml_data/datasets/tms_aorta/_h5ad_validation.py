"""Resource and count validation for the pinned TMS Aorta H5AD."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, Final, override

import anndata as ad
import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, InstanceOf, ValidationError
from scipy import sparse

from bioml_data._artifacts import ArtifactId, ArtifactReceipt


@unique
class RawTmsViolation(StrEnum):
    """Machine-readable reasons a raw H5AD cannot enter this transform."""

    RAW_LAYER_MISSING = "raw_layer_missing"
    RAW_MATRIX_NOT_CSR = "raw_matrix_not_csr"
    SHAPE_MISMATCH = "shape_mismatch"
    REQUIRED_OBSERVATION_COLUMN = "required_observation_column"
    DUPLICATE_IDENTIFIER = "duplicate_identifier"
    INVALID_METADATA = "invalid_metadata"
    NON_INTEGER_COUNT = "non_integer_count"
    NEGATIVE_COUNT = "negative_count"
    NONFINITE_COUNT = "nonfinite_count"
    RESOURCE_LIMIT = "resource_limit"


@dataclass(frozen=True, slots=True)
class InvalidRawTmsArtifactError(Exception):
    """Raised when a verified H5AD violates the versioned transform input."""

    artifact_id: ArtifactId
    violation: RawTmsViolation
    field: str | None = None

    @override
    def __str__(self) -> str:
        suffix = f" ({self.field})" if self.field is not None else ""
        return f"raw TMS artifact {self.artifact_id}: {self.violation}{suffix}"


@dataclass(frozen=True, slots=True)
class TmsAortaTransformLimits:
    """Pinned resource envelope checked before canonical expansion."""

    observations: int
    features: int
    maximum_nonzero_counts: int
    maximum_metadata_length: int
    maximum_output_bytes: int


class _RawMatrixBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        from_attributes=True,
    )

    matrix: InstanceOf[sparse.csr_matrix[np.float32]] = Field(alias="X")


TMS_AORTA_TRANSFORM_LIMITS: Final = TmsAortaTransformLimits(
    observations=906,
    features=22_966,
    maximum_nonzero_counts=2_000_087,
    maximum_metadata_length=512,
    maximum_output_bytes=32 * 1024 * 1024,
)


def validated_counts(
    raw: ArtifactReceipt,
    raw_layer: ad.Raw,
    limits: TmsAortaTransformLimits,
) -> sparse.csr_matrix[np.float32]:
    """Validate and normalize the bounded raw count matrix."""
    try:
        matrix = _RawMatrixBoundary.model_validate(raw_layer).matrix.copy()
    except ValidationError as error:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.RAW_MATRIX_NOT_CSR,
        ) from error
    if matrix.nnz > limits.maximum_nonzero_counts:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.RESOURCE_LIMIT,
            field="nonzero_counts",
        )
    matrix.sum_duplicates()
    matrix.sort_indices()
    matrix.eliminate_zeros()
    values: npt.NDArray[np.float32] = np.asarray(matrix.data)
    if not np.isfinite(values).all():
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.NONFINITE_COUNT,
        )
    if (values < 0).any():
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.NEGATIVE_COUNT,
        )
    if not np.equal(values, np.floor(values)).all():
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.NON_INTEGER_COUNT,
        )
    return matrix


def validate_text_lengths(
    values: tuple[str, ...],
    *,
    limits: TmsAortaTransformLimits,
    artifact_id: ArtifactId,
) -> None:
    """Reject metadata outside the pinned transform's resource envelope."""
    if any(len(value) > limits.maximum_metadata_length for value in values):
        raise InvalidRawTmsArtifactError(
            artifact_id=artifact_id,
            violation=RawTmsViolation.RESOURCE_LIMIT,
            field="metadata_length",
        )
