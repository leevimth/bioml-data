"""Split evidence for the published pancreas leave-one-study-out benchmark."""

from typing import Final

from bioml_data._domain import SplitEvidenceBasis, SplitStrategy
from bioml_data._split_capability_models import (
    SplitCapability,
    SplitEvidenceCitation,
    SplitEvidenceScope,
    SplitProtocolEvidence,
)
from bioml_data.datasets.pancreas._identity import (
    PANCREAS_ARTIFACT_SCOPE,
    PANCREAS_CELL_TYPE_TASK,
    PANCREAS_LODO_PROTOCOL,
    PANCREAS_SNAPSHOT,
)

_SCOPE: Final = SplitEvidenceScope(
    dataset=PANCREAS_SNAPSHOT,
    artifact=PANCREAS_ARTIFACT_SCOPE,
    task=PANCREAS_CELL_TYPE_TASK,
    protocol=PANCREAS_LODO_PROTOCOL,
)
_CITATION: Final = SplitEvidenceCitation(
    title="Abdelaal et al. (2019) pancreas cross-study benchmark",
    uri="https://link.springer.com/article/10.1186/s13059-019-1795-z",
)
PANCREAS_LODO_CAPABILITY: Final = SplitCapability(
    dataset=PANCREAS_SNAPSHOT,
    task=PANCREAS_CELL_TYPE_TASK,
    protocol=PANCREAS_LODO_PROTOCOL,
    role=None,
    evidence_type=None,
    artifact=PANCREAS_ARTIFACT_SCOPE,
    evidence=(
        SplitProtocolEvidence(
            scope=_SCOPE,
            role=None,
            evidence_type=None,
            citations=(_CITATION,),
            fit_scope="not reported by the literature reference",
            leakage_caveat=(
                "Historical cross-study reference; not a package claim about "
                "modern train-only preprocessing."
            ),
            basis=SplitEvidenceBasis.LITERATURE_REFERENCE,
        ),
    ),
    held_out_axis="study",
    leakage_unit="study",
    required_columns=("cell_id", "study_id"),
    grouping_column="study_id",
    basis=SplitEvidenceBasis.LITERATURE_REFERENCE,
    strategy=SplitStrategy.LEAVE_ONE_STUDY_OUT,
    evaluation_target="unseen study",
    is_canary=False,
)
