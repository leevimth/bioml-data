"""Dataset declaration for the published pancreas LODO reference."""

from typing import Final

from bioml_data._dataset_definition import DatasetDefinition
from bioml_data._domain import (
    DatasetLifecycle,
    SourceReference,
    SourceUri,
    SplitEvidenceBasis,
    SplitProtocolDefinition,
    SplitStrategy,
    TaskDefinition,
)
from bioml_data.datasets.pancreas._identity import (
    PANCREAS_CELL_TYPE_TASK,
    PANCREAS_LODO_PROTOCOL,
    PANCREAS_SNAPSHOT,
)

PANCREAS_DEFINITION: Final = DatasetDefinition(
    snapshot=PANCREAS_SNAPSHOT,
    source=SourceReference(uri=SourceUri("https://zenodo.org/records/3357167")),
    lifecycle=DatasetLifecycle.SUPPORTED,
    tasks=(
        TaskDefinition(
            id=PANCREAS_CELL_TYPE_TASK,
            prediction_unit="cell",
            target="cell_type",
        ),
    ),
    supported_splits=(
        SplitProtocolDefinition(
            id=PANCREAS_LODO_PROTOCOL,
            role=None,
            task=PANCREAS_CELL_TYPE_TASK,
            required_metadata=("cell_id", "study_id"),
            basis=SplitEvidenceBasis.LITERATURE_REFERENCE,
            strategy=SplitStrategy.LEAVE_ONE_STUDY_OUT,
            held_out_axis="study",
            leakage_unit="study",
            grouping_column="study_id",
            evaluation_target="unseen study",
            is_canary=False,
        ),
    ),
)
