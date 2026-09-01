"""Split-evidence publication boundary tests."""

from dataclasses import dataclass, replace

import pytest

from bioml_data._artifact_types import ArtifactId, TransformProtocolId
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    TaskId,
)
from bioml_data._split_capability_models import SplitEvidenceCitation
from bioml_data.datasets._registry import (
    DatasetCapabilityMismatchError,
    DatasetRegistry,
)
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


@dataclass(frozen=True, slots=True)
class _CitationCase:
    title: str
    uri: str


@pytest.mark.parametrize("scope_field", ["dataset", "artifact", "task", "protocol"])
def test_registry_rejects_split_evidence_for_a_different_scope(
    scope_field: str,
) -> None:
    # Given: evidence silently reassigned outside its capability scope.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    evidence = capability.evidence[0]
    replacement = {
        "dataset": DatasetSnapshotIdentity(
            name=DatasetName("other-dataset"),
            version=DatasetVersion("v1"),
        ),
        "artifact": replace(
            capability.artifact,
            transform_protocol=TransformProtocolId("other-transform-v1"),
        ),
        "task": TaskId("other-task"),
        "protocol": ProtocolId("other-protocol"),
    }[scope_field]
    wrong_evidence = replace(
        evidence,
        scope=replace(evidence.scope, **{scope_field: replacement}),
    )
    wrong_capability = replace(
        capability,
        evidence=(wrong_evidence, *capability.evidence[1:]),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(wrong_capability,),
    )

    # When: the registration boundary validates the scoped evidence.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: evidence cannot become authoritative for another scientific scope.


def test_registry_rejects_coordinated_artifact_scope_reassignment() -> None:
    # Given: capability and all evidence records are rewritten together.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    wrong_artifact = replace(
        capability.artifact,
        source_artifact=ArtifactId("sha256:" + "9" * 64),
    )
    wrong_evidence = tuple(
        replace(
            evidence,
            scope=replace(evidence.scope, artifact=wrong_artifact),
        )
        for evidence in capability.evidence
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(
            replace(capability, artifact=wrong_artifact, evidence=wrong_evidence),
        ),
    )

    # When: the coordinated rewrite reaches the publication boundary.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: registration provenance remains authoritative.


def test_trusted_registration_is_authority_for_a_coordinated_scope_change() -> None:
    # Given: trusted package source changes registration, capability, and evidence.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    changed_artifact = replace(
        capability.artifact,
        source_artifact=ArtifactId("sha256:" + "8" * 64),
    )
    changed_evidence = tuple(
        replace(
            evidence,
            scope=replace(evidence.scope, artifact=changed_artifact),
        )
        for evidence in capability.evidence
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        artifact_scope=changed_artifact,
        split_capabilities=(
            replace(
                capability,
                artifact=changed_artifact,
                evidence=changed_evidence,
            ),
        ),
    )

    # When: the internally coherent built-in registration is constructed.
    registry = DatasetRegistry(registrations=(registration,))

    # Then: validation enforces coherence, not an external source-code trust root.
    assert registry.registrations[0].artifact_scope == changed_artifact


@pytest.mark.parametrize("field", ["fit_scope", "leakage_caveat"])
def test_registry_rejects_blank_evidence_semantics(field: str) -> None:
    # Given: one evidence record with blank semantic metadata.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    evidence = replace(capability.evidence[0], **{field: "  "})
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(
            replace(
                capability,
                evidence=(evidence, *capability.evidence[1:]),
            ),
        ),
    )

    # When: the evidence is published.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: empty scientific semantics cannot enter the capability index.


@pytest.mark.parametrize(
    "case",
    [
        _CitationCase(title="  ", uri="https://example.test/evidence"),
        _CitationCase(title="Evidence", uri="docs/evidence.md"),
        _CitationCase(title="Evidence", uri="http://example.test/evidence"),
        _CitationCase(title="Evidence", uri="https://example.test/bad path"),
        _CitationCase(title="Evidence", uri="https://@"),
        _CitationCase(title="Evidence", uri="https://user@example.test/evidence"),
        _CitationCase(title="Evidence", uri="https://example.test/%GG"),
        _CitationCase(title="Evidence", uri="https://example.test:/evidence"),
        _CitationCase(title="Evidence", uri="https://example.test:99999/evidence"),
        _CitationCase(title="Evidence", uri="https://127.0.0.1/evidence"),
        _CitationCase(title="Evidence", uri="https://10.0.0.1/evidence"),
        _CitationCase(title="Evidence", uri="https://[::1]/evidence"),
    ],
)
def test_registry_rejects_invalid_evidence_citations(case: _CitationCase) -> None:
    # Given: a citation with a blank title or invalid publication URI.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    evidence = replace(
        capability.evidence[0],
        citations=(SplitEvidenceCitation(title=case.title, uri=case.uri),),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(
            replace(
                capability,
                evidence=(evidence, *capability.evidence[1:]),
            ),
        ),
    )

    # When: the evidence is published.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: citations remain human-readable and resolvable over HTTPS.
