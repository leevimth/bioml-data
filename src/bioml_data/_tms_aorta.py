"""Compatibility facade for the TMS Aorta dataset vertical slice."""

from bioml_data.datasets.tms_aorta._adapter import (
    InvalidTmsSchemaError,
    UnlinkedTmsArtifactError,
    load_tms_aorta,
)
from bioml_data.datasets.tms_aorta._definition import TMS_AORTA_SOURCE
from bioml_data.datasets.tms_aorta._identity import (
    TMS_AORTA_TRANSFORM_PROTOCOL,
)

__all__ = [
    "TMS_AORTA_SOURCE",
    "TMS_AORTA_TRANSFORM_PROTOCOL",
    "InvalidTmsSchemaError",
    "UnlinkedTmsArtifactError",
    "load_tms_aorta",
]
