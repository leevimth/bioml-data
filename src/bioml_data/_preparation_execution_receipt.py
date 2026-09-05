"""Full public-boundary validation and rendering for execution receipts."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Final

from bioml_data._artifacts import ArtifactId, ArtifactReceipt
from bioml_data._dataset_preparation_models import (
    DatasetPreparationOutcome,
    DatasetPreparationReceipt,
)
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    TaskId,
)
from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._preparation_contracts import ExpressionInput, PreparationFitScope
from bioml_data._preparation_execution_json import (
    PreparationExecutionReceiptJsonPayload,
    parse_preparation_execution_receipt_payload,
)
from bioml_data._preparation_execution_models import (
    MetadataConcordanceAttachment,
    MetadataConcordanceAttachmentStatus,
    PreparationExecutionReceiptIdentity,
    PreparationSemanticParameters,
)
from bioml_data._preparation_execution_receipt_validation import (
    raise_mismatch,
    validate_receipt_structure,
)
from bioml_data._preparation_execution_runtime import (
    DependencyVersion,
    PreparationExecutionRuntime,
    RuntimeComponent,
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

RECEIPT_FORMAT_VERSION: Final = "v1"


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
        expected = preparation_execution_receipt_identity(self)
        if self.receipt_identity != expected:
            raise_mismatch("receipt_identity", "matching receipt identity", "mismatch")
        return _canonical_json_unchecked(self, include_receipt_identity=True)

    @staticmethod
    def from_json(payload: str | bytes) -> "PreparationExecutionReceipt":
        """Parse a supported versioned JSON receipt at the public boundary."""
        return preparation_execution_receipt_from_json(payload)


type ReceiptRoot = PreparationExecutionReceipt | str | list[str] | dict[str, str] | None


def preparation_execution_receipt_identity(
    receipt: ReceiptRoot,
) -> PreparationExecutionReceiptIdentity:
    """Hash every validated scientific field except its derived receipt identity."""
    validated = validate_preparation_execution_receipt_structure(receipt)
    encoded = _canonical_json_unchecked(validated, include_receipt_identity=False)
    return PreparationExecutionReceiptIdentity(sha256(encoded.encode()).hexdigest())


def validate_preparation_execution_receipt_structure(
    receipt: ReceiptRoot,
) -> PreparationExecutionReceipt:
    """Reject hostile rehashed nested values before identity or JSON rendering."""
    if type(receipt) is not PreparationExecutionReceipt:
        raise_mismatch(
            "preparation_execution_receipt",
            "exact PreparationExecutionReceipt",
            type(receipt).__name__,
        )
    validate_receipt_structure(receipt)
    return receipt


def preparation_execution_receipt_from_json(
    payload: str | bytes,
) -> PreparationExecutionReceipt:
    """Deserialize one bounded v1 JSON receipt and verify its claimed identity."""
    decoded = parse_preparation_execution_receipt_payload(payload)
    receipt = _receipt_from_payload(decoded)
    expected = preparation_execution_receipt_identity(receipt)
    if receipt.receipt_identity != expected:
        raise_mismatch("receipt_identity", "matching receipt identity", "mismatch")
    return receipt


def _receipt_from_payload(
    payload: PreparationExecutionReceiptJsonPayload,
) -> PreparationExecutionReceipt:
    """Construct domain values after the JSON layer has closed the raw shape."""
    semantic = payload.semantic_parameters
    metadata = payload.metadata_concordance
    return PreparationExecutionReceipt(
        receipt_identity=PreparationExecutionReceiptIdentity(payload.receipt_identity),
        dataset=DatasetSnapshotIdentity(
            name=DatasetName(payload.dataset.name),
            version=DatasetVersion(payload.dataset.version),
        ),
        task=TaskId(payload.task),
        input_artifact_identity=ArtifactId(payload.input_artifact_identity),
        canonical_artifact_identity=ArtifactId(payload.canonical_artifact_identity),
        materialization_parent_artifact_identities=tuple(
            ArtifactId(value)
            for value in payload.materialization_parent_artifact_identities
        ),
        materialization_outcome=DatasetPreparationOutcome(
            payload.materialization_outcome
        ),
        preparation_protocol_id=payload.preparation_protocol_id,
        preparation_protocol_version=payload.preparation_protocol_version,
        preparation_protocol_semantic_identity=payload.preparation_protocol_semantic_identity,
        semantic_parameters=PreparationSemanticParameters(
            minimum_cell_count=semantic.minimum_cell_count,
            minimum_feature_cells=semantic.minimum_feature_cells,
            alignment_feature_ids=semantic.alignment_feature_ids,
            alignment_feature_count=semantic.alignment_feature_count,
            alignment_feature_identity=semantic.alignment_feature_identity,
            normalization_target_sum=semantic.normalization_target_sum,
            max_features=semantic.max_features,
        ),
        expression_input=ExpressionInput(payload.expression_input),
        canonical_materialization_fit_scope=PreparationFitScope(
            payload.canonical_materialization_fit_scope
        ),
        prepared_fit_scope=PreparationFitScope(payload.prepared_fit_scope),
        split_protocol=ProtocolId(payload.split_protocol),
        split_assignment_identity=AssignmentIdentity(payload.split_assignment_identity),
        seed=payload.seed,
        prepared_benchmark_receipt_identity=PreparationReceiptIdentity(
            payload.prepared_benchmark_receipt_identity
        ),
        prepared_output_artifact_identity=PreparedArtifactIdentity(
            payload.prepared_output_artifact_identity
        ),
        fitted_state_identity=PreparationStateIdentity(payload.fitted_state_identity),
        runtime=PreparationExecutionRuntime(
            toolkit_version=payload.runtime.toolkit_version,
            dependencies=tuple(
                DependencyVersion(
                    component=RuntimeComponent(item.component), version=item.version
                )
                for item in payload.runtime.dependencies
            ),
        ),
        metadata_concordance=(
            None
            if metadata is None
            else MetadataConcordanceAttachment(
                report_identity=metadata.report_identity,
                status=MetadataConcordanceAttachmentStatus(metadata.status),
            )
        ),
    )


def _canonical_json_unchecked(
    receipt: PreparationExecutionReceipt,
    *,
    include_receipt_identity: bool,
) -> str:
    """Render after the public boundary has completed structural validation."""
    payload = asdict(receipt)
    if not include_receipt_identity:
        del payload["receipt_identity"]
    if include_receipt_identity:
        payload = {"receipt_format_version": RECEIPT_FORMAT_VERSION, **payload}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
