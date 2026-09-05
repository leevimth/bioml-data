"""Support-readiness gate scenarios."""

import json
from dataclasses import replace

import bioml_data as bio
from bioml_data._dataset_readiness import (
    PANCREAS_READINESS_EVIDENCE,
    ReadinessDimension,
    ReadinessQualification,
    ReadinessVerdict,
    assess_registration_readiness,
)
from bioml_data.datasets.pancreas._registration import PANCREAS_REGISTRATION


def test_tms_aorta_is_ready_with_its_explicit_rights_qualification() -> None:
    """A cited field qualification permits a bounded readiness result."""
    # Given: the complete registered TMS contract.

    # When: readiness is assessed through the public catalog API.
    report = bio.assess_dataset_readiness("tms-aorta")

    # Then: it has no unqualified missing or failing fields.
    assert report.verdict is ReadinessVerdict.READY_WITH_QUALIFICATIONS
    assert report.missing_fields == ()
    assert report.failing_fields == ()
    assert tuple(field.dimension for field in report.qualified_fields) == (
        ReadinessDimension.RIGHTS,
    )
    assert report.qualified_fields[0].citation is not None
    assert json.loads(report.to_json())["verdict"] == "ready_with_qualifications"


def test_pancreas_incomplete_evidence_bundle_is_blocked_with_named_fields() -> None:
    """Omitting required evidence never silently promotes a registration."""
    # Given: an intentionally incomplete Pancreas evidence bundle.
    incomplete = replace(
        PANCREAS_READINESS_EVIDENCE,
        rights=None,
        metadata_concordance=None,
    )

    # When: the same registered implementation is assessed with that bundle.
    report = assess_registration_readiness(PANCREAS_REGISTRATION, incomplete)

    # Then: each absent requirement is explicitly named as missing.
    assert report.verdict is ReadinessVerdict.BLOCKED
    assert tuple(field.dimension for field in report.missing_fields) == (
        ReadinessDimension.RIGHTS,
        ReadinessDimension.EVALUATION,
        ReadinessDimension.METADATA_CONCORDANCE,
    )


def test_cited_field_qualification_is_the_only_way_to_accept_a_failed_gate() -> None:
    """A structural mismatch blocks unless its own cited qualification is explicit."""
    # Given: a registration whose canonical derivation is deliberately absent.
    incomplete_registration = replace(PANCREAS_REGISTRATION, canonical_derivation=None)
    metadata = PANCREAS_READINESS_EVIDENCE.metadata_concordance
    assert metadata is not None
    qualified_evidence = replace(
        PANCREAS_READINESS_EVIDENCE,
        qualifications=(
            ReadinessQualification(
                dimension=ReadinessDimension.DETERMINISTIC_PREPARATION,
                detail=(
                    "External canonical materialization is out of scope for this "
                    "review."
                ),
                citation=metadata.citation,
            ),
        ),
    )

    # When: the mismatch is first assessed without a qualification.
    unqualified = assess_registration_readiness(
        incomplete_registration,
        PANCREAS_READINESS_EVIDENCE,
    )

    # Then: its exact field blocks readiness.
    assert ReadinessDimension.DETERMINISTIC_PREPARATION in tuple(
        field.dimension for field in unqualified.failing_fields
    )

    # When: the same failure has a field-specific cited qualification.
    report = assess_registration_readiness(
        incomplete_registration,
        qualified_evidence,
    )

    # Then: the preparation field is qualified rather than silently passing.
    preparation = next(
        field
        for field in report.qualified_fields
        if field.dimension is ReadinessDimension.DETERMINISTIC_PREPARATION
    )
    assert (
        preparation.citation
        is metadata.citation
    )
    assert ReadinessDimension.DETERMINISTIC_PREPARATION not in tuple(
        field.dimension for field in report.failing_fields
    )


def test_readiness_json_is_deterministic() -> None:
    """Repeated assessments emit one canonical machine-readable result."""
    # Given: the registered Pancreas contract.

    # When: the gate is run twice.
    first = bio.assess_dataset_readiness("pancreas-four-study").to_json()
    second = bio.assess_dataset_readiness("pancreas-four-study").to_json()

    # Then: consumers receive the same ordered serialized report.
    assert first == second
