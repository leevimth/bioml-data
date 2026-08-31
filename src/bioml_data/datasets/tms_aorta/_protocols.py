"""Versioned protocol declarations owned by the TMS Aorta canary."""

from typing import Final

from bioml_data._domain import ProtocolId
from bioml_data._evaluation_models import (
    AggregationLevel,
    MetricEvidence,
    MetricName,
    MetricProtocol,
    ResamplingProtocol,
    ResamplingUnit,
    UncertaintyMethod,
)
from bioml_data.datasets.tms_aorta._identity import TMS_CELL_TYPE_TASK

TMS_AORTA_PREPARATION_PROTOCOL_ID: Final = "tms-aorta-canary-preparation"
TMS_AORTA_PREPARATION_VERSION: Final = "v1"
TMS_AORTA_METRIC_PROTOCOL_ID: Final = ProtocolId("tms-aorta-mouse-macro-f1-canary")
TMS_AORTA_METRIC_PROTOCOL_VERSION: Final = "v1"

_RESAMPLING_SEED: Final = 23
_BOOTSTRAP_REPLICATES: Final = 64
_CONFIDENCE_LEVEL: Final = 0.95


def tms_aorta_canary_protocol(
    eligible_labels: tuple[str, ...],
) -> MetricProtocol:
    """Define the product canary; this is not a literature reference protocol."""
    return MetricProtocol(
        protocol_id=TMS_AORTA_METRIC_PROTOCOL_ID,
        version=TMS_AORTA_METRIC_PROTOCOL_VERSION,
        task=TMS_CELL_TYPE_TASK,
        metric=MetricName.MACRO_F1,
        aggregation=AggregationLevel.GROUP,
        evidence=MetricEvidence.PRODUCT_PROTOCOL,
        eligible_labels=eligible_labels,
        resampling=ResamplingProtocol(
            method=UncertaintyMethod.BOOTSTRAP,
            unit=ResamplingUnit.GROUP,
            seed=_RESAMPLING_SEED,
            replicates=_BOOTSTRAP_REPLICATES,
            confidence_level=_CONFIDENCE_LEVEL,
        ),
    )
