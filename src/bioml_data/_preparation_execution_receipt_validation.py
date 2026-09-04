"""Structural validation for serialized preparation-execution receipts."""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn, Protocol

from bioml_data._dataset_preparation_models import DatasetPreparationOutcome
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data._preparation_contracts import ExpressionInput, PreparationFitScope
from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_models import (
    MetadataConcordanceAttachment,
    MetadataConcordanceAttachmentStatus,
    PreparationExecutionReceiptIdentity,
    PreparationSemanticParameters,
    validate_semantic_parameters,
)
from bioml_data._preparation_execution_runtime import (
    PreparationExecutionRuntime,
    validate_runtime_metadata,
)
from bioml_data._preparation_execution_tokens import (
    validate_safe_identifier,
    validate_sha256,
)

if TYPE_CHECKING:
    from enum import StrEnum

    from bioml_data._artifacts import ArtifactId
    from bioml_data._domain import ProtocolId, TaskId
    from bioml_data._preparation_models import (
        PreparationReceiptIdentity,
        PreparationStateIdentity,
        PreparedArtifactIdentity,
    )
    from bioml_data._split import AssignmentIdentity


class ExecutionReceiptLike(Protocol):
    """Fields needed to validate a serialized execution receipt."""

    @property
    def receipt_identity(self) -> PreparationExecutionReceiptIdentity: ...
    @property
    def dataset(self) -> DatasetSnapshotIdentity: ...
    @property
    def task(self) -> TaskId: ...
    @property
    def input_artifact_identity(self) -> ArtifactId: ...
    @property
    def canonical_artifact_identity(self) -> ArtifactId: ...
    @property
    def materialization_parent_artifact_identities(self) -> tuple[ArtifactId, ...]: ...
    @property
    def materialization_outcome(self) -> DatasetPreparationOutcome: ...
    @property
    def preparation_protocol_id(self) -> str: ...
    @property
    def preparation_protocol_version(self) -> str: ...
    @property
    def preparation_protocol_semantic_identity(self) -> str: ...
    @property
    def semantic_parameters(self) -> PreparationSemanticParameters: ...
    @property
    def expression_input(self) -> ExpressionInput: ...
    @property
    def canonical_materialization_fit_scope(self) -> PreparationFitScope: ...
    @property
    def prepared_fit_scope(self) -> PreparationFitScope: ...
    @property
    def split_protocol(self) -> ProtocolId: ...
    @property
    def split_assignment_identity(self) -> AssignmentIdentity: ...
    @property
    def seed(self) -> int: ...
    @property
    def prepared_benchmark_receipt_identity(self) -> PreparationReceiptIdentity: ...
    @property
    def prepared_output_artifact_identity(self) -> PreparedArtifactIdentity: ...
    @property
    def fitted_state_identity(self) -> PreparationStateIdentity: ...
    @property
    def runtime(self) -> PreparationExecutionRuntime: ...
    @property
    def metadata_concordance(self) -> MetadataConcordanceAttachment | None: ...


def validate_receipt_structure(receipt: ExecutionReceiptLike) -> None:
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


def raise_mismatch(field: str, expected: str, actual: str) -> NoReturn:
    raise PreparationExecutionReceiptMismatchError(
        field=field,
        expected=expected,
        actual=actual,
    )


def _require_semantic_parameters(value: PreparationSemanticParameters | str) -> None:
    if type(value) is not PreparationSemanticParameters:
        raise_mismatch(
            "semantic_parameters", "PreparationSemanticParameters", type(value).__name__
        )
    validate_semantic_parameters(value)


def _require_runtime(value: PreparationExecutionRuntime | str) -> None:
    if type(value) is not PreparationExecutionRuntime:
        raise_mismatch("runtime", "PreparationExecutionRuntime", type(value).__name__)
    validate_runtime_metadata(value)


def _require_enum(field: str, value: StrEnum, enum: type[StrEnum]) -> None:
    if type(value) is not enum:
        raise_mismatch(
            field, "/".join(item.value for item in enum), type(value).__name__
        )


def _require_fit_scopes(receipt: ExecutionReceiptLike) -> None:
    _require_enum(
        "canonical_materialization_fit_scope",
        receipt.canonical_materialization_fit_scope,
        PreparationFitScope,
    )
    _require_enum("prepared_fit_scope", receipt.prepared_fit_scope, PreparationFitScope)
    if receipt.canonical_materialization_fit_scope != PreparationFitScope.NONE:
        raise_mismatch(
            "canonical_materialization_fit_scope",
            "none",
            str(receipt.canonical_materialization_fit_scope),
        )
    if receipt.prepared_fit_scope != PreparationFitScope.TRAIN_ONLY:
        raise_mismatch(
            "prepared_fit_scope", "train_only", str(receipt.prepared_fit_scope)
        )


def _require_attachment(value: MetadataConcordanceAttachment | str | None) -> None:
    if value is None:
        return
    if type(value) is not MetadataConcordanceAttachment:
        raise_mismatch(
            "metadata_concordance",
            "MetadataConcordanceAttachment or none",
            type(value).__name__,
        )
    _require_enum(
        "metadata_concordance_status", value.status, MetadataConcordanceAttachmentStatus
    )
    _ = validate_sha256(
        field="metadata_concordance_identity",
        value=value.report_identity,
        prefixed=False,
    )


def _require_execution_scalars(receipt: ExecutionReceiptLike) -> None:
    if type(receipt.dataset) is not DatasetSnapshotIdentity:
        raise_mismatch(
            "dataset", "DatasetSnapshotIdentity", type(receipt.dataset).__name__
        )
    if type(receipt.seed) is not int or receipt.seed < 0:
        raise_mismatch("seed", "non-negative integer", type(receipt.seed).__name__)
    parent_ids = receipt.materialization_parent_artifact_identities
    if type(parent_ids) is not tuple:
        raise_mismatch(
            "materialization_parent_artifact_identities",
            "tuple of artifact identities",
            type(parent_ids).__name__,
        )
    if not parent_ids:
        raise_mismatch(
            "materialization_parent_artifact_identities", "at least one parent", "empty"
        )
    if len(set(parent_ids)) != len(parent_ids):
        raise_mismatch(
            "materialization_parent_artifact_identities",
            "unique artifact identities",
            "duplicate",
        )
    for field, value in (
        ("dataset_name", receipt.dataset.name),
        ("dataset_version", receipt.dataset.version),
        ("task", receipt.task),
        ("preparation_protocol_id", receipt.preparation_protocol_id),
        ("preparation_protocol_version", receipt.preparation_protocol_version),
        ("split_protocol", receipt.split_protocol),
    ):
        _ = validate_safe_identifier(field=field, value=value)
    for field, value, prefixed in (
        ("input_artifact_identity", receipt.input_artifact_identity, True),
        ("canonical_artifact_identity", receipt.canonical_artifact_identity, True),
        (
            "preparation_protocol_semantic_identity",
            receipt.preparation_protocol_semantic_identity,
            False,
        ),
        ("split_assignment_identity", receipt.split_assignment_identity, False),
        (
            "prepared_benchmark_receipt_identity",
            receipt.prepared_benchmark_receipt_identity,
            False,
        ),
        (
            "prepared_output_artifact_identity",
            receipt.prepared_output_artifact_identity,
            False,
        ),
        ("fitted_state_identity", receipt.fitted_state_identity, False),
    ):
        _ = validate_sha256(field=field, value=value, prefixed=prefixed)
    for parent_identity in parent_ids:
        _ = validate_sha256(
            field="materialization_parent_artifact_identity",
            value=parent_identity,
            prefixed=True,
        )
