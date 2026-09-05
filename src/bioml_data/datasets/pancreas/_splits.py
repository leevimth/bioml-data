"""Explicit literature-reference leave-one-study-out pancreas partitions."""

from dataclasses import replace
from typing import Final, final, override

from bioml_data._assignment_receipt_identity import (
    AssignmentReceiptIdentityFields,
    canonical_assignment_receipt_identity,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import (
    AssignmentIdentity,
    GroupId,
    ObservationId,
    PartitionFractions,
    PartitionGroupCounts,
    SplitAssignment,
    SplitAssignmentReceipt,
    SplitPartition,
)
from bioml_data.datasets.pancreas._identity import (
    PANCREAS_CELL_TYPE_TASK,
    PANCREAS_LODO_PROTOCOL,
    PANCREAS_SNAPSHOT,
)

PANCREAS_LODO_STUDIES: Final = (
    "Baron Human",
    "Muraro",
    "Segerstolpe",
    "Xin",
)


def pancreas_lodo_split(
    dataset: CanonicalSingleCellDataset,
    *,
    held_out_study: str,
) -> SplitAssignmentReceipt:
    """Create one explicit no-validation fold for a named held-out source study."""
    if dataset.snapshot != PANCREAS_SNAPSHOT:
        raise UnknownPancreasStudyError(study=held_out_study)
    if held_out_study not in PANCREAS_LODO_STUDIES:
        raise UnknownPancreasStudyError(study=held_out_study)
    assignments = tuple(
        SplitAssignment(
            observation_id=ObservationId(item.cell_id),
            group=GroupId(item.study_id),
            partition=(
                SplitPartition.TEST
                if item.study_id == held_out_study
                else SplitPartition.TRAIN
            ),
        )
        for item in dataset.observations
    )
    receipt = SplitAssignmentReceipt(
        dataset=PANCREAS_SNAPSHOT,
        task=PANCREAS_CELL_TYPE_TASK,
        protocol=PANCREAS_LODO_PROTOCOL,
        seed=0,
        assignment_identity=AssignmentIdentity(""),
        assignments=assignments,
        requested_group_fractions=PartitionFractions(
            train=0.75,
            validation=0.0,
            test=0.25,
        ),
        realized_group_counts=PartitionGroupCounts(train=3, validation=0, test=1),
        observation_count=len(assignments),
        group_count=4,
    )
    return replace(receipt, assignment_identity=_identity(receipt))


def _identity(receipt: SplitAssignmentReceipt) -> AssignmentIdentity:
    return AssignmentIdentity(
        canonical_assignment_receipt_identity(
            AssignmentReceiptIdentityFields(
                dataset_name=str(receipt.dataset.name),
                dataset_version=str(receipt.dataset.version),
                task=str(receipt.task),
                protocol=str(receipt.protocol),
                seed=receipt.seed,
                assignments=tuple(
                    (str(item.observation_id), str(item.group), str(item.partition))
                    for item in receipt.assignments
                ),
                requested_group_fractions=(0.75, 0.0, 0.25),
                realized_group_counts=(3, 0, 1),
                observation_count=receipt.observation_count,
                group_count=4,
            )
        )
    )


@final
class UnknownPancreasStudyError(ValueError):
    """Raised when callers do not select one of the four published studies."""

    study: str

    def __init__(self, *, study: str) -> None:
        super().__init__(study)
        self.study = study

    @override
    def __str__(self) -> str:
        return f"unknown pancreas held-out study {self.study!r}"
