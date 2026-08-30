"""Fail-fast validation for indexed task-bound evaluation inputs."""

from dataclasses import dataclass

from bioml_data._evaluation_errors import (
    DegenerateLabelsError,
    DegeneratePredictionsError,
    EvaluationIndexError,
    EvaluationPartitionError,
    EvaluationProvenanceError,
    EvaluationShapeError,
    MetricProtocolError,
    MissingEvaluationGroupError,
    UnexpectedClassError,
)
from bioml_data._evaluation_metrics import EvaluationPair
from bioml_data._evaluation_models import (
    AggregationLevel,
    EvaluationRequest,
    ResamplingUnit,
)
from bioml_data._split import GroupId, ObservationId, SplitPartition

_MINIMUM_CLASS_COUNT = 2
_MINIMUM_BOOTSTRAP_REPLICATES = 2
_MINIMUM_GROUP_COUNT = 2


@dataclass(frozen=True, slots=True)
class ValidatedEvaluation:
    """Canonical aligned inputs safe for metric calculation."""

    pairs: tuple[EvaluationPair, ...]
    prediction_order: tuple[int, ...]
    label_order: tuple[int, ...]


def validate(request: EvaluationRequest) -> ValidatedEvaluation:
    """Validate shapes, indices, protocols, provenance, and class support."""
    _validate_protocol(request)
    if len(request.predictions) != len(request.labels):
        raise EvaluationShapeError(
            prediction_count=len(request.predictions),
            label_count=len(request.labels),
        )
    prediction_ids = tuple(item.observation_id for item in request.predictions)
    label_ids = tuple(item.observation_id for item in request.labels)
    duplicates_predictions = _duplicates(prediction_ids)
    duplicates_labels = _duplicates(label_ids)
    prediction_only = tuple(sorted(set(prediction_ids) - set(label_ids)))
    label_only = tuple(sorted(set(label_ids) - set(prediction_ids)))
    prepared_ids = {item.observation_id for item in request.preprocessing.observations}
    missing_preprocessing = tuple(sorted(set(prediction_ids) - prepared_ids))
    if (
        duplicates_predictions
        or duplicates_labels
        or prediction_only
        or label_only
        or missing_preprocessing
    ):
        raise EvaluationIndexError(
            duplicate_predictions=duplicates_predictions,
            duplicate_labels=duplicates_labels,
            prediction_only=prediction_only,
            label_only=label_only,
            missing_preprocessing=missing_preprocessing,
        )

    partitions = {
        item.observation_id: item.partition for item in request.split.assignments
    }
    missing_split_assignments = tuple(sorted(set(prediction_ids) - set(partitions)))
    if (
        request.protocol.aggregation is not AggregationLevel.GROUP
        and missing_split_assignments
    ):
        raise EvaluationIndexError(missing_split_assignments=missing_split_assignments)
    training_observation_ids = tuple(
        sorted(
            observation_id
            for observation_id in prediction_ids
            if partitions.get(observation_id) is SplitPartition.TRAIN
        )
    )
    if training_observation_ids:
        raise EvaluationPartitionError(
            training_observation_ids=training_observation_ids
        )

    predictions = {item.observation_id: item.label for item in request.predictions}
    labels = {item.observation_id: item.label for item in request.labels}
    _validate_classes(labels, predictions, request)
    groups = {item.observation_id: item.group for item in request.split.assignments}
    pairs = tuple(
        EvaluationPair(
            observation_id=observation_id,
            label=labels[observation_id],
            prediction=predictions[observation_id],
            group=_group_for(observation_id, groups, request),
        )
        for observation_id in sorted(predictions)
    )
    if request.protocol.aggregation is AggregationLevel.GROUP:
        group_count = len({pair.group for pair in pairs})
        if group_count < _MINIMUM_GROUP_COUNT:
            raise MetricProtocolError(
                reason="group bootstrap requires at least two groups"
            )
    return ValidatedEvaluation(
        pairs=pairs,
        prediction_order=tuple(
            index
            for index, _ in sorted(
                enumerate(request.predictions),
                key=lambda item: item[1].observation_id,
            )
        ),
        label_order=tuple(
            index
            for index, _ in sorted(
                enumerate(request.labels),
                key=lambda item: item[1].observation_id,
            )
        ),
    )


def _validate_protocol(request: EvaluationRequest) -> None:
    protocol = request.protocol
    if protocol.task != request.split.task:
        raise EvaluationProvenanceError(reason="metric task differs from split task")
    if (
        request.preprocessing.split_assignment_identity
        != request.split.assignment_identity
    ):
        raise EvaluationProvenanceError(
            reason="preprocessing receipt differs from split assignment"
        )
    if len(protocol.eligible_labels) < _MINIMUM_CLASS_COUNT:
        raise MetricProtocolError(reason="at least two eligible labels are required")
    if len(set(protocol.eligible_labels)) != len(protocol.eligible_labels):
        raise MetricProtocolError(reason="eligible labels must be unique")
    if any(not label for label in protocol.eligible_labels):
        raise MetricProtocolError(reason="eligible labels must be non-empty")
    if protocol.resampling.replicates < _MINIMUM_BOOTSTRAP_REPLICATES:
        raise MetricProtocolError(reason="bootstrap requires at least two replicates")
    if not 0.0 < protocol.resampling.confidence_level < 1.0:
        raise MetricProtocolError(
            reason="confidence level must be between zero and one"
        )
    expected_unit = ResamplingUnit(protocol.aggregation.value)
    if protocol.resampling.unit is not expected_unit:
        raise MetricProtocolError(
            reason=(
                f"{protocol.aggregation} aggregation requires "
                f"{expected_unit} resampling"
            )
        )


def _validate_classes(
    labels: dict[ObservationId, str],
    predictions: dict[ObservationId, str],
    request: EvaluationRequest,
) -> None:
    eligible = set(request.protocol.eligible_labels)
    unexpected = tuple(
        sorted((set(labels.values()) | set(predictions.values())) - eligible)
    )
    if unexpected:
        raise UnexpectedClassError(classes=unexpected)
    observed_labels = tuple(sorted(set(labels.values())))
    if len(observed_labels) < _MINIMUM_CLASS_COUNT:
        raise DegenerateLabelsError(observed_labels=observed_labels)
    observed_predictions = tuple(sorted(set(predictions.values())))
    if len(observed_predictions) < _MINIMUM_CLASS_COUNT:
        raise DegeneratePredictionsError(observed_labels=observed_predictions)


def _group_for(
    observation_id: ObservationId,
    groups: dict[ObservationId, GroupId],
    request: EvaluationRequest,
) -> GroupId | None:
    group = groups.get(observation_id)
    if request.protocol.aggregation is AggregationLevel.GROUP and not group:
        raise MissingEvaluationGroupError(observation_id=observation_id)
    return group


def _duplicates(values: tuple[ObservationId, ...]) -> tuple[ObservationId, ...]:
    seen: set[ObservationId] = set()
    duplicates: set[ObservationId] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates))
