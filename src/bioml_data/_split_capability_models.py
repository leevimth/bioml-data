"""Typed outcomes for dataset-specific split capability evidence."""

from dataclasses import dataclass, field
from enum import StrEnum, unique

from bioml_data._artifact_types import ArtifactId, TransformProtocolId
from bioml_data._domain import (
    DatasetSnapshotIdentity,
    ProtocolId,
    SplitEvidenceBasis,
    SplitProtocolCompatibilityRoleError,
    SplitProtocolRole,
    SplitStrategy,
    TaskId,
)
from bioml_data._split_contract_errors import (
    require_exact_bool,
    require_exact_split_enum,
    require_split_contract_field,
)


@unique
class SplitEvidenceType(StrEnum):
    """Deprecated evidence-type vocabulary retained for reader compatibility."""

    LITERATURE_REUSE = "literature_reuse"
    COMPARATIVE_EVIDENCE = "comparative_evidence"
    PRODUCT_PROTOCOL = "product_protocol"


@unique
class SplitCapabilityAvailability(StrEnum):
    """Assessment state independent of protocol role or audit result."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class SplitArtifactScope:
    """Exact raw artifact and transform to which split evidence applies."""

    source_artifact: ArtifactId
    transform_protocol: TransformProtocolId

    @property
    def parent_artifacts(self) -> tuple[ArtifactId, ...]:
        """Return the exact ordered derivation parents required by this scope."""
        return (self.source_artifact,)


@dataclass(frozen=True, slots=True)
class SplitEvidenceScope:
    """Scientific scope preventing evidence reuse across incompatible contracts."""

    dataset: DatasetSnapshotIdentity
    artifact: SplitArtifactScope
    task: TaskId
    protocol: ProtocolId


@dataclass(frozen=True, slots=True)
class SplitEvidenceCitation:
    """Human-readable provenance for a split-role claim."""

    title: str
    uri: str


@dataclass(frozen=True, slots=True)
class SplitProtocolEvidence:
    """One evidence-basis claim, its source, and its interpretation limits."""

    scope: SplitEvidenceScope
    role: SplitProtocolRole | None
    evidence_type: SplitEvidenceType | None
    citations: tuple[SplitEvidenceCitation, ...]
    fit_scope: str
    leakage_caveat: str
    basis: SplitEvidenceBasis | None = None

    def __post_init__(self) -> None:
        """Keep active evidence basis records free of legacy role claims."""
        _ = require_exact_split_enum(
            self.role,
            expected_type=SplitProtocolRole,
            protocol=self.scope.protocol,
            field="role",
        )
        _ = require_exact_split_enum(
            self.basis,
            expected_type=SplitEvidenceBasis,
            protocol=self.scope.protocol,
            field="basis",
        )
        if self.basis is not None and self.role is not None:
            raise SplitProtocolCompatibilityRoleError(
                protocol=self.scope.protocol,
                role=self.role,
            )


@dataclass(frozen=True, slots=True, init=False)
class SplitCapability:
    """Machine-readable contract for one supported split protocol."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId
    evidence_type: SplitEvidenceType | None
    artifact: SplitArtifactScope
    evidence: tuple[SplitProtocolEvidence, ...]
    held_out_axis: str
    leakage_unit: str
    required_columns: tuple[str, ...]
    grouping_column: str
    basis: SplitEvidenceBasis | None = None
    strategy: SplitStrategy | None = None
    evaluation_target: str = ""
    is_canary: bool = False
    _legacy_role: SplitProtocolRole | None = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __init__(  # noqa: PLR0913, PLR0917 — preserves the legacy dataclass constructor.
        self,
        dataset: DatasetSnapshotIdentity | None = None,
        task: TaskId | None = None,
        protocol: ProtocolId | None = None,
        role: SplitProtocolRole | None = None,
        evidence_type: SplitEvidenceType | None = None,
        artifact: SplitArtifactScope | None = None,
        evidence: tuple[SplitProtocolEvidence, ...] | None = None,
        held_out_axis: str | None = None,
        leakage_unit: str | None = None,
        required_columns: tuple[str, ...] | None = None,
        grouping_column: str | None = None,
        basis: SplitEvidenceBasis | None = None,
        strategy: SplitStrategy | None = None,
        evaluation_target: str = "",
        is_canary: bool = False,
    ) -> None:
        """Create a split capability while retaining legacy role inputs."""
        resolved_dataset = require_split_contract_field(dataset, field="dataset")
        resolved_task = require_split_contract_field(task, field="task")
        resolved_protocol = require_split_contract_field(protocol, field="protocol")
        resolved_artifact = require_split_contract_field(artifact, field="artifact")
        resolved_evidence = require_split_contract_field(evidence, field="evidence")
        resolved_held_out_axis = require_split_contract_field(
            held_out_axis,
            field="held-out axis",
        )
        resolved_leakage_unit = require_split_contract_field(
            leakage_unit,
            field="leakage unit",
        )
        resolved_required_columns = require_split_contract_field(
            required_columns,
            field="required columns",
        )
        resolved_grouping_column = require_split_contract_field(
            grouping_column,
            field="grouping column",
        )
        resolved_is_canary = require_exact_bool(
            is_canary,
            protocol=resolved_protocol,
        )
        resolved_role = require_exact_split_enum(
            role,
            expected_type=SplitProtocolRole,
            protocol=resolved_protocol,
            field="role",
        )
        resolved_basis = require_exact_split_enum(
            basis,
            expected_type=SplitEvidenceBasis,
            protocol=resolved_protocol,
            field="basis",
        )
        resolved_strategy = require_exact_split_enum(
            strategy,
            expected_type=SplitStrategy,
            protocol=resolved_protocol,
            field="strategy",
        )
        if resolved_basis is not None and resolved_role is not None:
            raise SplitProtocolCompatibilityRoleError(
                protocol=resolved_protocol,
                role=resolved_role,
            )
        for field_name, value in (
            ("dataset", resolved_dataset),
            ("task", resolved_task),
            ("protocol", resolved_protocol),
            ("evidence_type", evidence_type),
            ("artifact", resolved_artifact),
            ("evidence", resolved_evidence),
            ("held_out_axis", resolved_held_out_axis),
            ("leakage_unit", resolved_leakage_unit),
            ("required_columns", resolved_required_columns),
            ("grouping_column", resolved_grouping_column),
            ("basis", resolved_basis),
            ("strategy", resolved_strategy),
            ("evaluation_target", evaluation_target),
            ("is_canary", resolved_is_canary),
            ("_legacy_role", resolved_role),
        ):
            object.__setattr__(self, field_name, value)

    @property
    def role(self) -> SplitProtocolRole | None:
        """Return the deprecated role view derived from active package usage."""
        if self.basis is not None:
            return SplitProtocolRole.CANARY if self.is_canary else None
        return self._legacy_role
