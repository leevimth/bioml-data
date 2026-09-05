"""Explicit, non-promoting support-readiness assessment for registrations."""

from typing import Final

from bioml_data._dataset_readiness_models import (
    DatasetReadinessEvidence,
    DatasetReadinessReport,
    ReadinessCitation,
    ReadinessDimension,
    ReadinessEvidence,
    ReadinessField,
    ReadinessFieldStatus,
    ReadinessQualification,
    ReadinessVerdict,
)
from bioml_data._domain import DatasetSnapshotIdentity
from bioml_data.datasets._models import DatasetRegistration
from bioml_data.datasets._split_contract_validation import (
    valid_split_capability_contract_mode,
    valid_split_semantics,
)

_SHA256_ARTIFACT_ID_LENGTH: Final = 71


def assess_dataset_readiness(
    name: str,
    *,
    version: str | None = None,
) -> DatasetReadinessReport:
    """Assess one built-in registration without changing its lifecycle declaration."""
    from bioml_data.datasets._registry import DATASET_REGISTRY  # noqa: PLC0415

    registration = DATASET_REGISTRY.resolve(name, version=version)
    evidence = _BUILTIN_EVIDENCE.get(registration.definition.snapshot, _EMPTY_EVIDENCE)
    return assess_registration_readiness(registration, evidence)


def assess_registration_readiness(
    registration: DatasetRegistration,
    evidence: DatasetReadinessEvidence,
) -> DatasetReadinessReport:
    """Assess a trusted registration against explicit non-code evidence."""
    fields = (
        _checked_field(
            ReadinessDimension.SOURCE_CHECKSUM,
            _source_checksum_ready(registration),
            "registered source URI and SHA-256 artifact scope",
            evidence,
        ),
        _evidence_field(
            ReadinessDimension.RIGHTS,
            evidence.rights,
            evidence,
            requires_license=True,
        ),
        _checked_field(
            ReadinessDimension.CANONICAL_SCHEMA,
            _canonical_schema_ready(registration),
            "registered canonical adapter and artifact scope",
            evidence,
        ),
        _checked_field(
            ReadinessDimension.TASK,
            bool(registration.definition.tasks),
            "at least one registered prediction task",
            evidence,
        ),
        _checked_field(
            ReadinessDimension.DETERMINISTIC_PREPARATION,
            _preparation_ready(registration),
            "registered derivation matches the canonical artifact scope",
            evidence,
        ),
        _checked_field(
            ReadinessDimension.SPLIT,
            _split_ready(registration),
            "registered split semantics, evidence, and citations",
            evidence,
        ),
        _evidence_field(ReadinessDimension.EVALUATION, evidence.evaluation, evidence),
        _evidence_field(
            ReadinessDimension.METADATA_CONCORDANCE,
            evidence.metadata_concordance,
            evidence,
        ),
    )
    return DatasetReadinessReport(
        dataset=registration.definition.snapshot,
        verdict=_verdict(fields),
        fields=fields,
    )


def _source_checksum_ready(registration: DatasetRegistration) -> bool:
    scope = registration.artifact_scope
    return (
        bool(str(registration.definition.source.uri))
        and scope is not None
        and str(scope.source_artifact).startswith("sha256:")
        and len(str(scope.source_artifact)) == _SHA256_ARTIFACT_ID_LENGTH
    )


def _canonical_schema_ready(registration: DatasetRegistration) -> bool:
    return (
        registration.artifact_scope is not None and registration.materialize is not None
    )


def _preparation_ready(registration: DatasetRegistration) -> bool:
    scope = registration.artifact_scope
    derivation = registration.canonical_derivation
    return (
        scope is not None
        and derivation is not None
        and derivation.parent_artifacts == scope.parent_artifacts
        and derivation.transform_protocol == scope.transform_protocol
        and bool(derivation.parameters)
    )


def _split_ready(registration: DatasetRegistration) -> bool:
    definitions = registration.definition.supported_splits
    capabilities = registration.split_capabilities
    return (
        bool(definitions)
        and len(definitions) == len(capabilities)
        and all(
            capability.dataset == registration.definition.snapshot
            and capability.task == definition.task
            and capability.protocol == definition.id
            and capability.artifact == registration.artifact_scope
            and bool(capability.evidence)
            and valid_split_capability_contract_mode(capability)
            and valid_split_semantics(capability)
            and all(item.citations for item in capability.evidence)
            for definition, capability in zip(definitions, capabilities, strict=True)
        )
    )


def _evidence_field(
    dimension: ReadinessDimension,
    item: ReadinessEvidence | None,
    evidence: DatasetReadinessEvidence,
    *,
    requires_license: bool = False,
) -> ReadinessField:
    if item is None:
        return ReadinessField(
            dimension=dimension,
            status=ReadinessFieldStatus.MISSING,
            detail=f"missing {dimension.value} evidence",
        )
    passed = not requires_license or "license:" in item.detail.lower()
    return _checked_field(
        dimension,
        passed=passed,
        detail=item.detail,
        evidence=evidence,
        citation=item.citation,
    )


def _checked_field(
    dimension: ReadinessDimension,
    passed: bool,
    detail: str,
    evidence: DatasetReadinessEvidence,
    citation: ReadinessCitation | None = None,
) -> ReadinessField:
    qualification = _qualification_for(dimension, evidence)
    if passed and qualification is None:
        return ReadinessField(
            dimension=dimension,
            status=ReadinessFieldStatus.SATISFIED,
            detail=detail,
            citation=citation,
        )
    if qualification is not None:
        return ReadinessField(
            dimension=dimension,
            status=ReadinessFieldStatus.QUALIFIED,
            detail=qualification.detail,
            citation=qualification.citation,
        )
    return ReadinessField(
        dimension=dimension,
        status=ReadinessFieldStatus.FAILING,
        detail=detail,
    )


def _qualification_for(
    dimension: ReadinessDimension,
    evidence: DatasetReadinessEvidence,
) -> ReadinessQualification | None:
    return next(
        (item for item in evidence.qualifications if item.dimension is dimension),
        None,
    )


def _verdict(fields: tuple[ReadinessField, ...]) -> ReadinessVerdict:
    statuses = {item.status for item in fields}
    if (
        ReadinessFieldStatus.MISSING in statuses
        or ReadinessFieldStatus.FAILING in statuses
    ):
        return ReadinessVerdict.BLOCKED
    if ReadinessFieldStatus.QUALIFIED in statuses:
        return ReadinessVerdict.READY_WITH_QUALIFICATIONS
    return ReadinessVerdict.READY


_TMS_CITATION: Final = ReadinessCitation(
    title="Tabula Muris Senis Data Objects: Aorta H5AD",
    uri="https://figshare.com/articles/dataset/Tabula_Muris_Senis_Data_Objects/12654728",
)
_PANCREAS_CITATION: Final = ReadinessCitation(
    title="scRNAseq Benchmark datasets",
    uri="https://zenodo.org/records/3357167",
)
_PANCREAS_METADATA_CITATION: Final = ReadinessCitation(
    title="Abdelaal et al. (2019) pancreas cross-study benchmark",
    uri="https://link.springer.com/article/10.1186/s13059-019-1795-z",
)
TMS_AORTA_READINESS_EVIDENCE: Final = DatasetReadinessEvidence(
    rights=ReadinessEvidence("Declared license: MIT.", _TMS_CITATION),
    evaluation=ReadinessEvidence(
        "Versioned package canary metric protocol is registered.", _TMS_CITATION
    ),
    metadata_concordance=ReadinessEvidence(
        "Pinned artifact metadata expectations are registered.", _TMS_CITATION
    ),
    qualifications=(
        ReadinessQualification(
            dimension=ReadinessDimension.RIGHTS,
            detail=(
                "File-level redistribution terms remain a cited qualification; "
                "this report does not authorize redistribution."
            ),
            citation=_TMS_CITATION,
        ),
    ),
)
PANCREAS_READINESS_EVIDENCE: Final = DatasetReadinessEvidence(
    rights=ReadinessEvidence("Declared license: CC-BY-4.0.", _PANCREAS_CITATION),
    evaluation=None,
    metadata_concordance=ReadinessEvidence(
        "Publication-scoped whole-cohort and held-out metadata checks are registered.",
        _PANCREAS_METADATA_CITATION,
    ),
)
_EMPTY_EVIDENCE: Final = DatasetReadinessEvidence(None, None, None)


def _built_in_evidence() -> dict[DatasetSnapshotIdentity, DatasetReadinessEvidence]:
    from bioml_data.datasets.pancreas._identity import (  # noqa: PLC0415
        PANCREAS_SNAPSHOT,
    )
    from bioml_data.datasets.tms_aorta._identity import (  # noqa: PLC0415
        TMS_AORTA_SNAPSHOT,
    )

    return {
        TMS_AORTA_SNAPSHOT: TMS_AORTA_READINESS_EVIDENCE,
        PANCREAS_SNAPSHOT: PANCREAS_READINESS_EVIDENCE,
    }


_BUILTIN_EVIDENCE: Final = _built_in_evidence()


__all__ = [
    "PANCREAS_READINESS_EVIDENCE",
    "TMS_AORTA_READINESS_EVIDENCE",
    "DatasetReadinessEvidence",
    "DatasetReadinessReport",
    "ReadinessCitation",
    "ReadinessDimension",
    "ReadinessEvidence",
    "ReadinessField",
    "ReadinessFieldStatus",
    "ReadinessQualification",
    "ReadinessVerdict",
    "assess_dataset_readiness",
    "assess_registration_readiness",
]
