"""Split capabilities declared by the TMS Aorta dataset."""

from typing import Final

from bioml_data._artifact_types import ArtifactId
from bioml_data._domain import SplitProtocolRole
from bioml_data._split_capability_models import (
    SplitArtifactScope,
    SplitCapability,
    SplitEvidenceCitation,
    SplitEvidenceScope,
    SplitEvidenceType,
    SplitProtocolEvidence,
)
from bioml_data.datasets.tms_aorta._identity import (
    TMS_ANIMAL_HELD_OUT_PROTOCOL,
    TMS_AORTA_SNAPSHOT,
    TMS_AORTA_TRANSFORM_PROTOCOL,
    TMS_CELL_TYPE_TASK,
)

TMS_AORTA_ARTIFACT_SCOPE: Final = SplitArtifactScope(
    source_artifact=ArtifactId(
        "sha256:0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3"
    ),
    transform_protocol=TMS_AORTA_TRANSFORM_PROTOCOL,
)
TMS_ANIMAL_HELD_OUT_EVIDENCE_SCOPE: Final = SplitEvidenceScope(
    dataset=TMS_AORTA_SNAPSHOT,
    artifact=TMS_AORTA_ARTIFACT_SCOPE,
    task=TMS_CELL_TYPE_TASK,
    protocol=TMS_ANIMAL_HELD_OUT_PROTOCOL,
)
TMS_PACKAGE_CONTRACT_CITATION: Final = SplitEvidenceCitation(
    title="TMS Aorta package contract",
    uri="docs/tms-aorta.md",
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
