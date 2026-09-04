"""Canonical identities for train-fitted preparation state and outputs."""

import json
from dataclasses import dataclass
from hashlib import sha256

from bioml_data._preparation_models import (
    FittedPreparationState,
    PreparationProtocol,
    PreparationReceiptIdentity,
    PreparationStateIdentity,
    PreparedArtifactIdentity,
    PreparedBenchmarkReceipt,
    PreparedObservation,
    TrainingMembershipIdentity,
    preparation_protocol_semantic_identity,
    validate_prepared_observations,
)

type JsonScalar = str | int | float
type JsonValue = JsonScalar | dict[str, JsonValue] | tuple[JsonValue, ...]
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class FittedStateIdentityInput:
    """All semantic fields used to identify one fitted preparation state."""

    protocol: PreparationProtocol
    seed: int
    training_membership_identity: TrainingMembershipIdentity
    training_observation_ids: tuple[str, ...]
    training_observations: tuple[PreparedObservation, ...]
    selected_feature_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreparedOutputIdentityInput:
    """All immutable fields used to identify a prepared output artifact."""

    input_artifact_identity: str
    independent_artifact_identity: str
    fitted_state: FittedPreparationState
    protocol_semantic_identity: str
    split_assignment_identity: str
    seed: int
    observations: tuple[PreparedObservation, ...]


def fitted_state_identity(
    identity_input: FittedStateIdentityInput,
) -> PreparationStateIdentity:
    """Identify all fixed, training-row, and selected-feature state inputs."""
    payload: JsonObject = {
        "domain": "bioml-data/fitted-preparation-state",
        "schema": "v1",
        "protocol_id": identity_input.protocol.protocol_id,
        "protocol_version": identity_input.protocol.version,
        "protocol_semantic_identity": preparation_protocol_semantic_identity(
            identity_input.protocol
        ),
        "seed": identity_input.seed,
        "training_membership_identity": identity_input.training_membership_identity,
        "training_observation_ids": identity_input.training_observation_ids,
        "training_observations": _observations_payload(
            identity_input.training_observations
        ),
        "selected_feature_ids": identity_input.selected_feature_ids,
    }
    return PreparationStateIdentity(_payload_identity(payload))


def training_membership_identity(
    training_observation_ids: tuple[str, ...],
) -> TrainingMembershipIdentity:
    """Identify the canonical sorted set of observations used for fitting."""
    payload: JsonObject = {
        "domain": "bioml-data/training-membership",
        "schema": "v1",
        "training_observation_ids": tuple(sorted(training_observation_ids)),
    }
    return TrainingMembershipIdentity(_payload_identity(payload))


def prepared_output_artifact_identity(
    identity_input: PreparedOutputIdentityInput,
) -> PreparedArtifactIdentity:
    """Identify the output artifact from its exact transformed sparse rows."""
    validate_prepared_observations(identity_input.observations)
    payload: JsonObject = {
        "domain": "bioml-data/prepared-output-artifact",
        "schema": "v1",
        "input_artifact_identity": identity_input.input_artifact_identity,
        "independent_artifact_identity": identity_input.independent_artifact_identity,
        "fitted_state": _fitted_state_payload(identity_input.fitted_state),
        "protocol_semantic_identity": identity_input.protocol_semantic_identity,
        "split_assignment_identity": identity_input.split_assignment_identity,
        "seed": identity_input.seed,
        "observations": _observations_payload(identity_input.observations),
    }
    return PreparedArtifactIdentity(_payload_identity(payload))


def prepared_benchmark_receipt_identity(
    receipt: PreparedBenchmarkReceipt,
) -> PreparationReceiptIdentity:
    """Identify every immutable prepared receipt field, including output rows."""
    validate_prepared_observations(receipt.observations)
    payload: JsonObject = {
        "domain": "bioml-data/prepared-benchmark-receipt",
        "schema": "v1",
        "input_artifact_identity": receipt.input_artifact_identity,
        "output_artifact_identity": receipt.output_artifact_identity,
        "independent_artifact_identity": receipt.independent_artifact_identity,
        "protocol_id": receipt.protocol_id,
        "protocol_version": receipt.protocol_version,
        "protocol_semantic_identity": receipt.protocol_semantic_identity,
        "seed": receipt.seed,
        "split_assignment_identity": receipt.split_assignment_identity,
        "fitted_state": _fitted_state_payload(receipt.fitted_state),
        "observations": _observations_payload(receipt.observations),
    }
    return PreparationReceiptIdentity(_payload_identity(payload))


def _fitted_state_payload(state: FittedPreparationState) -> JsonObject:
    return {
        "state_identity": state.state_identity,
        "protocol_id": state.protocol_id,
        "protocol_version": state.protocol_version,
        "protocol_semantic_identity": state.protocol_semantic_identity,
        "seed": state.seed,
        "training_membership_identity": state.training_membership_identity,
        "training_observation_ids": state.training_observation_ids,
        "selected_feature_ids": state.selected_feature_ids,
    }


def _observations_payload(
    observations: tuple[PreparedObservation, ...],
) -> tuple[JsonObject, ...]:
    validate_prepared_observations(observations)
    return tuple(_observation_payload(item) for item in observations)


def _observation_payload(observation: PreparedObservation) -> JsonObject:
    values: tuple[JsonObject, ...] = tuple(
        {"feature_id": str(value.feature_id), "value": value.value}
        for value in observation.values
    )
    return {"observation_id": str(observation.observation_id), "values": values}


def _payload_identity(payload: JsonObject) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return sha256(encoded.encode()).hexdigest()
