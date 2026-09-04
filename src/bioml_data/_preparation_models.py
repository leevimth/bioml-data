"""Immutable contracts for split-aware single-cell preparation."""

import json
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import ClassVar, NewType

from pydantic import BaseModel, ConfigDict

from bioml_data._artifacts import ArtifactId
from bioml_data._preparation_contracts import ExpressionInput
from bioml_data._preparation_errors import (
    FittedProtocolSemanticMismatchError,
    FittedSplitMismatchError,
    FittedStateMismatchError,
    InsufficientPreparationDataError,
    InvalidNormalizationTargetError,
    InvalidPreparedStructureError,
    InvalidPreparedValueError,
    SplitAssignmentRequiredError,
    UnknownAlignmentFeatureError,
)
from bioml_data._single_cell import (
    CanonicalSingleCellDataset,
    FeatureId,
)
from bioml_data._split import (
    ObservationId,
    SplitAssignmentReceipt,
)

PreparedArtifactIdentity = NewType("PreparedArtifactIdentity", str)
PreparationReceiptIdentity = NewType("PreparationReceiptIdentity", str)
PreparationStateIdentity = NewType("PreparationStateIdentity", str)
TrainingMembershipIdentity = NewType("TrainingMembershipIdentity", str)
PreparationProtocolSemanticIdentity = NewType(
    "PreparationProtocolSemanticIdentity", str
)

__all__ = (
    "FittedProtocolSemanticMismatchError",
    "FittedSplitMismatchError",
    "FittedStateMismatchError",
    "InsufficientPreparationDataError",
    "InvalidNormalizationTargetError",
    "InvalidPreparedStructureError",
    "InvalidPreparedValueError",
    "SplitAssignmentRequiredError",
    "UnknownAlignmentFeatureError",
)


@dataclass(frozen=True, slots=True)
class QcParameters:
    """Per-cell count QC plus train-fitted feature-support QC."""

    minimum_cell_count: int
    minimum_feature_cells: int


@dataclass(frozen=True, slots=True)
class GeneAlignmentParameters:
    """Fixed ordered feature identity contract."""

    feature_ids: tuple[FeatureId, ...]


@dataclass(frozen=True, slots=True)
class NormalizationParameters:
    """Fixed per-cell library-size normalization target."""

    target_sum: float

    def __post_init__(self) -> None:
        """Reject non-finite normalization semantics at the domain boundary."""
        if type(self.target_sum) not in (int, float) or not isfinite(self.target_sum):
            raise InvalidNormalizationTargetError(target_sum=self.target_sum)


@dataclass(frozen=True, slots=True)
class FeatureSelectionParameters:
    """Optional train-fitted feature-count cap."""

    max_features: int


@dataclass(frozen=True, slots=True)
class PreparationProtocol:
    """Versioned deterministic and train-fitted preparation parameters."""

    protocol_id: str
    version: str
    qc: QcParameters
    alignment: GeneAlignmentParameters
    normalization: NormalizationParameters
    feature_selection: FeatureSelectionParameters | None


def preparation_protocol_semantic_identity(
    protocol: PreparationProtocol,
) -> PreparationProtocolSemanticIdentity:
    """Identify every ordered fixed and train-fitted protocol semantic input."""
    selection = protocol.feature_selection
    target_sum = protocol.normalization.target_sum
    if type(target_sum) not in (int, float) or not isfinite(target_sum):
        raise InvalidNormalizationTargetError(target_sum=target_sum)
    payload = {
        "domain": "bioml-data/preparation-protocol-semantics",
        "schema": "v1",
        "protocol_id": protocol.protocol_id,
        "version": protocol.version,
        "qc": {
            "minimum_cell_count": protocol.qc.minimum_cell_count,
            "minimum_feature_cells": protocol.qc.minimum_feature_cells,
        },
        "alignment_feature_ids": tuple(
            str(item) for item in protocol.alignment.feature_ids
        ),
        "normalization_target_sum": target_sum,
        "feature_selection_max_features": (
            None if selection is None else selection.max_features
        ),
        "expression_input": ExpressionInput.RAW_X.value,
        "canonical_materialization_fit_scope": "none",
        "prepared_fit_scope": "train_only",
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return PreparationProtocolSemanticIdentity(sha256(encoded.encode()).hexdigest())


@dataclass(frozen=True, slots=True)
class PreparedValue:
    """One nonzero normalized feature value."""

    feature_id: FeatureId
    value: float

    def __post_init__(self) -> None:
        """Reject non-finite values before they can reach identity rendering."""
        if type(self.value) not in (int, float) or not isfinite(self.value):
            raise InvalidPreparedValueError(value=self.value)


@dataclass(frozen=True, slots=True)
class PreparedObservation:
    """One sparse prepared observation."""

    observation_id: ObservationId
    values: tuple[PreparedValue, ...]

    def __post_init__(self) -> None:
        """Revalidate nested values at this broader immutable boundary."""
        validate_prepared_observations((self,))


@dataclass(frozen=True, slots=True)
class TrainIndependentPreparation:
    """Fixed preparation output produced without learning split statistics."""

    input_artifact_identity: ArtifactId
    output_artifact_identity: PreparedArtifactIdentity
    protocol: PreparationProtocol
    seed: int
    feature_ids: tuple[FeatureId, ...]
    observations: tuple[PreparedObservation, ...]


class FittedPreparationState(BaseModel):
    """Serializable state learned exclusively from assigned training rows."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    state_identity: PreparationStateIdentity
    protocol_id: str
    protocol_version: str
    protocol_semantic_identity: PreparationProtocolSemanticIdentity
    seed: int
    training_membership_identity: TrainingMembershipIdentity
    training_observation_ids: tuple[ObservationId, ...]
    selected_feature_ids: tuple[FeatureId, ...]


@dataclass(frozen=True, slots=True)
class PreparationRequest:
    """Complete benchmark preparation invocation."""

    dataset: CanonicalSingleCellDataset
    protocol: PreparationProtocol
    split: SplitAssignmentReceipt
    seed: int


@dataclass(frozen=True, slots=True)
class PreparedBenchmarkReceipt:
    """Prepared rows with fitted state and reproducible artifact identities."""

    receipt_identity: PreparationReceiptIdentity
    input_artifact_identity: ArtifactId
    output_artifact_identity: PreparedArtifactIdentity
    independent_artifact_identity: PreparedArtifactIdentity
    protocol_id: str
    protocol_version: str
    protocol_semantic_identity: PreparationProtocolSemanticIdentity
    seed: int
    split_assignment_identity: str
    fitted_state: FittedPreparationState
    observations: tuple[PreparedObservation, ...]


def validate_prepared_observations(
    observations: tuple[PreparedObservation, ...],
) -> None:
    """Parse nested sparse rows before deterministic identity work."""
    if type(observations) is not tuple:
        raise InvalidPreparedStructureError(field="observations")
    for observation in observations:
        if type(observation) is not PreparedObservation:
            raise InvalidPreparedStructureError(field="observations")
        if type(observation.values) is not tuple:
            raise InvalidPreparedStructureError(field="values")
        for value in observation.values:
            if type(value) is not PreparedValue:
                raise InvalidPreparedStructureError(field="values")
            if type(value.value) not in (int, float) or not isfinite(value.value):
                raise InvalidPreparedValueError(value=value.value)
