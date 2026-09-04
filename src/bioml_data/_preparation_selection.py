"""Train-only feature filtering and deterministic feature selection."""

from bioml_data._preparation_models import (
    InsufficientPreparationDataError,
    PreparedObservation,
    TrainIndependentPreparation,
)
from bioml_data._single_cell import FeatureId


def select_features(
    prepared: TrainIndependentPreparation,
    training_rows: tuple[PreparedObservation, ...],
) -> tuple[FeatureId, ...]:
    """Fit feature support and optional count cap exclusively from training rows."""
    supported = tuple(
        feature_id
        for feature_id in prepared.feature_ids
        if sum(
            1
            for row in training_rows
            if any(
                value.feature_id == feature_id and value.value > 0
                for value in row.values
            )
        )
        >= prepared.protocol.qc.minimum_feature_cells
    )
    if not supported:
        raise InsufficientPreparationDataError(phase="feature_qc")
    selection = prepared.protocol.feature_selection
    if selection is None:
        return supported
    totals = {
        feature_id: sum(
            value.value
            for row in training_rows
            for value in row.values
            if value.feature_id == feature_id
        )
        for feature_id in supported
    }
    return tuple(
        sorted(supported, key=lambda item: (-totals[item], item))[
            : selection.max_features
        ]
    )
