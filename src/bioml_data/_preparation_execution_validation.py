"""Cross-receipt lineage validation for execution receipt construction."""

from hashlib import sha256

from bioml_data._artifacts import ArtifactReceipt
from bioml_data._preparation import prepare_benchmark
from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_models import PreparationSemanticParameters
from bioml_data._preparation_execution_receipt import PreparationExecutionRequest
from bioml_data._preparation_identities import (
    PreparedOutputIdentityInput,
    prepared_benchmark_receipt_identity,
    prepared_output_artifact_identity,
)
from bioml_data._preparation_models import (
    PreparationRequest,
    PreparedBenchmarkReceipt,
    preparation_protocol_semantic_identity,
)


def validate_execution_context(request: PreparationExecutionRequest) -> None:
    """Require that all parent receipts and canonical replay agree exactly."""
    dataset = request.dataset
    input_artifact = request.input_artifact
    materialization = request.materialization
    prepared = request.prepared
    assignment = request.assignment
    protocol = request.protocol
    require("dataset", dataset.snapshot, assignment.dataset)
    require(
        "canonical_artifact_manifest",
        dataset.artifact,
        materialization.artifact.manifest,
    )
    parent_ids = tuple(item.artifact_id for item in materialization.parent_artifacts)
    if input_artifact.artifact_id not in parent_ids:
        field = "input_artifact"
        raise mismatch(
            field, "a materialization parent", str(input_artifact.artifact_id)
        )
    _require_input_parent_manifest(input_artifact, materialization.parent_artifacts)
    derivation = materialization.artifact.manifest.derivation
    if derivation is None:
        field = "canonical_derivation"
        raise mismatch(field, "declared transform provenance", "absent")
    require("canonical_derivation_parents", parent_ids, derivation.parent_artifacts)
    require(
        "prepared_input_artifact",
        materialization.artifact.artifact_id,
        prepared.input_artifact_identity,
    )
    require(
        "prepared_split_assignment_identity",
        assignment.assignment_identity,
        prepared.split_assignment_identity,
    )
    require("prepared_seed", assignment.seed, prepared.seed)
    require("prepared_protocol_id", protocol.protocol_id, prepared.protocol_id)
    require("prepared_protocol_version", protocol.version, prepared.protocol_version)
    require(
        "prepared_protocol_semantic_identity",
        preparation_protocol_semantic_identity(protocol),
        prepared.protocol_semantic_identity,
    )
    require(
        "fitted_split_assignment_identity",
        assignment.assignment_identity,
        prepared.fitted_state.split_assignment_identity,
    )
    require("fitted_seed", assignment.seed, prepared.fitted_state.seed)
    require(
        "fitted_protocol_id", protocol.protocol_id, prepared.fitted_state.protocol_id
    )
    require(
        "fitted_protocol_version",
        protocol.version,
        prepared.fitted_state.protocol_version,
    )
    require(
        "fitted_protocol_semantic_identity",
        prepared.protocol_semantic_identity,
        prepared.fitted_state.protocol_semantic_identity,
    )
    _require_prepared_identities(prepared)
    _require_canonical_prepared_replay(request)


def _require_input_parent_manifest(
    input_artifact: ArtifactReceipt,
    parents: tuple[ArtifactReceipt, ...],
) -> None:
    """Bind the consumed input receipt's complete provenance to its parent slot."""
    matches = tuple(
        item for item in parents if item.artifact_id == input_artifact.artifact_id
    )
    if len(matches) != 1:
        field = "input_artifact_parent"
        raise mismatch(field, "one matching parent", str(len(matches)))
    require("input_artifact_manifest", input_artifact.manifest, matches[0].manifest)


def semantic_parameters(
    request: PreparationExecutionRequest,
) -> PreparationSemanticParameters:
    """Expose bounded, ordered preprocessing parameters in the execution receipt."""
    protocol = request.protocol
    feature_ids = tuple(str(item) for item in protocol.alignment.feature_ids)
    selection = protocol.feature_selection
    return PreparationSemanticParameters(
        minimum_cell_count=protocol.qc.minimum_cell_count,
        minimum_feature_cells=protocol.qc.minimum_feature_cells,
        alignment_feature_ids=feature_ids,
        alignment_feature_count=len(feature_ids),
        alignment_feature_identity=sha256("\0".join(feature_ids).encode()).hexdigest(),
        normalization_target_sum=protocol.normalization.target_sum,
        max_features=None if selection is None else selection.max_features,
    )


def require[T](field: str, expected: T, actual: T) -> None:
    if expected != actual:
        raise mismatch(field, str(expected), str(actual))


def mismatch(
    field: str,
    expected: str,
    actual: str,
) -> PreparationExecutionReceiptMismatchError:
    return PreparationExecutionReceiptMismatchError(
        field=field,
        expected=expected,
        actual=actual,
    )


def _require_prepared_identities(prepared: PreparedBenchmarkReceipt) -> None:
    observation_ids = tuple(item.observation_id for item in prepared.observations)
    if not observation_ids:
        field = "prepared_observations"
        raise mismatch(field, "at least one observation", "empty")
    if len(observation_ids) != len(set(observation_ids)):
        field = "prepared_observations"
        raise mismatch(field, "unique observation ids", "duplicate")
    expected_output = prepared_output_artifact_identity(
        PreparedOutputIdentityInput(
            input_artifact_identity=prepared.input_artifact_identity,
            independent_artifact_identity=prepared.fitted_state.independent_artifact_identity,
            fitted_state=prepared.fitted_state,
            protocol_semantic_identity=prepared.protocol_semantic_identity,
            split_assignment_identity=prepared.split_assignment_identity,
            seed=prepared.seed,
            observations=prepared.observations,
        )
    )
    require(
        "prepared_output_artifact_identity",
        expected_output,
        prepared.output_artifact_identity,
    )
    require(
        "prepared_benchmark_receipt_identity",
        prepared_benchmark_receipt_identity(prepared),
        prepared.receipt_identity,
    )


def _require_canonical_prepared_replay(request: PreparationExecutionRequest) -> None:
    expected = prepare_benchmark(
        PreparationRequest(
            dataset=request.dataset,
            protocol=request.protocol,
            split=request.assignment,
            seed=request.assignment.seed,
        )
    )
    actual = request.prepared
    require("fitted_preparation_state", expected.fitted_state, actual.fitted_state)
    require("prepared_observations", expected.observations, actual.observations)
    require(
        "prepared_output_artifact_identity",
        expected.output_artifact_identity,
        actual.output_artifact_identity,
    )
    require(
        "prepared_benchmark_receipt_identity",
        expected.receipt_identity,
        actual.receipt_identity,
    )
