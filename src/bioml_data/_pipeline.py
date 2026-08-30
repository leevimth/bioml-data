"""Shared end-to-end TMS Aorta product-canary pipeline."""

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from bioml_data._artifacts import ArtifactId, ArtifactReceipt
from bioml_data._catalog import load_dataset
from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId
from bioml_data._evaluation import evaluate, tms_aorta_canary_protocol
from bioml_data._evaluation_models import (
    EvaluationReceiptIdentity,
    EvaluationRequest,
    LabelRecord,
    MetricProtocolIdentity,
)
from bioml_data._evaluation_sanity import FeatureThresholdSanityEstimator
from bioml_data._leakage_audit import audit_split
from bioml_data._leakage_audit_models import (
    AuditStatus,
    LeakageAuditIdentity,
    LeakageAuditRequest,
)
from bioml_data._preparation import (
    FeatureSelectionParameters,
    GeneAlignmentParameters,
    NormalizationParameters,
    PreparationProtocol,
    QcParameters,
    apply_fitted_preprocessing,
    fit_train_preprocessing,
    prepare_train_independent,
)
from bioml_data._preparation_models import (
    PreparationReceiptIdentity,
    PreparedBenchmarkReceipt,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import (
    AssignmentIdentity,
    ObservationId,
    SplitAssigner,
    SplitAssignmentReceipt,
    SplitPartition,
)

_TASK = TaskId("cell-type-annotation-v1")
_EVALUATION_PARTITION = {
    SplitPartition.TRAIN: False,
    SplitPartition.VALIDATION: True,
    SplitPartition.TEST: True,
}


class BenchmarkRunReceipt(BaseModel):
    """Serializable identity chain for one end-to-end canary run."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    dataset: DatasetSnapshotIdentity
    artifact_identity: ArtifactId
    split_protocol_id: ProtocolId
    seed: int
    split_assignment_identity: AssignmentIdentity
    preparation_receipt_identity: PreparationReceiptIdentity
    audit_report_identity: LeakageAuditIdentity
    audit_status: AuditStatus
    metric_protocol_identity: MetricProtocolIdentity
    evaluation_receipt_identity: EvaluationReceiptIdentity
    evaluation_point_estimate: float


def run_tms_aorta_canary(
    artifact: ArtifactReceipt,
    *,
    split_protocol: str | None,
    seed: int,
) -> BenchmarkRunReceipt:
    """Run the small product-canary path through the shared protocol stages."""
    dataset = load_dataset("tms-aorta", artifact=artifact)
    preparation = prepare_train_independent(
        dataset,
        protocol=_preparation_protocol(dataset),
        seed=seed,
    )
    assignment = SplitAssigner(
        dataset=dataset.snapshot,
        task=_TASK,
        observations=dataset.split_observations,
    ).split(protocol=split_protocol, seed=seed)
    fitted = fit_train_preprocessing(preparation, split=assignment)
    prepared = apply_fitted_preprocessing(
        preparation,
        fitted=fitted,
        split=assignment,
    )
    audit = audit_split(LeakageAuditRequest.from_dataset(dataset, assignment))
    evaluation = evaluate(_evaluation_request(dataset, assignment, prepared))
    return BenchmarkRunReceipt(
        dataset=dataset.snapshot,
        artifact_identity=artifact.artifact_id,
        split_protocol_id=assignment.protocol,
        seed=seed,
        split_assignment_identity=assignment.assignment_identity,
        preparation_receipt_identity=prepared.receipt_identity,
        audit_report_identity=audit.report_identity,
        audit_status=audit.status,
        metric_protocol_identity=evaluation.metric_protocol_identity,
        evaluation_receipt_identity=evaluation.receipt_identity,
        evaluation_point_estimate=evaluation.point_estimate,
    )


def _preparation_protocol(
    dataset: CanonicalSingleCellDataset,
) -> PreparationProtocol:
    return PreparationProtocol(
        protocol_id="tms-aorta-canary-preparation",
        version="v1",
        qc=QcParameters(minimum_cell_count=1, minimum_feature_cells=1),
        alignment=GeneAlignmentParameters(
            feature_ids=tuple(feature.feature_id for feature in dataset.features),
        ),
        normalization=NormalizationParameters(target_sum=100.0),
        feature_selection=FeatureSelectionParameters(
            max_features=len(dataset.features),
        ),
    )


def _evaluation_request(
    dataset: CanonicalSingleCellDataset,
    assignment: SplitAssignmentReceipt,
    prepared: PreparedBenchmarkReceipt,
) -> EvaluationRequest:
    evaluation_ids = frozenset(
        item.observation_id
        for item in assignment.assignments
        if _EVALUATION_PARTITION[item.partition]
    )
    evaluation_rows = tuple(
        item for item in prepared.observations if item.observation_id in evaluation_ids
    )
    labels_by_id = {
        ObservationId(item.cell_id): item.cell_type for item in dataset.observations
    }
    labels = tuple(
        LabelRecord(
            observation_id=item.observation_id,
            label=labels_by_id[item.observation_id],
        )
        for item in evaluation_rows
    )
    eligible_labels = tuple(sorted(set(labels_by_id.values())))
    estimator = FeatureThresholdSanityEstimator(
        feature_id=prepared.fitted_state.selected_feature_ids[-1],
        threshold=50.0,
        below_label=eligible_labels[0],
        at_or_above_label=eligible_labels[1],
    )
    return EvaluationRequest(
        predictions=estimator.predict(evaluation_rows),
        labels=labels,
        split=assignment,
        preprocessing=prepared,
        protocol=tms_aorta_canary_protocol(eligible_labels),
    )
