"""Immutable, path-free scientific preparation-execution receipts."""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum, unique
from hashlib import sha256
from math import isfinite
from typing import Final, NewType

from bioml_data._artifacts import ArtifactId, ArtifactReceipt
from bioml_data._dataset_preparation_models import (
    DatasetPreparationOutcome,
    DatasetPreparationReceipt,
)
from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId
from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_runtime import PreparationExecutionRuntime
from bioml_data._preparation_models import (
    PreparationProtocol,
    PreparationReceiptIdentity,
    PreparationStateIdentity,
    PreparedArtifactIdentity,
    PreparedBenchmarkReceipt,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import AssignmentIdentity, SplitAssignmentReceipt

PreparationExecutionReceiptIdentity = NewType(
    "PreparationExecutionReceiptIdentity", str
)
MAX_ALIGNMENT_FEATURE_IDS: Final = 50_000


@unique
class ExpressionInput(StrEnum):
    """Matrix selected by the canonical dataset transform."""

    RAW_X = "raw.X"
    X = "X"


@unique
class PreparationFitScope(StrEnum):
    """Scope from which a preparation stage may learn statistics."""

    NONE = "none"
    TRAIN_ONLY = "train_only"


@unique
class MetadataConcordanceAttachmentStatus(StrEnum):
    """Collapsed status of a full optional concordance report."""

    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_REPORTED = "not_reported"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class PreparationExecutionRequest:
    """Typed inputs needed to record one complete preparation execution."""

    dataset: CanonicalSingleCellDataset
    input_artifact: ArtifactReceipt
    materialization: DatasetPreparationReceipt
    prepared: PreparedBenchmarkReceipt
    assignment: SplitAssignmentReceipt
    protocol: PreparationProtocol
    runtime: PreparationExecutionRuntime
    concordance: MetadataConcordanceReport | None = None


@dataclass(frozen=True, slots=True)
class PreparationSemanticParameters:
    """Compact semantic parameters, excluding paths and host-local state."""

    minimum_cell_count: int
    minimum_feature_cells: int
    alignment_feature_ids: tuple[str, ...]
    alignment_feature_count: int
    alignment_feature_identity: str
    normalization_target_sum: float
    max_features: int | None

    def __post_init__(self) -> None:
        """Keep rendered preparation semantics finite, bounded, and canonical."""
        _validate_semantic_parameters(self)


@dataclass(frozen=True, slots=True)
class MetadataConcordanceAttachment:
    """Identity and aggregate outcome for an attached concordance report."""

    report_identity: str
    status: MetadataConcordanceAttachmentStatus


@dataclass(frozen=True, slots=True)
class PreparationExecutionReceipt:
    """One deterministic scientific context for split-aware preparation output."""

    receipt_identity: PreparationExecutionReceiptIdentity
    dataset: DatasetSnapshotIdentity
    task: TaskId
    input_artifact_identity: ArtifactId
    canonical_artifact_identity: ArtifactId
    materialization_parent_artifact_identities: tuple[ArtifactId, ...]
    materialization_outcome: DatasetPreparationOutcome
    preparation_protocol_id: str
    preparation_protocol_version: str
    semantic_parameters: PreparationSemanticParameters
    expression_input: ExpressionInput
    canonical_materialization_fit_scope: PreparationFitScope
    prepared_fit_scope: PreparationFitScope
    split_protocol: ProtocolId
    split_assignment_identity: AssignmentIdentity
    seed: int
    prepared_benchmark_receipt_identity: PreparationReceiptIdentity
    prepared_output_artifact_identity: PreparedArtifactIdentity
    fitted_state_identity: PreparationStateIdentity
    runtime: PreparationExecutionRuntime
    metadata_concordance: MetadataConcordanceAttachment | None

    def to_json(self) -> str:
        """Return canonical JSON without filesystem or host-local fields."""
        _validate_semantic_parameters(self.semantic_parameters)
        return json.dumps(
            asdict(self),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def preparation_execution_receipt_identity(
    receipt: PreparationExecutionReceipt,
) -> PreparationExecutionReceiptIdentity:
    """Hash every rendered scientific field except its derived receipt identity."""
    _validate_semantic_parameters(receipt.semantic_parameters)
    payload = asdict(receipt)
    del payload["receipt_identity"]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return PreparationExecutionReceiptIdentity(sha256(encoded.encode()).hexdigest())


def _validate_semantic_parameters(parameters: PreparationSemanticParameters) -> None:
    """Reject values that cannot be safely and reproducibly rendered to JSON."""
    if not isfinite(parameters.normalization_target_sum):
        raise PreparationExecutionReceiptMismatchError(
            field="normalization_target_sum",
            expected="finite float",
            actual=repr(parameters.normalization_target_sum),
        )
    feature_ids = parameters.alignment_feature_ids
    if len(feature_ids) > MAX_ALIGNMENT_FEATURE_IDS:
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_ids",
            expected=f"at most {MAX_ALIGNMENT_FEATURE_IDS} feature identifiers",
            actual=str(len(feature_ids)),
        )
    if parameters.alignment_feature_count != len(feature_ids):
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_count",
            expected=str(len(feature_ids)),
            actual=str(parameters.alignment_feature_count),
        )
    if feature_ids != tuple(sorted(set(feature_ids))):
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_ids",
            expected="sorted unique feature identifiers",
            actual=str(len(feature_ids)),
        )
    expected_identity = sha256("\0".join(feature_ids).encode()).hexdigest()
    if parameters.alignment_feature_identity != expected_identity:
        raise PreparationExecutionReceiptMismatchError(
            field="alignment_feature_identity",
            expected=expected_identity,
            actual=parameters.alignment_feature_identity,
        )
