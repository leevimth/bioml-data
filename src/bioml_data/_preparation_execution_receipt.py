"""Full public-boundary validation and rendering for execution receipts."""

import json
import re
from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Final, NoReturn

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
from bioml_data._preparation_execution_models import (
    ExpressionInput,
    MetadataConcordanceAttachment,
    MetadataConcordanceAttachmentStatus,
    PreparationExecutionReceiptIdentity,
    PreparationFitScope,
    PreparationSemanticParameters,
    validate_semantic_parameters,
)
from bioml_data._preparation_execution_runtime import (
    PreparationExecutionRuntime,
    validate_runtime_metadata,
)
from bioml_data._preparation_models import (
    PreparationProtocol,
    PreparationReceiptIdentity,
    PreparationStateIdentity,
    PreparedArtifactIdentity,
    PreparedBenchmarkReceipt,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import AssignmentIdentity, SplitAssignmentReceipt

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


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
    preparation_protocol_semantic_identity: str
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
        """Return only fully validated canonical JSON."""
        validate_preparation_execution_receipt_structure(self)
        return _canonical_json_unchecked(self, include_receipt_identity=True)


def preparation_execution_receipt_identity(
    receipt: PreparationExecutionReceipt,
) -> PreparationExecutionReceiptIdentity:
    """Hash every validated scientific field except its derived receipt identity."""
    validate_preparation_execution_receipt_structure(receipt)
    encoded = _canonical_json_unchecked(receipt, include_receipt_identity=False)
    return PreparationExecutionReceiptIdentity(sha256(encoded.encode()).hexdigest())


def validate_preparation_execution_receipt_structure(
    receipt: PreparationExecutionReceipt,
) -> None:
    """Reject hostile rehashed nested values before identity or JSON rendering."""
    _require_semantic_parameters(receipt.semantic_parameters)
    _require_runtime(receipt.runtime)
    _require_enum(
        "materialization_outcome",
        receipt.materialization_outcome,
        DatasetPreparationOutcome,
    )
    _require_enum("expression_input", receipt.expression_input, ExpressionInput)
    _require_fit_scopes(receipt)
    _require_attachment(receipt.metadata_concordance)
    _require_execution_scalars(receipt)


def _canonical_json_unchecked(
    receipt: PreparationExecutionReceipt,
    *,
    include_receipt_identity: bool,
) -> str:
    """Render after the public boundary has completed structural validation."""
    payload = asdict(receipt)
    if not include_receipt_identity:
        del payload["receipt_identity"]
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _require_semantic_parameters(value: PreparationSemanticParameters | str) -> None:
    if not isinstance(value, PreparationSemanticParameters):
        _raise(
            "semantic_parameters", "PreparationSemanticParameters", type(value).__name__
        )
    validate_semantic_parameters(value)


def _require_runtime(value: PreparationExecutionRuntime | str) -> None:
    if not isinstance(value, PreparationExecutionRuntime):
        _raise("runtime", "PreparationExecutionRuntime", type(value).__name__)
    validate_runtime_metadata(value)


def _require_enum(field: str, value: StrEnum, enum: type[StrEnum]) -> None:
    try:
        _ = enum(value)
    except (TypeError, ValueError):
        _raise(field, "/".join(item.value for item in enum), repr(value))


def _require_fit_scopes(receipt: PreparationExecutionReceipt) -> None:
    _require_enum(
        "canonical_materialization_fit_scope",
        receipt.canonical_materialization_fit_scope,
        PreparationFitScope,
    )
    _require_enum("prepared_fit_scope", receipt.prepared_fit_scope, PreparationFitScope)
    if receipt.canonical_materialization_fit_scope != PreparationFitScope.NONE:
        _raise(
            "canonical_materialization_fit_scope",
            "none",
            str(receipt.canonical_materialization_fit_scope),
        )
    if receipt.prepared_fit_scope != PreparationFitScope.TRAIN_ONLY:
        _raise("prepared_fit_scope", "train_only", str(receipt.prepared_fit_scope))


def _require_attachment(value: MetadataConcordanceAttachment | str | None) -> None:
    if value is None:
        return
    if not isinstance(value, MetadataConcordanceAttachment):
        _raise(
            "metadata_concordance",
            "MetadataConcordanceAttachment or none",
            type(value).__name__,
        )
    _require_enum(
        "metadata_concordance_status", value.status, MetadataConcordanceAttachmentStatus
    )
    if _SHA256.fullmatch(value.report_identity) is None:
        _raise(
            "metadata_concordance_identity",
            "64 lowercase hexadecimal characters",
            value.report_identity,
        )


def _require_execution_scalars(receipt: PreparationExecutionReceipt) -> None:
    if type(receipt.seed) is not int or receipt.seed < 0:
        _raise("seed", "non-negative integer", repr(receipt.seed))
    parent_ids = receipt.materialization_parent_artifact_identities
    if not parent_ids:
        _raise(
            "materialization_parent_artifact_identities", "at least one parent", "empty"
        )
    if len(set(parent_ids)) != len(parent_ids):
        _raise(
            "materialization_parent_artifact_identities",
            "unique artifact identities",
            "duplicate",
        )
    for field, value in (
        ("preparation_protocol_id", receipt.preparation_protocol_id),
        ("preparation_protocol_version", receipt.preparation_protocol_version),
    ):
        if type(value) is not str or not value.strip():
            _raise(field, "non-empty string", repr(value))
    if _SHA256.fullmatch(receipt.preparation_protocol_semantic_identity) is None:
        _raise(
            "preparation_protocol_semantic_identity",
            "64 lowercase hexadecimal characters",
            receipt.preparation_protocol_semantic_identity,
        )


def _raise(field: str, expected: str, actual: str) -> NoReturn:
    raise PreparationExecutionReceiptMismatchError(
        field=field,
        expected=expected,
        actual=actual,
    )
