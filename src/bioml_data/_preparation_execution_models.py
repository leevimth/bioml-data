"""Immutable, path-free scientific preparation-execution receipts."""

import json
from dataclasses import asdict, dataclass
from enum import StrEnum, unique
from hashlib import sha256
from typing import NewType, final, override

from bioml_data._artifacts import ArtifactId, ArtifactReceipt
from bioml_data._dataset_preparation_models import (
    DatasetPreparationOutcome,
    DatasetPreparationReceipt,
)
from bioml_data._domain import DatasetSnapshotIdentity, ProtocolId, TaskId
from bioml_data._metadata_concordance import MetadataConcordanceReport
from bioml_data._preparation_models import (
    PreparationProtocol,
    PreparationReceiptIdentity,
    PreparationStateIdentity,
    PreparedArtifactIdentity,
    PreparedBenchmarkReceipt,
)
from bioml_data._single_cell import CanonicalSingleCellDataset
from bioml_data._split import AssignmentIdentity, SplitAssignmentReceipt

PreparationExecutionReceiptIdentity = NewType(
    "PreparationExecutionReceiptIdentity", str
)


@unique
class ExpressionInput(StrEnum):
    """Matrix selected by the canonical dataset transform."""

    RAW_X = "raw.X"
    X = "X"


@unique
class PreparationFitScope(StrEnum):
    """Scope from which a preparation stage may learn statistics."""

    NONE = "none"
    TRAIN_ONLY = "train_only"


@unique
class RuntimeComponent(StrEnum):
    """Bounded runtime components relevant to single-cell preparation."""

    ANNDATA = "anndata"
    NUMPY = "numpy"
    SCIPY = "scipy"


@unique
class MetadataConcordanceAttachmentStatus(StrEnum):
    """Collapsed status of a full optional concordance report."""

    MATCH = "match"
    MISMATCH = "mismatch"
    NOT_REPORTED = "not_reported"
    MIXED = "mixed"


@final
class PreparationExecutionReceiptMismatchError(Exception):
    """Raised when execution layers cannot be joined into one receipt."""

    __slots__ = ("actual", "expected", "field")

    field: str
    expected: str
    actual: str

    def __init__(self, field: str, expected: str, actual: str) -> None:
        super().__init__(field, expected, actual)
        self.field = field
        self.expected = expected
        self.actual = actual

    @override
    def __str__(self) -> str:
        return (
            f"preparation execution receipt mismatch for {self.field}: "
            f"expected {self.expected!r}, received {self.actual!r}"
        )


@dataclass(frozen=True, slots=True)
class DependencyVersion:
    """One bounded, named runtime dependency version."""

    component: RuntimeComponent
    version: str

    def __post_init__(self) -> None:
        """Reject empty or whitespace-normalized runtime versions."""
        if not self.version or self.version != self.version.strip():
            raise PreparationExecutionReceiptMismatchError(
                field="dependency_version",
                expected="non-empty normalized version",
                actual=self.version,
            )


@dataclass(frozen=True, slots=True)
class PreparationExecutionRuntime:
    """Toolkit plus a bounded, canonically ordered dependency version set."""

    toolkit_version: str
    dependencies: tuple[DependencyVersion, ...]

    def __post_init__(self) -> None:
        """Keep runtime metadata small, normalized, unique, and deterministic."""
        components = tuple(item.component for item in self.dependencies)
        if (
            not self.toolkit_version
            or self.toolkit_version != self.toolkit_version.strip()
        ):
            raise PreparationExecutionReceiptMismatchError(
                field="toolkit_version",
                expected="non-empty normalized version",
                actual=self.toolkit_version,
            )
        if components != tuple(sorted(components, key=str)):
            raise PreparationExecutionReceiptMismatchError(
                field="runtime_dependencies",
                expected="sorted by component",
                actual=str(components),
            )
        if len(components) != len(set(components)):
            raise PreparationExecutionReceiptMismatchError(
                field="runtime_dependencies",
                expected="unique components",
                actual=str(components),
            )


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
class PreparationSemanticParameters:
    """Compact semantic parameters, excluding paths and host-local state."""

    minimum_cell_count: int
    minimum_feature_cells: int
    alignment_feature_identity: str
    normalization_target_sum: float
    max_features: int | None


@dataclass(frozen=True, slots=True)
class MetadataConcordanceAttachment:
    """Identity and aggregate outcome for an attached concordance report."""

    report_identity: str
    status: MetadataConcordanceAttachmentStatus


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
        """Return canonical JSON without filesystem or host-local fields."""
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def preparation_execution_receipt_identity(
    receipt: PreparationExecutionReceipt,
) -> PreparationExecutionReceiptIdentity:
    """Hash every rendered scientific field except its derived receipt identity."""
    payload = asdict(receipt)
    del payload["receipt_identity"]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return PreparationExecutionReceiptIdentity(sha256(encoded.encode()).hexdigest())
