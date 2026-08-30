"""Deterministic leakage audit report assembly."""

from dataclasses import dataclass
from hashlib import sha256

from bioml_data._domain import ProtocolId
from bioml_data._leakage_audit_models import (
    AuditStatus,
    AuditSupport,
    DuplicateSummary,
    LeakageAuditIdentity,
    LeakageAuditReport,
    LeakageAuditRequest,
    OverlapCheck,
)


@dataclass(frozen=True, slots=True)
class LeakageAuditEvidence:
    support: AuditSupport
    status: AuditStatus
    supported_protocols: tuple[ProtocolId, ...]
    duplicates: DuplicateSummary
    checks: tuple[OverlapCheck, ...]


def build_report(
    request: LeakageAuditRequest,
    evidence: LeakageAuditEvidence,
) -> LeakageAuditReport:
    evidence_fields = tuple(
        sorted(
            {
                str(item.column)
                for observation in request.observations
                for item in observation.metadata
            }
        )
    )
    checks_evidence = "|".join(
        "".join(
            (
                f"{check.axis}:{check.status}:{check.coverage.present}/",
                f"{check.coverage.total}:",
                ",".join(check.overlapping_values),
            )
        )
        for check in evidence.checks
    )
    identity_input = "".join(
        (
            f"{request.dataset.name}\0{request.dataset.version}\0",
            f"{request.artifact_identity}\0{request.assignment.protocol}\0",
            f"{request.assignment.assignment_identity}\0{evidence.support}\0",
            f"{evidence.status}\0{checks_evidence}",
        )
    )
    return LeakageAuditReport(
        report_identity=LeakageAuditIdentity(
            sha256(identity_input.encode()).hexdigest()
        ),
        dataset=request.dataset,
        artifact_identity=request.artifact_identity,
        protocol=request.assignment.protocol,
        assignment_identity=request.assignment.assignment_identity,
        support=evidence.support,
        status=evidence.status,
        evidence_fields=evidence_fields,
        supported_protocols=evidence.supported_protocols,
        duplicates=evidence.duplicates,
        checks=evidence.checks,
    )
