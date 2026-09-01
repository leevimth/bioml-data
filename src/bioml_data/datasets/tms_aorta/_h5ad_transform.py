"""Validated H5AD boundary for the tms-aorta-csr-v1 transform."""

import warnings
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, Final, override

import anndata as ad
import numpy as np
import numpy.typing as npt
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    InstanceOf,
    TypeAdapter,
    ValidationError,
)
from scipy import sparse

from bioml_data._artifacts import ArtifactId, ArtifactReceipt
from bioml_data.datasets.tms_aorta._interchange import (
    CsrCountsPayload,
    TmsAortaPayload,
    TmsFeaturePayload,
    TmsObservationPayload,
)


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


class _RawMatrixBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        from_attributes=True,
    )

    matrix: InstanceOf[sparse.csr_matrix[np.float32]] = Field(alias="X")


class _RawLayerBoundary(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        from_attributes=True,
    )

    raw_layer: InstanceOf[ad.Raw] = Field(alias="raw")


_REQUIRED_OBS_COLUMNS = (
    "cell",
    "mouse.id",
    "method",
    "tissue",
    "cell_ontology_class",
)
_STRING_TUPLE: Final[TypeAdapter[tuple[str, ...]]] = TypeAdapter(tuple[str, ...])
_INT_TUPLE: Final[TypeAdapter[tuple[int, ...]]] = TypeAdapter(tuple[int, ...])


def transform_h5ad(raw: ArtifactReceipt) -> TmsAortaPayload:
    """Read and validate one raw H5AD into deterministic payload values."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Moving element from \.uns\['neighbors'\]",
            category=FutureWarning,
        )
        dataset = ad.read_h5ad(raw.content_path)
    try:
        raw_layer = _RawLayerBoundary.model_validate(dataset).raw_layer
    except ValidationError as error:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.RAW_LAYER_MISSING,
        ) from error
    if raw_layer.shape != dataset.shape:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.SHAPE_MISMATCH,
        )
    for column in _REQUIRED_OBS_COLUMNS:
        if column not in dataset.obs:
            raise InvalidRawTmsArtifactError(
                artifact_id=raw.artifact_id,
                violation=RawTmsViolation.REQUIRED_OBSERVATION_COLUMN,
                field=column,
            )
    if not dataset.obs_names.is_unique or not raw_layer.var_names.is_unique:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.DUPLICATE_IDENTIFIER,
        )
    matrix = _validated_counts(raw, raw_layer)
    try:
        observations = _observations(dataset)
        features = _features(raw_layer)
    except ValidationError as error:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.INVALID_METADATA,
        ) from error
    return TmsAortaPayload(
        schema_version="tms-aorta-csr-v1",
        observations=observations,
        features=features,
        counts=_counts_payload(matrix),
    )


def _validated_counts(
    raw: ArtifactReceipt,
    raw_layer: ad.Raw,
) -> sparse.csr_matrix[np.float32]:
    try:
        matrix = _RawMatrixBoundary.model_validate(raw_layer).matrix.copy()
    except ValidationError as error:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.RAW_MATRIX_NOT_CSR,
        ) from error
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


def _counts_payload(
    matrix: sparse.csr_matrix[np.float32],
) -> CsrCountsPayload:
    values: npt.NDArray[np.int64] = matrix.data.astype(np.int64)
    indices: npt.NDArray[np.int64] = matrix.indices.astype(np.int64)
    offsets: npt.NDArray[np.int64] = matrix.indptr.astype(np.int64)
    return CsrCountsPayload(
        format="csr",
        data=_INT_TUPLE.validate_python(values),
        indices=_INT_TUPLE.validate_python(indices),
        indptr=_INT_TUPLE.validate_python(offsets),
        shape=(matrix.shape[0], matrix.shape[1]),
    )


def _observations(dataset: ad.AnnData) -> tuple[TmsObservationPayload, ...]:
    cell_ids = _STRING_TUPLE.validate_python(dataset.obs_names)
    source_cell_ids = _STRING_TUPLE.validate_python(dataset.obs["cell"])
    mouse_ids = _STRING_TUPLE.validate_python(dataset.obs["mouse.id"])
    methods = _STRING_TUPLE.validate_python(dataset.obs["method"])
    tissues = _STRING_TUPLE.validate_python(dataset.obs["tissue"])
    cell_types = _STRING_TUPLE.validate_python(
        dataset.obs["cell_ontology_class"],
    )
    ontology_ids: tuple[str | None, ...] = (
        _STRING_TUPLE.validate_python(dataset.obs["cell_ontology_id"])
        if "cell_ontology_id" in dataset.obs
        else (None,) * dataset.n_obs
    )
    return tuple(
        TmsObservationPayload(
            cell_id=cell_ids[position],
            source_cell_id=source_cell_ids[position],
            **{"mouse.id": mouse_ids[position]},
            method=methods[position],
            assay=None,
            tissue=tissues[position],
            cell_ontology_class=cell_types[position],
            cell_ontology_id=ontology_ids[position],
        )
        for position in range(dataset.n_obs)
    )


def _features(raw_layer: ad.Raw) -> tuple[TmsFeaturePayload, ...]:
    feature_ids = _STRING_TUPLE.validate_python(raw_layer.var_names)
    return tuple(
        TmsFeaturePayload(feature_id=feature_id, feature_name=feature_id)
        for feature_id in feature_ids
    )
