"""Shared fixtures for evaluation contract tests."""

from dataclasses import replace

from bioml_data import _preparation as preparation
from bioml_data._evaluation import tms_aorta_canary_protocol
from bioml_data._evaluation_models import (
    EvaluationRequest,
    LabelRecord,
    MetricProtocol,
    PredictionRecord,
)
from bioml_data._preparation_models import PreparedBenchmarkReceipt
from bioml_data._single_cell import FeatureId
from bioml_data._split import (
    AssignmentIdentity,
    GroupId,
    ObservationId,
    PartitionGroupCounts,
    SplitAssignment,
    SplitAssignmentReceipt,
    SplitPartition,
)
from tests._single_cell_fixtures import make_dataset, make_split


def make_evaluation_split() -> SplitAssignmentReceipt:
    """Return three held-out animals spanning all fixture labels."""
    base = make_split(make_dataset())
    partitions = {
        "cell-1": ("mouse-a", SplitPartition.TEST),
        "cell-2": ("mouse-a", SplitPartition.TEST),
        "cell-3": ("mouse-b", SplitPartition.TEST),
        "cell-4": ("mouse-c", SplitPartition.VALIDATION),
        "cell-5": ("mouse-d", SplitPartition.TEST),
        "cell-6": ("mouse-e", SplitPartition.TRAIN),
    }
    assignments = tuple(
        SplitAssignment(
            observation_id=ObservationId(cell_id),
            group=GroupId(group),
            partition=partition,
        )
        for cell_id, (group, partition) in partitions.items()
    )
    return replace(
        base,
        assignment_identity=AssignmentIdentity("evaluation-split"),
        assignments=assignments,
        realized_group_counts=PartitionGroupCounts(train=1, validation=1, test=3),
    )


def make_prepared(split: SplitAssignmentReceipt) -> PreparedBenchmarkReceipt:
    """Prepare canonical sparse fixture rows against the supplied split."""
    protocol = preparation.PreparationProtocol(
        protocol_id="single-cell-canary-preparation",
        version="v1",
        qc=preparation.QcParameters(
            minimum_cell_count=1,
            minimum_feature_cells=1,
        ),
        alignment=preparation.GeneAlignmentParameters(
            feature_ids=(FeatureId("gene-1"), FeatureId("gene-2"), FeatureId("gene-3")),
        ),
        normalization=preparation.NormalizationParameters(target_sum=100.0),
        feature_selection=None,
    )
    return preparation.prepare_benchmark(
        preparation.PreparationRequest(
            dataset=make_dataset(),
            protocol=protocol,
            split=split,
            seed=17,
        )
    )


def make_metric_protocol() -> MetricProtocol:
    """Return the frozen TMS product-canary protocol for fixture labels."""
    return tms_aorta_canary_protocol(
        ("endothelial", "fibroblast", "smooth-muscle", "immune")
    )


def make_predictions() -> tuple[PredictionRecord, ...]:
    """Return indexed non-degenerate canary predictions."""
    return (
        PredictionRecord(observation_id=ObservationId("cell-1"), label="endothelial"),
        PredictionRecord(observation_id=ObservationId("cell-2"), label="fibroblast"),
        PredictionRecord(observation_id=ObservationId("cell-3"), label="fibroblast"),
        PredictionRecord(observation_id=ObservationId("cell-5"), label="smooth-muscle"),
    )


def make_labels() -> tuple[LabelRecord, ...]:
    """Return indexed held-out fixture labels."""
    return (
        LabelRecord(observation_id=ObservationId("cell-1"), label="endothelial"),
        LabelRecord(observation_id=ObservationId("cell-2"), label="endothelial"),
        LabelRecord(observation_id=ObservationId("cell-3"), label="fibroblast"),
        LabelRecord(observation_id=ObservationId("cell-5"), label="smooth-muscle"),
    )


def make_evaluation_request() -> EvaluationRequest:
    """Return a fully provenance-bound evaluation invocation."""
    split = make_evaluation_split()
    return EvaluationRequest(
        predictions=make_predictions(),
        labels=make_labels(),
        split=split,
        preprocessing=make_prepared(split),
        protocol=make_metric_protocol(),
    )
