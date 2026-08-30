"""Task-bound evaluation and provenance receipt tests."""

from dataclasses import replace

import pytest

from bioml_data._domain import TaskId
from bioml_data._evaluation import evaluate
from bioml_data._evaluation_errors import (
    DegenerateLabelsError,
    DegeneratePredictionsError,
    EvaluationIndexError,
    EvaluationPartitionError,
    EvaluationProvenanceError,
    EvaluationShapeError,
    MetricProtocolError,
    MissingEvaluationGroupError,
)
from bioml_data._evaluation_models import (
    AggregationLevel,
    EvaluationReceipt,
    LabelRecord,
    MetricEvidence,
    MetricName,
    PredictionRecord,
    ResamplingProtocol,
    ResamplingUnit,
    UncertaintyMethod,
)
from bioml_data._evaluation_sanity import FeatureThresholdSanityEstimator
from bioml_data._single_cell import FeatureId
from bioml_data._split import ObservationId
from tests._evaluation_fixtures import make_evaluation_request as _request
from tests._evaluation_fixtures import make_labels as _labels
from tests._evaluation_fixtures import make_metric_protocol as _protocol
from tests._evaluation_fixtures import make_predictions as _predictions


def test_tms_metric_is_explicit_product_canary() -> None:
    protocol = _protocol()

    assert protocol.evidence is MetricEvidence.PRODUCT_PROTOCOL
    assert protocol.metric is MetricName.MACRO_F1
    assert protocol.aggregation is AggregationLevel.GROUP
    assert protocol.resampling.unit is ResamplingUnit.GROUP
    assert protocol.identity == _protocol().identity


def test_same_inputs_and_protocol_produce_same_complete_receipt() -> None:
    first = evaluate(_request())
    second = evaluate(_request())

    assert first == second
    assert first.receipt_identity == second.receipt_identity
    assert first.predictions == _predictions()
    assert first.labels == _labels()
    assert first.split_assignment_identity == "evaluation-split"
    assert (
        first.preprocessing_receipt_identity
        == _request().preprocessing.receipt_identity
    )
    assert first.metric_protocol_identity == _protocol().identity
    assert first.point_estimate == pytest.approx(8 / 9)
    assert first.accuracy == pytest.approx(3 / 4)
    assert first.micro_f1 == pytest.approx(3 / 4)
    assert first.group_median == pytest.approx(1.0)
    assert first.uncertainty.seed == 23
    assert first.uncertainty.unit is ResamplingUnit.GROUP
    assert first.uncertainty.replicates == 64
    immune = next(score for score in first.per_class if score.label == "immune")
    assert immune.support == 0
    assert not immune.estimable
    assert immune.f1 is None


def test_receipt_round_trips_through_json() -> None:
    receipt = evaluate(_request())

    restored = EvaluationReceipt.model_validate_json(receipt.model_dump_json())

    assert restored == receipt


@pytest.mark.parametrize(
    ("aggregation", "unit"),
    [
        (AggregationLevel.CELL, ResamplingUnit.CELL),
        (AggregationLevel.SAMPLE, ResamplingUnit.SAMPLE),
    ],
)
def test_cell_and_sample_aggregation_are_explicit(
    aggregation: AggregationLevel,
    unit: ResamplingUnit,
) -> None:
    protocol = _protocol().model_copy(
        update={
            "aggregation": aggregation,
            "resampling": _protocol().resampling.model_copy(update={"unit": unit}),
        }
    )

    receipt = evaluate(replace(_request(), protocol=protocol))

    assert receipt.aggregation is aggregation
    assert receipt.point_estimate == pytest.approx(7 / 9)
    assert receipt.uncertainty.unit is unit
    assert receipt.per_group == ()


def test_shape_failure_precedes_metric_evaluation() -> None:
    request = replace(_request(), labels=_labels()[:-1])

    with pytest.raises(EvaluationShapeError):
        _ = evaluate(request)


def test_train_partition_observations_cannot_be_evaluated() -> None:
    # Given: aligned predictions and labels containing one training observation.
    predictions = (
        *_predictions()[:-1],
        PredictionRecord(
            observation_id=ObservationId("cell-6"),
            label="smooth-muscle",
        ),
    )
    labels = (
        *_labels()[:-1],
        LabelRecord(
            observation_id=ObservationId("cell-6"),
            label="smooth-muscle",
        ),
    )

    # When: public evaluation validates the requested observation partition.
    with pytest.raises(EvaluationPartitionError) as captured:
        _ = evaluate(replace(_request(), predictions=predictions, labels=labels))

    # Then: the typed failure reports exactly the forbidden training observation.
    assert captured.value.training_observation_ids == (ObservationId("cell-6"),)


@pytest.mark.parametrize(
    ("predictions", "labels"),
    [
        ((*_predictions()[:-1], _predictions()[0]), _labels()),
        (
            _predictions(),
            (
                *_labels()[:-1],
                LabelRecord(
                    observation_id=ObservationId("cell-4"),
                    label="smooth-muscle",
                ),
            ),
        ),
    ],
)
def test_duplicate_or_misaligned_indices_fail(
    predictions: tuple[PredictionRecord, ...],
    labels: tuple[LabelRecord, ...],
) -> None:
    with pytest.raises(EvaluationIndexError):
        _ = evaluate(replace(_request(), predictions=predictions, labels=labels))


@pytest.mark.parametrize(
    ("aggregation", "unit"),
    [
        (AggregationLevel.CELL, ResamplingUnit.CELL),
        (AggregationLevel.SAMPLE, ResamplingUnit.SAMPLE),
    ],
)
def test_cell_and_sample_evaluation_require_split_assignments(
    aggregation: AggregationLevel,
    unit: ResamplingUnit,
) -> None:
    # Given: aligned inputs with one observation absent from the split receipt.
    request = _request()
    split = replace(
        request.split,
        assignments=tuple(
            assignment
            for assignment in request.split.assignments
            if assignment.observation_id != ObservationId("cell-5")
        ),
    )
    protocol = request.protocol.model_copy(
        update={
            "aggregation": aggregation,
            "resampling": request.protocol.resampling.model_copy(update={"unit": unit}),
        }
    )

    # When: evaluation validates split membership before calculating metrics.
    with pytest.raises(EvaluationIndexError) as captured:
        _ = evaluate(replace(request, split=split, protocol=protocol))

    # Then: the typed index failure identifies the unassigned observation.
    assert captured.value.missing_split_assignments == (ObservationId("cell-5"),)


def test_degenerate_labels_and_predictions_are_typed() -> None:
    labels = tuple(
        item.model_copy(update={"label": "endothelial"}) for item in _labels()
    )
    with pytest.raises(DegenerateLabelsError):
        _ = evaluate(replace(_request(), labels=labels))

    predictions = tuple(
        item.model_copy(update={"label": "endothelial"}) for item in _predictions()
    )
    with pytest.raises(DegeneratePredictionsError):
        _ = evaluate(replace(_request(), predictions=predictions))


def test_group_aggregation_requires_every_group() -> None:
    request = _request()
    split = replace(
        request.split,
        assignments=tuple(
            item
            for item in request.split.assignments
            if item.observation_id != "cell-5"
        ),
    )

    with pytest.raises(MissingEvaluationGroupError) as captured:
        _ = evaluate(replace(request, split=split))

    assert captured.value.observation_id == "cell-5"


def test_protocol_rejects_incompatible_resampling_unit() -> None:
    protocol = _protocol().model_copy(
        update={
            "resampling": ResamplingProtocol(
                method=UncertaintyMethod.BOOTSTRAP,
                unit=ResamplingUnit.CELL,
                seed=23,
                replicates=64,
                confidence_level=0.95,
            )
        }
    )

    with pytest.raises(MetricProtocolError):
        _ = evaluate(replace(_request(), protocol=protocol))


def test_metric_protocol_is_bound_to_split_task() -> None:
    protocol = _protocol().model_copy(update={"task": TaskId("other-task")})

    with pytest.raises(EvaluationProvenanceError):
        _ = evaluate(replace(_request(), protocol=protocol))


def test_feature_threshold_sanity_estimator_is_sparse_and_deterministic() -> None:
    prepared = _request().preprocessing
    estimator = FeatureThresholdSanityEstimator(
        feature_id=FeatureId("gene-1"),
        threshold=50.0,
        below_label="fibroblast",
        at_or_above_label="endothelial",
    )

    first = estimator.predict(prepared.observations)
    second = estimator.predict(tuple(reversed(prepared.observations)))

    assert first == second
    assert {prediction.label for prediction in first} == {
        "endothelial",
        "fibroblast",
    }
