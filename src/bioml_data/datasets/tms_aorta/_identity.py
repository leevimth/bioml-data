"""Low-dependency identities shared by the TMS Aorta vertical slice."""

from typing import Final

from bioml_data._artifact_types import ArtifactId, TransformProtocolId
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    TaskId,
)
from bioml_data._split_capability_models import SplitArtifactScope

TMS_AORTA_SNAPSHOT: Final = DatasetSnapshotIdentity(
    name=DatasetName("tms-aorta"),
    version=DatasetVersion("figshare-project-64982"),
)
TMS_CELL_TYPE_TASK: Final = TaskId("cell-type-annotation-v1")
TMS_ANIMAL_HELD_OUT_PROTOCOL: Final = ProtocolId("animal-held-out-v1")
TMS_AORTA_TRANSFORM_PROTOCOL: Final = TransformProtocolId("tms-aorta-csr-v1")
TMS_AORTA_SOURCE_SHA256: Final = (
    "0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3"
)
TMS_AORTA_SOURCE_ARTIFACT: Final = ArtifactId(f"sha256:{TMS_AORTA_SOURCE_SHA256}")
TMS_AORTA_ARTIFACT_SCOPE: Final = SplitArtifactScope(
    source_artifact=TMS_AORTA_SOURCE_ARTIFACT,
    transform_protocol=TMS_AORTA_TRANSFORM_PROTOCOL,
)
