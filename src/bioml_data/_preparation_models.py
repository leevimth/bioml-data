"""Immutable contracts for split-aware single-cell preparation."""

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import ClassVar, NewType, override

from pydantic import BaseModel, ConfigDict

from bioml_data._artifacts import ArtifactId
from bioml_data._single_cell import (
    CanonicalSingleCellDataset,
    FeatureId,
)
from bioml_data._split import (
    AssignmentIdentity,
    ObservationId,
    SplitAssignmentReceipt,
)

PreparedArtifactIdentity = NewType("PreparedArtifactIdentity", str)
PreparationReceiptIdentity = NewType("PreparationReceiptIdentity", str)
PreparationStateIdentity = NewType("PreparationStateIdentity", str)
PreparationProtocolSemanticIdentity = NewType(
    "PreparationProtocolSemanticIdentity", str
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
        "normalization_target_sum": protocol.normalization.target_sum,
        "feature_selection_max_features": (
            None if selection is None else selection.max_features
        ),
        "expression_input": "raw_x",
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


@dataclass(frozen=True, slots=True)
class PreparedObservation:
    """One sparse prepared observation."""

    observation_id: ObservationId
    values: tuple[PreparedValue, ...]


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
    independent_artifact_identity: PreparedArtifactIdentity
    protocol_id: str
    protocol_version: str
    protocol_semantic_identity: PreparationProtocolSemanticIdentity
    seed: int
    split_assignment_identity: AssignmentIdentity
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
    protocol_id: str
    protocol_version: str
    protocol_semantic_identity: PreparationProtocolSemanticIdentity
    seed: int
    split_assignment_identity: str
    fitted_state: FittedPreparationState
    observations: tuple[PreparedObservation, ...]


@dataclass(frozen=True, slots=True)
class SplitAssignmentRequiredError(Exception):
    """Raised when train-fitted preprocessing is attempted before splitting."""

    protocol_id: str

    @override
    def __str__(self) -> str:
        return f"split assignment required before fitting {self.protocol_id!r}"


@dataclass(frozen=True, slots=True)
class InsufficientPreparationDataError(Exception):
    """Raised when preparation filters leave no usable rows or features."""

    phase: str

    @override
    def __str__(self) -> str:
        return f"preparation has no usable data after {self.phase}"


@dataclass(frozen=True, slots=True)
class UnknownAlignmentFeatureError(Exception):
    """Raised when a fixed alignment requests a feature absent from the input."""

    feature_id: FeatureId

    @override
    def __str__(self) -> str:
        return f"alignment feature {self.feature_id!r} is absent"


@dataclass(frozen=True, slots=True)
class FittedStateMismatchError(Exception):
    """Raised when fitted state is applied to a different prepared artifact."""

    expected: PreparedArtifactIdentity
    actual: PreparedArtifactIdentity

    @override
    def __str__(self) -> str:
        return f"fitted state expects {self.expected}; received {self.actual}"


@dataclass(frozen=True, slots=True)
class FittedSplitMismatchError(Exception):
    """Raised when fitted state is applied under a different split receipt."""

    expected: AssignmentIdentity
    actual: AssignmentIdentity

    @override
    def __str__(self) -> str:
        return f"fitted state expects split {self.expected}; received {self.actual}"


@dataclass(frozen=True, slots=True)
class FittedProtocolSemanticMismatchError(Exception):
    """Raised when fitted state belongs to another protocol semantic identity."""

    expected: PreparationProtocolSemanticIdentity
    actual: PreparationProtocolSemanticIdentity

    @override
    def __str__(self) -> str:
        return (
            f"fitted state expects protocol semantics {self.expected}; "
            f"received {self.actual}"
        )
