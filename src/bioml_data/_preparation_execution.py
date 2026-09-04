"""Build and verify execution receipts from already-produced scientific layers."""

from dataclasses import replace
from hashlib import sha256
from typing import assert_never

from bioml_data._metadata_receipt_validation import validate_receipt_integrity
from bioml_data._preparation_execution_concordance import concordance_attachment
from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_models import (
    ExpressionInput,
    PreparationExecutionReceiptIdentity,
    PreparationFitScope,
    PreparationSemanticParameters,
)
from bioml_data._preparation_execution_receipt import (
    PreparationExecutionReceipt,
    PreparationExecutionRequest,
    preparation_execution_receipt_identity,
)
from bioml_data._preparation_models import (
    PreparedBenchmarkReceipt,
    preparation_protocol_semantic_identity,
)


def record_preparation_execution(
    request: PreparationExecutionRequest,
) -> PreparationExecutionReceipt:
    """Join exact materialization, split, preparation, and evidence receipts."""
    validate_receipt_integrity(request.dataset, request.assignment)
    _validate_context(request)
    receipt = PreparationExecutionReceipt(
        receipt_identity=PreparationExecutionReceiptIdentity(""),
        dataset=request.dataset.snapshot,
        task=request.assignment.task,
        input_artifact_identity=request.input_artifact.artifact_id,
        canonical_artifact_identity=request.materialization.artifact.artifact_id,
        materialization_parent_artifact_identities=tuple(
            item.artifact_id for item in request.materialization.parent_artifacts
        ),
        materialization_outcome=request.materialization.outcome,
        preparation_protocol_id=request.protocol.protocol_id,
        preparation_protocol_version=request.protocol.version,
        preparation_protocol_semantic_identity=request.prepared.protocol_semantic_identity,
        semantic_parameters=_semantic_parameters(request),
        expression_input=_expression_input(request),
        canonical_materialization_fit_scope=PreparationFitScope.NONE,
        prepared_fit_scope=PreparationFitScope.TRAIN_ONLY,
        split_protocol=request.assignment.protocol,
        split_assignment_identity=request.assignment.assignment_identity,
        seed=request.assignment.seed,
        prepared_benchmark_receipt_identity=request.prepared.receipt_identity,
        prepared_output_artifact_identity=request.prepared.output_artifact_identity,
        fitted_state_identity=request.prepared.fitted_state.state_identity,
        runtime=request.runtime,
        metadata_concordance=concordance_attachment(request),
    )
    return replace(
        receipt,
        receipt_identity=preparation_execution_receipt_identity(receipt),
    )


def validate_preparation_execution_receipt(
    receipt: PreparationExecutionReceipt,
) -> None:
    expected = preparation_execution_receipt_identity(receipt)
    if receipt.receipt_identity != expected:
        field = "receipt_identity"
        raise _mismatch(field, str(expected), str(receipt.receipt_identity))


def _validate_context(request: PreparationExecutionRequest) -> None:
    dataset = request.dataset
    input_artifact = request.input_artifact
    materialization = request.materialization
    prepared = request.prepared
    assignment = request.assignment
    protocol = request.protocol
    _require("dataset", dataset.snapshot, assignment.dataset)
    _require(
        "canonical_artifact",
        dataset.artifact.artifact_id,
        materialization.artifact.artifact_id,
    )
    parent_ids = tuple(item.artifact_id for item in materialization.parent_artifacts)
    if input_artifact.artifact_id not in parent_ids:
        field = "input_artifact"
        expected = "a materialization parent"
        raise _mismatch(
            field,
            expected,
            str(input_artifact.artifact_id),
        )
    derivation = materialization.artifact.manifest.derivation
    if derivation is None:
        field = "canonical_derivation"
        expected = "declared transform provenance"
        raise _mismatch(field, expected, "absent")
    _require("canonical_derivation_parents", parent_ids, derivation.parent_artifacts)
    _require(
        "prepared_input_artifact",
        materialization.artifact.artifact_id,
        prepared.input_artifact_identity,
    )
    _require(
        "prepared_split_assignment_identity",
        assignment.assignment_identity,
        prepared.split_assignment_identity,
    )
    _require("prepared_seed", assignment.seed, prepared.seed)
    _require("prepared_protocol_id", protocol.protocol_id, prepared.protocol_id)
    _require("prepared_protocol_version", protocol.version, prepared.protocol_version)
    _require(
        "prepared_protocol_semantic_identity",
        preparation_protocol_semantic_identity(protocol),
        prepared.protocol_semantic_identity,
    )
    _require(
        "fitted_split_assignment_identity",
        assignment.assignment_identity,
        prepared.fitted_state.split_assignment_identity,
    )
    _require("fitted_seed", assignment.seed, prepared.fitted_state.seed)
    _require(
        "fitted_protocol_id", protocol.protocol_id, prepared.fitted_state.protocol_id
    )
    _require(
        "fitted_protocol_version",
        protocol.version,
        prepared.fitted_state.protocol_version,
    )
    _require(
        "fitted_protocol_semantic_identity",
        prepared.protocol_semantic_identity,
        prepared.fitted_state.protocol_semantic_identity,
    )
    _require_prepared_identities(prepared)


def _require_prepared_identities(prepared: PreparedBenchmarkReceipt) -> None:
    output_payload = (
        f"{prepared.input_artifact_identity}\0"
        f"{prepared.fitted_state.independent_artifact_identity}\0"
        f"{prepared.fitted_state.state_identity}\0"
        f"{prepared.protocol_semantic_identity}\0"
        f"{prepared.split_assignment_identity}\0{prepared.seed}"
    )
    expected_output = sha256(output_payload.encode()).hexdigest()
    _require(
        "prepared_output_artifact_identity",
        expected_output,
        prepared.output_artifact_identity,
    )
    receipt_payload = (
        f"{prepared.output_artifact_identity}\0{prepared.protocol_id}\0"
        f"{prepared.protocol_version}\0{prepared.protocol_semantic_identity}\0"
        f"{prepared.seed}"
    )
    _require(
        "prepared_benchmark_receipt_identity",
        sha256(receipt_payload.encode()).hexdigest(),
        prepared.receipt_identity,
    )


def _semantic_parameters(
    request: PreparationExecutionRequest,
) -> PreparationSemanticParameters:
    protocol = request.protocol
    feature_ids = tuple(str(item) for item in protocol.alignment.feature_ids)
    feature_payload = "\0".join(feature_ids)
    selection = protocol.feature_selection
    return PreparationSemanticParameters(
        minimum_cell_count=protocol.qc.minimum_cell_count,
        minimum_feature_cells=protocol.qc.minimum_feature_cells,
        alignment_feature_ids=feature_ids,
        alignment_feature_count=len(feature_ids),
        alignment_feature_identity=sha256(feature_payload.encode()).hexdigest(),
        normalization_target_sum=protocol.normalization.target_sum,
        max_features=None if selection is None else selection.max_features,
    )


def _expression_input(request: PreparationExecutionRequest) -> ExpressionInput:
    materialization = request.materialization
    derivation = materialization.artifact.manifest.derivation
    if derivation is None:
        field = "canonical_derivation"
        expected = "declared transform provenance"
        raise _mismatch(field, expected, "absent")
    values = tuple(
        item.value for item in derivation.parameters if item.name == "expression_input"
    )
    if len(values) != 1:
        field = "expression_input"
        expected = "one declared expression_input"
        raise _mismatch(field, expected, str(values))
    match _parse_expression_input(values[0]):
        case ExpressionInput.RAW_X:
            return ExpressionInput.RAW_X
        case unreachable:
            if unreachable is ExpressionInput.X:
                return ExpressionInput.X
            assert_never(unreachable)


def _parse_expression_input(value: str) -> ExpressionInput:
    """Parse the external manifest value before matching the closed enum."""
    try:
        return ExpressionInput(value)
    except ValueError:
        field = "expression_input"
        expected = "raw.X or X"
        raise _mismatch(field, expected, value) from None


def _require[T](field: str, expected: T, actual: T) -> None:
    if expected != actual:
        raise _mismatch(field, str(expected), str(actual))


def _mismatch(
    field: str,
    expected: str,
    actual: str,
) -> PreparationExecutionReceiptMismatchError:
    return PreparationExecutionReceiptMismatchError(
        field=field,
        expected=expected,
        actual=actual,
    )
