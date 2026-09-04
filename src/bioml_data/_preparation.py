"""Split-aware single-cell preparation lifecycle."""

from dataclasses import replace

import bioml_data._preparation_models as _models
from bioml_data._preparation_identities import (
    FittedStateIdentityInput,
    PreparedOutputIdentityInput,
    fitted_state_identity,
    prepared_benchmark_receipt_identity,
    prepared_output_artifact_identity,
    training_membership_identity,
)
from bioml_data._preparation_models import (
    FittedProtocolSemanticMismatchError,
    FittedStateMismatchError,
    InsufficientPreparationDataError,
    PreparationReceiptIdentity,
    PreparedBenchmarkReceipt,
    PreparedObservation,
    TrainIndependentPreparation,
    UnknownAlignmentFeatureError,
    preparation_protocol_semantic_identity,
)
from bioml_data._preparation_rows import (
    PreparationRun,
    SupportedFeatures,
    aligned_row,
    independent_identity,
    normalize_row,
)
from bioml_data._preparation_selection import select_features
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import ObservationId, SplitAssignmentReceipt, SplitPartition

FeatureSelectionParameters = _models.FeatureSelectionParameters
FittedPreparationState = _models.FittedPreparationState
GeneAlignmentParameters = _models.GeneAlignmentParameters
NormalizationParameters = _models.NormalizationParameters
PreparationProtocol = _models.PreparationProtocol
PreparationRequest = _models.PreparationRequest
QcParameters = _models.QcParameters
SplitAssignmentRequiredError = _models.SplitAssignmentRequiredError


def prepare_train_independent(
    dataset: CanonicalSingleCellDataset,
    *,
    protocol: PreparationProtocol,
    seed: int,
) -> TrainIndependentPreparation:
    """Apply fixed QC, alignment, and per-cell normalization without fitting."""
    input_features = tuple(feature.feature_id for feature in dataset.features)
    feature_positions = {
        feature_id: position for position, feature_id in enumerate(input_features)
    }
    for feature_id in protocol.alignment.feature_ids:
        if feature_id not in feature_positions:
            raise UnknownAlignmentFeatureError(feature_id=feature_id)
    source_positions = tuple(
        feature_positions[feature_id] for feature_id in protocol.alignment.feature_ids
    )

    aligned_rows = tuple(
        aligned_row(dataset, row_index, source_positions)
        for row_index in range(len(dataset.observations))
    )
    retained = tuple(
        (dataset.observations[index], row)
        for index, row in enumerate(aligned_rows)
        if sum(row) >= protocol.qc.minimum_cell_count
    )
    if not retained:
        raise InsufficientPreparationDataError(phase="cell_qc")

    supported = SupportedFeatures(
        feature_ids=protocol.alignment.feature_ids,
        positions=tuple(range(len(protocol.alignment.feature_ids))),
    )
    prepared_rows = tuple(
        PreparedObservation(
            observation_id=ObservationId(observation.cell_id),
            values=normalize_row(
                row,
                supported,
                protocol.normalization,
            ),
        )
        for observation, row in retained
    )
    identity = independent_identity(
        dataset,
        PreparationRun(protocol=protocol, seed=seed),
        prepared_rows,
    )
    return TrainIndependentPreparation(
        input_artifact_identity=dataset.artifact.artifact_id,
        output_artifact_identity=identity,
        protocol=protocol,
        seed=seed,
        feature_ids=protocol.alignment.feature_ids,
        observations=prepared_rows,
    )


def fit_train_preprocessing(
    prepared: TrainIndependentPreparation,
    *,
    split: SplitAssignmentReceipt | None,
) -> FittedPreparationState:
    """Fit optional feature selection using assigned training observations only."""
    if split is None:
        raise SplitAssignmentRequiredError(protocol_id=prepared.protocol.protocol_id)
    training_ids = tuple(
        sorted(
            assignment.observation_id
            for assignment in split.assignments
            if assignment.partition is SplitPartition.TRAIN
        )
    )
    observations_by_id = {
        observation.observation_id: observation for observation in prepared.observations
    }
    training_rows = tuple(
        observations_by_id[item] for item in training_ids if item in observations_by_id
    )
    if not training_rows:
        raise InsufficientPreparationDataError(phase="training_partition")

    selected = select_features(prepared, training_rows)
    return FittedPreparationState(
        state_identity=fitted_state_identity(
            FittedStateIdentityInput(
                protocol=prepared.protocol,
                seed=prepared.seed,
                training_membership_identity=training_membership_identity(
                    tuple(str(item) for item in training_ids)
                ),
                training_observation_ids=training_ids,
                training_observations=training_rows,
                selected_feature_ids=selected,
            )
        ),
        protocol_id=prepared.protocol.protocol_id,
        protocol_version=prepared.protocol.version,
        protocol_semantic_identity=preparation_protocol_semantic_identity(
            prepared.protocol
        ),
        seed=prepared.seed,
        training_membership_identity=training_membership_identity(
            tuple(str(item) for item in training_ids)
        ),
        training_observation_ids=training_ids,
        selected_feature_ids=selected,
    )


def apply_fitted_preprocessing(
    prepared: TrainIndependentPreparation,
    *,
    fitted: FittedPreparationState,
    split: SplitAssignmentReceipt,
) -> PreparedBenchmarkReceipt:
    """Apply serialized train-fitted state to train, validation, and test rows."""
    protocol_semantic_identity = preparation_protocol_semantic_identity(
        prepared.protocol
    )
    if fitted.protocol_semantic_identity != protocol_semantic_identity:
        raise FittedProtocolSemanticMismatchError(
            expected=fitted.protocol_semantic_identity,
            actual=protocol_semantic_identity,
        )
    expected_fitted = fit_train_preprocessing(prepared, split=split)
    if fitted != expected_fitted:
        raise FittedStateMismatchError(
            expected=str(expected_fitted.state_identity),
            actual=str(fitted.state_identity),
        )
    selected = frozenset(fitted.selected_feature_ids)
    observations = tuple(
        PreparedObservation(
            observation_id=observation.observation_id,
            values=tuple(
                value for value in observation.values if value.feature_id in selected
            ),
        )
        for observation in prepared.observations
    )
    output_identity = prepared_output_artifact_identity(
        PreparedOutputIdentityInput(
            input_artifact_identity=prepared.input_artifact_identity,
            independent_artifact_identity=prepared.output_artifact_identity,
            fitted_state=fitted,
            protocol_semantic_identity=protocol_semantic_identity,
            split_assignment_identity=split.assignment_identity,
            seed=prepared.seed,
            observations=observations,
        )
    )
    receipt = PreparedBenchmarkReceipt(
        receipt_identity=PreparationReceiptIdentity(""),
        input_artifact_identity=prepared.input_artifact_identity,
        output_artifact_identity=output_identity,
        independent_artifact_identity=prepared.output_artifact_identity,
        protocol_id=prepared.protocol.protocol_id,
        protocol_version=prepared.protocol.version,
        protocol_semantic_identity=protocol_semantic_identity,
        seed=prepared.seed,
        split_assignment_identity=split.assignment_identity,
        fitted_state=fitted,
        observations=observations,
    )
    return replace(
        receipt,
        receipt_identity=prepared_benchmark_receipt_identity(receipt),
    )


def prepare_benchmark(request: PreparationRequest) -> PreparedBenchmarkReceipt:
    """Run fixed preparation, train fitting, and deterministic state application."""
    independent = prepare_train_independent(
        request.dataset,
        protocol=request.protocol,
        seed=request.seed,
    )
    fitted = fit_train_preprocessing(independent, split=request.split)
    return apply_fitted_preprocessing(
        independent,
        fitted=fitted,
        split=request.split,
    )
