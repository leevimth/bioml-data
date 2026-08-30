"""Typed failures raised before task-bound metric calculation."""

from dataclasses import dataclass
from typing import override

from bioml_data._split import ObservationId


@dataclass(frozen=True, slots=True)
class EvaluationShapeError(Exception):
    """Raised when prediction and label vector lengths differ."""

    prediction_count: int
    label_count: int

    @override
    def __str__(self) -> str:
        return (
            f"prediction count {self.prediction_count} "
            f"!= label count {self.label_count}"
        )


@dataclass(frozen=True, slots=True)
class EvaluationIndexError(Exception):
    """Raised when indexed evaluation inputs are duplicate or misaligned."""

    duplicate_predictions: tuple[ObservationId, ...] = ()
    duplicate_labels: tuple[ObservationId, ...] = ()
    prediction_only: tuple[ObservationId, ...] = ()
    label_only: tuple[ObservationId, ...] = ()
    missing_preprocessing: tuple[ObservationId, ...] = ()
    missing_split_assignments: tuple[ObservationId, ...] = ()


@dataclass(frozen=True, slots=True)
class DegenerateLabelsError(Exception):
    """Raised when fewer than two ground-truth classes are observable."""

    observed_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DegeneratePredictionsError(Exception):
    """Raised when predictions contain fewer than two observable classes."""

    observed_labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MissingEvaluationGroupError(Exception):
    """Raised when grouped evaluation lacks an observation's group identity."""

    observation_id: ObservationId


@dataclass(frozen=True, slots=True)
class MetricProtocolError(Exception):
    """Raised when a metric specification is incompatible or incomplete."""

    reason: str


@dataclass(frozen=True, slots=True)
class EvaluationProvenanceError(Exception):
    """Raised when split, task, or preprocessing identities disagree."""

    reason: str


@dataclass(frozen=True, slots=True)
class EvaluationPartitionError(Exception):
    """Raised when evaluation inputs contain training observations."""

    training_observation_ids: tuple[ObservationId, ...]

    @override
    def __str__(self) -> str:
        return (
            "evaluation is limited to validation/test observations; received "
            f"training observations {self.training_observation_ids!r}"
        )


@dataclass(frozen=True, slots=True)
class UnexpectedClassError(Exception):
    """Raised when labels fall outside the frozen protocol eligibility set."""

    classes: tuple[str, ...]
