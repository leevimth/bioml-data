"""Build and verify execution receipts from already-produced scientific layers."""

from dataclasses import replace

from bioml_data._metadata_receipt_validation import validate_receipt_integrity
from bioml_data._preparation_contracts import ExpressionInput, PreparationFitScope
from bioml_data._preparation_execution_concordance import concordance_attachment
from bioml_data._preparation_execution_models import PreparationExecutionReceiptIdentity
from bioml_data._preparation_execution_receipt import (
    PreparationExecutionReceipt,
    PreparationExecutionRequest,
    ReceiptRoot,
    preparation_execution_receipt_identity,
    validate_preparation_execution_receipt_structure,
)
from bioml_data._preparation_execution_request_validation import (
    validate_execution_request_roots,
)
from bioml_data._preparation_execution_validation import (
    mismatch,
    semantic_parameters,
    validate_execution_context,
)


def record_preparation_execution(
    request: PreparationExecutionRequest,
) -> PreparationExecutionReceipt:
    """Join exact materialization, split, preparation, and evidence receipts."""
    validate_execution_request_roots(request)
    validate_receipt_integrity(request.dataset, request.assignment)
    validate_execution_context(request)
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
        semantic_parameters=semantic_parameters(request),
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
    receipt: ReceiptRoot,
) -> None:
    validated = validate_preparation_execution_receipt_structure(receipt)
    expected = preparation_execution_receipt_identity(validated)
    if validated.receipt_identity != expected:
        field = "receipt_identity"
        raise mismatch(field, "matching receipt identity", "mismatch")


def _expression_input(request: PreparationExecutionRequest) -> ExpressionInput:
    materialization = request.materialization
    derivation = materialization.artifact.manifest.derivation
    if derivation is None:
        field = "canonical_derivation"
        expected = "declared transform provenance"
        raise mismatch(field, expected, "absent")
    values = tuple(
        item.value for item in derivation.parameters if item.name == "expression_input"
    )
    if len(values) != 1:
        field = "expression_input"
        expected = "one declared expression_input"
        raise mismatch(field, expected, "invalid declaration")
    return _parse_expression_input(values[0])


def _parse_expression_input(value: str) -> ExpressionInput:
    """Parse the external manifest value before matching the closed enum."""
    try:
        return ExpressionInput(value)
    except ValueError:
        field = "expression_input"
        expected = "raw.X"
        raise mismatch(field, expected, value) from None
