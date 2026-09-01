"""Split capabilities declared by the TMS Aorta dataset."""

from typing import Final

from bioml_data._domain import SplitProtocolRole
from bioml_data._split_capability_models import (
    SplitCapability,
    SplitEvidenceCitation,
    SplitEvidenceScope,
    SplitEvidenceType,
    SplitProtocolEvidence,
)
from bioml_data.datasets.tms_aorta._identity import (
    TMS_ANIMAL_HELD_OUT_PROTOCOL,
    TMS_AORTA_ARTIFACT_SCOPE,
    TMS_AORTA_SNAPSHOT,
    TMS_CELL_TYPE_TASK,
)

TMS_ANIMAL_HELD_OUT_EVIDENCE_SCOPE: Final = SplitEvidenceScope(
    dataset=TMS_AORTA_SNAPSHOT,
    artifact=TMS_AORTA_ARTIFACT_SCOPE,
    task=TMS_CELL_TYPE_TASK,
    protocol=TMS_ANIMAL_HELD_OUT_PROTOCOL,
)
TMS_PACKAGE_CONTRACT_CITATION: Final = SplitEvidenceCitation(
    title="TMS Aorta package contract",
    uri="https://github.com/leevimth/bioml-data/blob/main/docs/tms-aorta.md",
)

TMS_ANIMAL_HELD_OUT_CAPABILITY: Final = SplitCapability(
    dataset=TMS_AORTA_SNAPSHOT,
    task=TMS_CELL_TYPE_TASK,
    protocol=TMS_ANIMAL_HELD_OUT_PROTOCOL,
    role=SplitProtocolRole.CANARY,
    evidence_type=SplitEvidenceType.PRODUCT_PROTOCOL,
    artifact=TMS_AORTA_ARTIFACT_SCOPE,
    evidence=(
        SplitProtocolEvidence(
            scope=TMS_ANIMAL_HELD_OUT_EVIDENCE_SCOPE,
            role=SplitProtocolRole.CANARY,
            evidence_type=SplitEvidenceType.PRODUCT_PROTOCOL,
            citations=(TMS_PACKAGE_CONTRACT_CITATION,),
            fit_scope="train-only feature selection",
            leakage_caveat=(
                "Technical lifecycle canary; not a scientific benchmark claim."
            ),
        ),
        SplitProtocolEvidence(
            scope=TMS_ANIMAL_HELD_OUT_EVIDENCE_SCOPE,
            role=SplitProtocolRole.ROBUSTNESS,
            evidence_type=SplitEvidenceType.PRODUCT_PROTOCOL,
            citations=(TMS_PACKAGE_CONTRACT_CITATION,),
            fit_scope="train-only feature selection",
            leakage_caveat=(
                "Package-defined animal-independence check; not literature-recommended."
            ),
        ),
    ),
    held_out_axis="animal",
    leakage_unit="mouse",
    required_columns=("cell_id", "donor_id"),
    grouping_column="donor_id",
)
