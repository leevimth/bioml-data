"""Validated H5AD boundary for the tms-aorta-csr-v1 transform."""

import warnings
from typing import ClassVar, Final

import anndata as ad
import numpy as np
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    InstanceOf,
    TypeAdapter,
    ValidationError,
)
from scipy import sparse

from bioml_data._artifact_receipts import verified_artifact_copy
from bioml_data._artifacts import ArtifactId, ArtifactReceipt
from bioml_data.datasets.tms_aorta._h5ad_validation import (
    TMS_AORTA_TRANSFORM_LIMITS,
    InvalidRawTmsArtifactError,
    RawTmsViolation,
    TmsAortaTransformLimits,
    validate_text_lengths,
    validated_counts,
)
from bioml_data.datasets.tms_aorta._interchange import (
    CsrCountsPayload,
    TmsAortaPayload,
    TmsFeaturePayload,
    TmsObservationPayload,
)

__all__ = [
    "TMS_AORTA_TRANSFORM_LIMITS",
    "InvalidRawTmsArtifactError",
    "RawTmsViolation",
    "TmsAortaTransformLimits",
    "transform_h5ad",
]


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


def transform_h5ad(
    raw: ArtifactReceipt,
    limits: TmsAortaTransformLimits,
) -> TmsAortaPayload:
    """Read and validate one raw H5AD into deterministic payload values."""
    with verified_artifact_copy(raw) as copy_path, warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Moving element from \.uns\['neighbors'\]",
            category=FutureWarning,
        )
        warnings.filterwarnings(
            "ignore",
            message="(?:Observation|Variable) names are not unique.*",
            category=UserWarning,
        )
        dataset = ad.read_h5ad(copy_path)
    try:
        raw_layer = _RawLayerBoundary.model_validate(dataset).raw_layer
    except ValidationError as error:
        raise InvalidRawTmsArtifactError(
            artifact_id=raw.artifact_id,
            violation=RawTmsViolation.RAW_LAYER_MISSING,
        ) from error
    expected_shape = (limits.observations, limits.features)
    if raw_layer.shape != dataset.shape or dataset.shape != expected_shape:
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
    matrix = validated_counts(raw, raw_layer, limits)
    try:
        observations = _observations(dataset, limits, artifact_id=raw.artifact_id)
        features = _features(raw_layer, limits, artifact_id=raw.artifact_id)
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


def _counts_payload(
    matrix: sparse.csr_matrix[np.float32],
) -> CsrCountsPayload:
    values = matrix.data.astype(np.int64)
    indices = matrix.indices.astype(np.int64)
    offsets = matrix.indptr.astype(np.int64)
    return CsrCountsPayload(
        format="csr",
        data=_INT_TUPLE.validate_python(values),
        indices=_INT_TUPLE.validate_python(indices),
        indptr=_INT_TUPLE.validate_python(offsets),
        shape=(matrix.shape[0], matrix.shape[1]),
    )


def _observations(
    dataset: ad.AnnData,
    limits: TmsAortaTransformLimits,
    *,
    artifact_id: ArtifactId,
) -> tuple[TmsObservationPayload, ...]:
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
    validate_text_lengths(
        (
            *cell_ids,
            *source_cell_ids,
            *mouse_ids,
            *methods,
            *tissues,
            *cell_types,
            *(value for value in ontology_ids if value is not None),
        ),
        limits=limits,
        artifact_id=artifact_id,
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


def _features(
    raw_layer: ad.Raw,
    limits: TmsAortaTransformLimits,
    *,
    artifact_id: ArtifactId,
) -> tuple[TmsFeaturePayload, ...]:
    feature_ids = _STRING_TUPLE.validate_python(raw_layer.var_names)
    validate_text_lengths(feature_ids, limits=limits, artifact_id=artifact_id)
    return tuple(
        TmsFeaturePayload(feature_id=feature_id, feature_name=feature_id)
        for feature_id in feature_ids
    )
