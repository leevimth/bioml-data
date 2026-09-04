"""Optional metadata-concordance bindings for execution receipts."""

from typing import assert_never

from bioml_data._metadata_concordance_models import MetadataConcordance
from bioml_data._metadata_concordance_reporting import metadata_concordance_identity
from bioml_data._preparation_execution_errors import (
    PreparationExecutionReceiptMismatchError,
)
from bioml_data._preparation_execution_models import (
    MetadataConcordanceAttachment,
    MetadataConcordanceAttachmentStatus,
    PreparationExecutionRequest,
)


def concordance_attachment(
    request: PreparationExecutionRequest,
) -> MetadataConcordanceAttachment | None:
    """Bind optional publication metadata evidence to the exact canonical scope."""
    concordance = request.concordance
    if concordance is None:
        return None
    _require("concordance_dataset", request.dataset.snapshot, concordance.scope.dataset)
    _require("concordance_task", request.assignment.task, concordance.scope.task)
    _require(
        "concordance_protocol", request.assignment.protocol, concordance.scope.protocol
    )
    derivation = request.materialization.artifact.manifest.derivation
    if derivation is None:
        field = "canonical_derivation"
        expected = "declared transform provenance"
        raise _mismatch(field, expected, "absent")
    _require(
        "concordance_source_artifacts",
        derivation.parent_artifacts,
        concordance.scope.artifact.parent_artifacts,
    )
    _require(
        "concordance_transform_protocol",
        derivation.transform_protocol,
        concordance.scope.artifact.transform_protocol,
    )
    _require(
        "concordance_assignment_identity",
        request.assignment.assignment_identity,
        concordance.assignment_identity,
    )
    statuses = tuple(
        item.status
        for item in (
            *concordance.dataset_comparisons,
            *tuple(
                comparison
                for report in concordance.partition_reports
                for comparison in report.comparisons
            ),
        )
    )
    return MetadataConcordanceAttachment(
        report_identity=metadata_concordance_identity(concordance),
        status=_concordance_status(statuses),
    )


def _concordance_status(
    statuses: tuple[MetadataConcordance, ...],
) -> MetadataConcordanceAttachmentStatus:
    has_match = False
    has_not_reported = False
    for item in statuses:
        match item:
            case MetadataConcordance.MISMATCH:
                return MetadataConcordanceAttachmentStatus.MISMATCH
            case MetadataConcordance.MATCH:
                has_match = True
            case unreachable:
                if unreachable is MetadataConcordance.NOT_REPORTED:
                    has_not_reported = True
                    continue
                assert_never(unreachable)
    if has_match and has_not_reported:
        return MetadataConcordanceAttachmentStatus.MIXED
    if has_match:
        return MetadataConcordanceAttachmentStatus.MATCH
    return MetadataConcordanceAttachmentStatus.NOT_REPORTED


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
