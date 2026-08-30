"""Task-bound classification evaluation with provenance receipts."""

from hashlib import sha256

from bioml_data._domain import ProtocolId, TaskId
from bioml_data._evaluation_metrics import (
    bootstrap_uncertainty,
    group_median,
    summarize,
    summarize_groups,
)
from bioml_data._evaluation_models import (
    AggregationLevel,
    EvaluationReceipt,
    EvaluationReceiptIdentity,
    EvaluationRequest,
    LabelRecord,
    MetricEvidence,
    MetricName,
    MetricProtocol,
    PredictionRecord,
    ResamplingProtocol,
    ResamplingUnit,
    UncertaintyMethod,
)
from bioml_data._evaluation_validation import validate

_TMS_CANARY_RESAMPLING_SEED = 23
_TMS_CANARY_BOOTSTRAP_REPLICATES = 64
_TMS_CANARY_CONFIDENCE_LEVEL = 0.95


def tms_aorta_canary_protocol(
    eligible_labels: tuple[str, ...],
) -> MetricProtocol:
    """Define the product canary; this is not a literature reference protocol."""
    return MetricProtocol(
        protocol_id=ProtocolId("tms-aorta-mouse-macro-f1-canary"),
        version="v1",
        task=TaskId("cell-type-annotation-v1"),
        metric=MetricName.MACRO_F1,
        aggregation=AggregationLevel.GROUP,
        evidence=MetricEvidence.PRODUCT_PROTOCOL,
        eligible_labels=eligible_labels,
        resampling=ResamplingProtocol(
            method=UncertaintyMethod.BOOTSTRAP,
            unit=ResamplingUnit.GROUP,
            seed=_TMS_CANARY_RESAMPLING_SEED,
            replicates=_TMS_CANARY_BOOTSTRAP_REPLICATES,
            confidence_level=_TMS_CANARY_CONFIDENCE_LEVEL,
        ),
    )


def evaluate(request: EvaluationRequest) -> EvaluationReceipt:
    """Validate and evaluate predictions under their declared task protocol."""
    validated = validate(request)
    predictions = tuple(
        request.predictions[index] for index in validated.prediction_order
    )
    labels = tuple(request.labels[index] for index in validated.label_order)
    summary = summarize(validated.pairs, request.protocol.eligible_labels)
    groups = (
        summarize_groups(validated.pairs, request.protocol.eligible_labels)
        if request.protocol.aggregation is AggregationLevel.GROUP
        else ()
    )
    point_estimate = (
        sum(item.macro_f1 for item in groups) / len(groups)
        if groups
        else summary.macro_f1
    )
    uncertainty = bootstrap_uncertainty(
        validated.pairs,
        groups,
        request.protocol,
    )
    receipt_identity = _receipt_identity(request, predictions, labels)
    return EvaluationReceipt(
        receipt_identity=receipt_identity,
        dataset=request.split.dataset,
        task=request.split.task,
        predictions=predictions,
        labels=labels,
        split_assignment_identity=request.split.assignment_identity,
        preprocessing_receipt_identity=request.preprocessing.receipt_identity,
        metric_protocol_identity=request.protocol.identity,
        metric_protocol_id=request.protocol.protocol_id,
        metric=request.protocol.metric,
        aggregation=request.protocol.aggregation,
        point_estimate=point_estimate,
        overall_macro_f1=summary.macro_f1,
        micro_f1=summary.micro_f1,
        accuracy=summary.accuracy,
        group_median=group_median(groups) if groups else None,
        per_class=summary.per_class,
        per_group=groups,
        uncertainty=uncertainty,
    )


def _receipt_identity(
    request: EvaluationRequest,
    predictions: tuple[PredictionRecord, ...],
    labels: tuple[LabelRecord, ...],
) -> EvaluationReceiptIdentity:
    prediction_rows = tuple(
        f"{item.observation_id}\0{item.label}" for item in predictions
    )
    label_rows = tuple(f"{item.observation_id}\0{item.label}" for item in labels)
    fields = (
        request.split.assignment_identity,
        request.preprocessing.receipt_identity,
        request.protocol.identity,
        *prediction_rows,
        *label_rows,
    )
    return EvaluationReceiptIdentity(sha256("\0".join(fields).encode()).hexdigest())
