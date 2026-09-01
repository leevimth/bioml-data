"""Versioned TMS Aorta canonical interchange boundary."""

from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt


class _BoundaryModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True,
        populate_by_name=True,
        strict=True,
    )


class TmsObservationPayload(_BoundaryModel):
    """Canonical fields plus preserved source metadata for one cell."""

    cell_id: str
    source_cell_id: str | None = None
    mouse_id: str = Field(alias="mouse.id")
    method: str
    assay: str | None = None
    tissue: str
    cell_ontology_class: str
    cell_ontology_id: str | None = None


class TmsFeaturePayload(_BoundaryModel):
    """Stable feature identity and display name."""

    feature_id: str
    feature_name: str


class CsrCountsPayload(_BoundaryModel):
    """Integer-valued CSR count arrays."""

    format: Literal["csr"]
    data: tuple[NonNegativeInt, ...]
    indices: tuple[NonNegativeInt, ...]
    indptr: tuple[NonNegativeInt, ...]
    shape: tuple[NonNegativeInt, NonNegativeInt]


class TmsAortaPayload(_BoundaryModel):
    """Complete versioned canonical artifact payload."""

    schema_version: Literal["tms-aorta-csr-v1"]
    observations: Annotated[tuple[TmsObservationPayload, ...], Field(min_length=1)]
    features: Annotated[tuple[TmsFeaturePayload, ...], Field(min_length=1)]
    counts: CsrCountsPayload
