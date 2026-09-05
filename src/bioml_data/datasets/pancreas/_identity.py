"""Stable identities for the four-study pancreas reference artifact."""

from typing import Final

from bioml_data._artifact_derivation import ArtifactDerivationParameter
from bioml_data._artifact_types import ArtifactId, TransformProtocolId
from bioml_data._artifacts import ArtifactDerivation
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    TaskId,
)
from bioml_data._split_capability_models import SplitArtifactScope

PANCREAS_SNAPSHOT: Final = DatasetSnapshotIdentity(
    name=DatasetName("pancreas-four-study"),
    version=DatasetVersion("zenodo-3357167"),
)
PANCREAS_CELL_TYPE_TASK: Final = TaskId("cross-study-cell-type-annotation-v1")
PANCREAS_LODO_PROTOCOL: Final = ProtocolId("pancreas-four-study-lodo-reference-v1")
PANCREAS_TRANSFORM_PROTOCOL: Final = TransformProtocolId("pancreas-four-study-csr-v1")
PANCREAS_SOURCE_SHA256: Final = (
    "038d0a61ed3891c3d5f4ebd1dab5956465223e38b89859e1bf4792a9aeffbf06"
)
PANCREAS_SOURCE_ARTIFACT: Final = ArtifactId(f"sha256:{PANCREAS_SOURCE_SHA256}")
PANCREAS_TRANSFORM_PARAMETERS: Final = (
    ArtifactDerivationParameter(
        name="eligible_labels",
        value="alpha,beta,delta,gamma",
    ),
    ArtifactDerivationParameter(
        name="muraro_label_normalization",
        value="pp->gamma",
    ),
    ArtifactDerivationParameter(
        name="feature_alignment",
        value="source-provided-combined-raw-counts-v1",
    ),
)
PANCREAS_CANONICAL_DERIVATION: Final = ArtifactDerivation(
    parent_artifacts=(PANCREAS_SOURCE_ARTIFACT,),
    transform_protocol=PANCREAS_TRANSFORM_PROTOCOL,
    parameters=PANCREAS_TRANSFORM_PARAMETERS,
)
PANCREAS_ARTIFACT_SCOPE: Final = SplitArtifactScope(
    source_artifact=PANCREAS_SOURCE_ARTIFACT,
    transform_protocol=PANCREAS_TRANSFORM_PROTOCOL,
)
