"""Typed outcomes for dataset-specific split capability evidence."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import assert_never

from bioml_data._artifact_types import ArtifactId, TransformProtocolId
from bioml_data._domain import (
    DatasetSnapshotIdentity,
    ProtocolId,
    SplitEvidenceBasis,
    SplitProtocolCompatibilityRoleError,
    SplitProtocolRole,
    SplitStrategy,
    TaskId,
    normalize_split_contract_role,
)
from bioml_data._split_contract_errors import (
    SplitEvidenceTypeCompatibilityError,
    require_exact_bool,
    require_exact_split_enum,
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
        role = require_exact_split_enum(
            self.role,
            expected_type=SplitProtocolRole,
            protocol=self.scope.protocol,
            field="role",
        )
        basis = require_exact_split_enum(
            self.basis,
            expected_type=SplitEvidenceBasis,
            protocol=self.scope.protocol,
            field="basis",
        )
        evidence_type = require_exact_split_enum(
            self.evidence_type,
            expected_type=SplitEvidenceType,
            protocol=self.scope.protocol,
            field="evidence type",
        )
        if basis is not None and role is not None:
            raise SplitProtocolCompatibilityRoleError(
                protocol=self.scope.protocol,
                role=role,
            )
        object.__setattr__(
            self,
            "evidence_type",
            _normalize_legacy_evidence_type(
                protocol=self.scope.protocol,
                basis=basis,
                evidence_type=evidence_type,
            ),
        )


@dataclass(frozen=True, slots=True)
class SplitCapability:
    """Machine-readable contract for one supported split protocol."""

    dataset: DatasetSnapshotIdentity
    task: TaskId
    protocol: ProtocolId
    role: SplitProtocolRole | None
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

    def __post_init__(self) -> None:
        """Parse closed semantic inputs and normalize the active role view."""
        is_canary = require_exact_bool(self.is_canary, protocol=self.protocol)
        role = require_exact_split_enum(
            self.role,
            expected_type=SplitProtocolRole,
            protocol=self.protocol,
            field="role",
        )
        basis = require_exact_split_enum(
            self.basis,
            expected_type=SplitEvidenceBasis,
            protocol=self.protocol,
            field="basis",
        )
        _ = require_exact_split_enum(
            self.strategy,
            expected_type=SplitStrategy,
            protocol=self.protocol,
            field="strategy",
        )
        evidence_type = require_exact_split_enum(
            self.evidence_type,
            expected_type=SplitEvidenceType,
            protocol=self.protocol,
            field="evidence type",
        )
        object.__setattr__(self, "is_canary", is_canary)
        object.__setattr__(
            self,
            "role",
            normalize_split_contract_role(
                protocol=self.protocol,
                role=role,
                basis=basis,
                is_canary=is_canary,
            ),
        )
        object.__setattr__(
            self,
            "evidence_type",
            _normalize_legacy_evidence_type(
                protocol=self.protocol,
                basis=basis,
                evidence_type=evidence_type,
            ),
        )


def legacy_evidence_type_for_basis(
    basis: SplitEvidenceBasis,
) -> SplitEvidenceType:
    """Return the deterministic legacy evidence-type projection for one basis."""
    match basis:
        case SplitEvidenceBasis.PACKAGE_DEFINED:
            return SplitEvidenceType.PRODUCT_PROTOCOL
        case (
            SplitEvidenceBasis.LITERATURE_REFERENCE
            | SplitEvidenceBasis.COMMUNITY_REFERENCE
        ):
            return SplitEvidenceType.LITERATURE_REUSE
        case _:
            assert_never(basis)


def _normalize_legacy_evidence_type(
    *,
    protocol: ProtocolId,
    basis: SplitEvidenceBasis | None,
    evidence_type: SplitEvidenceType | None,
) -> SplitEvidenceType | None:
    """Project active evidence basis into a non-authoritative legacy reader."""
    match basis:
        case None:
            return evidence_type
        case SplitEvidenceBasis():
            expected_type = legacy_evidence_type_for_basis(basis)
            match evidence_type:
                case None:
                    return expected_type
                case actual_type if actual_type is expected_type:
                    return expected_type
                case SplitEvidenceType() as actual_type:
                    raise SplitEvidenceTypeCompatibilityError(
                        protocol=protocol,
                        expected_type=expected_type.value,
                        actual_type=actual_type.value,
                    )
                case _:
                    assert_never(evidence_type)
        case _:
            assert_never(basis)
