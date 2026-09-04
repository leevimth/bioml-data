"""Full public-boundary validation and rendering for execution receipts."""

import json
from dataclasses import asdict, dataclass
from hashlib import sha256

from bioml_data._artifacts import ArtifactId, ArtifactReceipt
from bioml_data._dataset_preparation_models import (
    DatasetPreparationOutcome,
    DatasetPreparationReceipt,
)
from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId
from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._preparation_contracts import ExpressionInput, PreparationFitScope
from bioml_data._preparation_execution_models import (
    MetadataConcordanceAttachment,
    PreparationExecutionReceiptIdentity,
    PreparationSemanticParameters,
)
from bioml_data._preparation_execution_receipt_validation import (
    raise_mismatch,
    validate_receipt_structure,
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
