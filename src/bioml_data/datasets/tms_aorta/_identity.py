"""Low-dependency identities shared by the TMS Aorta vertical slice."""

from typing import Final

from bioml_data._artifacts import ArtifactDerivationParameter, TransformProtocolId
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    TaskId,
)

TMS_AORTA_SNAPSHOT: Final = DatasetSnapshotIdentity(
    name=DatasetName("tms-aorta"),
    version=DatasetVersion("figshare-project-64982"),
)
TMS_CELL_TYPE_TASK: Final = TaskId("cell-type-annotation-v1")
TMS_ANIMAL_HELD_OUT_PROTOCOL: Final = ProtocolId("animal-held-out-v1")
TMS_AORTA_TRANSFORM_PROTOCOL: Final = TransformProtocolId("tms-aorta-csr-v1")
TMS_AORTA_TRANSFORM_PARAMETERS: Final = (
    ArtifactDerivationParameter(name="expression_input", value="raw.X"),
)
