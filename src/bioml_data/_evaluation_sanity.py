"""Small deterministic estimator for evaluation plumbing sanity checks."""

from dataclasses import dataclass

from bioml_data._evaluation_models import PredictionRecord
from bioml_data._preparation_models import PreparedObservation
from bioml_data._single_cell import FeatureId


@dataclass(frozen=True, slots=True)
class FeatureThresholdSanityEstimator:
    """Fixed sparse feature threshold; not a trained benchmark model."""

    feature_id: FeatureId
    threshold: float
    below_label: str
    at_or_above_label: str

    def predict(
        self,
        observations: tuple[PreparedObservation, ...],
    ) -> tuple[PredictionRecord, ...]:
        """Predict deterministically without dense matrix materialization."""
        return tuple(
            PredictionRecord(
                observation_id=observation.observation_id,
                label=(
                    self.at_or_above_label
                    if _feature_value(observation, self.feature_id) >= self.threshold
                    else self.below_label
                ),
            )
            for observation in sorted(
                observations,
                key=lambda item: item.observation_id,
            )
        )


def _feature_value(observation: PreparedObservation, feature_id: FeatureId) -> float:
    return next(
        (item.value for item in observation.values if item.feature_id == feature_id),
        0.0,
    )
