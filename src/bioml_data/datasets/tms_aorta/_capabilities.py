"""Split capabilities declared by the TMS Aorta dataset."""

from typing import Final

from bioml_data._domain import SplitProtocolRole
from bioml_data._split_capability_models import (
    SplitCapability,
    SplitEvidenceType,
)
from bioml_data.datasets.tms_aorta._identity import (
    TMS_ANIMAL_HELD_OUT_PROTOCOL,
    TMS_AORTA_SNAPSHOT,
    TMS_CELL_TYPE_TASK,
)

TMS_ANIMAL_HELD_OUT_CAPABILITY: Final = SplitCapability(
    dataset=TMS_AORTA_SNAPSHOT,
    task=TMS_CELL_TYPE_TASK,
    protocol=TMS_ANIMAL_HELD_OUT_PROTOCOL,
    role=SplitProtocolRole.CANARY,
    evidence_type=SplitEvidenceType.PRODUCT_PROTOCOL,
    held_out_axis="animal",
    leakage_unit="mouse",
    required_columns=("cell_id", "donor_id"),
    grouping_column="donor_id",
)
