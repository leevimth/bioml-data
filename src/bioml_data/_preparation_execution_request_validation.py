"""Typed nested-container parsing for execution recording requests."""

from bioml_data._artifact_derivation import ArtifactDerivationParameter
from bioml_data._artifacts import ArtifactDerivation, ArtifactManifest, ArtifactReceipt
from bioml_data._dataset_preparation_models import DatasetPreparationReceipt
from bioml_data._metadata_concordance import (
    MetadataComparison,
    MetadataConcordanceReport,
    MetadataPartitionReport,
)
from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_receipt import PreparationExecutionRequest
from bioml_data._preparation_execution_runtime import PreparationExecutionRuntime
from bioml_data._preparation_execution_tokens import validate_safe_identifier
from bioml_data._preparation_models import (
    PreparationProtocol,
    PreparedBenchmarkReceipt,
    validate_prepared_observations,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import SplitAssignmentReceipt


def validate_execution_request_structure(
    request: PreparationExecutionRequest,
) -> None:
    """Parse exact request roots before accessing nested scientific fields."""
    validate_execution_request_roots(request)
    _artifact_receipt("request_input_artifact", request.input_artifact)
    _artifact_receipt(
        "request_materialization_artifact", request.materialization.artifact
    )
    _manifest("request_dataset_manifest", request.dataset.artifact)
    _validate_execution_request_nested_tuples(request)


def validate_execution_request_roots(
    request: PreparationExecutionRequest,
) -> None:
    """Parse the outer request and fields before any other boundary accesses."""
    if type(request) is not PreparationExecutionRequest:
        _mismatch(
            "execution_request", "PreparationExecutionRequest", type(request).__name__
        )
    _root("request_dataset", request.dataset, CanonicalSingleCellDataset)
    _root("request_input_artifact", request.input_artifact, ArtifactReceipt)
    _root(
        "request_materialization",
        request.materialization,
        DatasetPreparationReceipt,
    )
    _root("request_prepared", request.prepared, PreparedBenchmarkReceipt)
    _root("request_assignment", request.assignment, SplitAssignmentReceipt)
    _root("request_protocol", request.protocol, PreparationProtocol)
    _root("request_runtime", request.runtime, PreparationExecutionRuntime)
    report = request.concordance
    if report is not None and type(report) is not MetadataConcordanceReport:
        _mismatch(
            "request_concordance",
            "MetadataConcordanceReport or none",
            type(report).__name__,
        )


def _validate_execution_request_nested_tuples(
    request: PreparationExecutionRequest,
) -> None:
    """Parse every nested tuple crossing the public execution-recording boundary."""
    _string_tuple(
        "protocol_alignment_feature_ids", request.protocol.alignment.feature_ids
    )
    _string_tuple(
        "fitted_training_observation_ids",
        request.prepared.fitted_state.training_observation_ids,
    )
    _string_tuple(
        "fitted_selected_feature_ids",
        request.prepared.fitted_state.selected_feature_ids,
    )
    validate_prepared_observations(request.prepared.observations)
    _derivation("dataset_canonical_derivation", request.dataset.artifact.derivation)
    _derivation(
        "canonical_derivation",
        request.materialization.artifact.manifest.derivation,
    )
    parents = _typed_tuple(
        "materialization_parent_artifacts",
        request.materialization.parent_artifacts,
        ArtifactReceipt,
    )
    for parent in parents:
        _artifact_receipt("materialization_parent_artifact", parent)
    report = request.concordance
    if report is not None:
        _concordance_report(report)


def _root[T](field: str, value: T, expected_type: type[T]) -> None:
    """Require an exact root type before dereferencing a public request field."""
    if type(value) is not expected_type:
        _mismatch(field, expected_type.__name__, type(value).__name__)


def _artifact_receipt(field: str, receipt: ArtifactReceipt) -> None:
    """Parse a receipt and manifest before any provenance dereference."""
    _root(field, receipt, ArtifactReceipt)
    _manifest(f"{field}_manifest", receipt.manifest)


def _manifest(field: str, manifest: ArtifactManifest) -> None:
    """Require an exact artifact manifest before reading its derivation."""
    _root(field, manifest, ArtifactManifest)


def _derivation(field: str, value: ArtifactDerivation | None) -> None:
    """Parse declared provenance without traversing a hostile parameter tuple."""
    if value is None:
        return
    if type(value) is not ArtifactDerivation:
        _mismatch(field, "ArtifactDerivation or none", type(value).__name__)
    _string_tuple(f"{field}_parents", value.parent_artifacts)
    _ = _typed_tuple(
        f"{field}_parameters",
        value.parameters,
        ArtifactDerivationParameter,
    )


def _concordance_report(report: MetadataConcordanceReport) -> None:
    """Parse nested evidence summaries before status replay or aggregation."""
    _ = _typed_tuple(
        "concordance_dataset_comparisons",
        report.dataset_comparisons,
        MetadataComparison,
    )
    partitions = _typed_tuple(
        "concordance_partition_reports",
        report.partition_reports,
        MetadataPartitionReport,
    )
    _string_tuple("concordance_cross_partition_groups", report.cross_partition_groups)
    for partition in partitions:
        _string_tuple("concordance_partition_group_ids", partition.group_ids)
        _string_tuple(
            "concordance_partition_held_out_groups",
            partition.held_out_groups,
        )
        _ = _typed_tuple(
            "concordance_partition_comparisons",
            partition.comparisons,
            MetadataComparison,
        )


def _string_tuple(field: str, values: tuple[str, ...]) -> None:
    """Require an exact tuple of safe identifier-like scientific labels."""
    if type(values) is not tuple:
        _mismatch(field, "tuple of safe identifiers", type(values).__name__)
    for value in values:
        _ = validate_safe_identifier(field=field, value=value)


def _typed_tuple[T](
    field: str,
    values: tuple[T, ...],
    item_type: type[T],
) -> tuple[T, ...]:
    """Require exact tuple and item runtime types before attribute traversal."""
    if type(values) is not tuple:
        _mismatch(field, f"tuple of {item_type.__name__} items", type(values).__name__)
    for value in values:
        if type(value) is not item_type:
            _mismatch(field, f"{item_type.__name__} items", type(value).__name__)
    return values


def _mismatch(field: str, expected: str, actual: str) -> None:
    raise PreparationExecutionReceiptMismatchError(
        field=field,
        expected=expected,
        actual=actual,
    )
