"""Typed nested-container parsing for execution recording requests."""

from typing import TYPE_CHECKING

from bioml_data._artifact_derivation import ArtifactDerivationParameter
from bioml_data._artifacts import ArtifactDerivation, ArtifactReceipt
from bioml_data._metadata_concordance import (
    MetadataComparison,
    MetadataConcordanceReport,
    MetadataPartitionReport,
)
from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_tokens import validate_safe_identifier
from bioml_data._preparation_models import validate_prepared_observations

if TYPE_CHECKING:
    from bioml_data._preparation_execution_receipt import PreparationExecutionRequest


def validate_execution_request_nested_tuples(
    request: "PreparationExecutionRequest",
) -> None:
    """Parse every tuple crossing the public execution-recording boundary."""
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
    _ = _typed_tuple(
        "materialization_parent_artifacts",
        request.materialization.parent_artifacts,
        ArtifactReceipt,
    )
    report = request.concordance
    if report is not None:
        _concordance_report(report)


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
