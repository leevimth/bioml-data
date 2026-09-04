"""Researcher-facing protocol inspection scenarios."""

import json
from dataclasses import replace

import pytest

import bioml_data as bio

from ._metadata_concordance_helpers import (
    explicit_partition_evidence,
    metadata_dataset,
    metadata_scope,
)
from ._single_cell_fixtures import make_split


def test_inspect_protocol_exposes_the_declared_tms_contract_without_execution() -> None:
    """A plan-time read names the contract without materializing an assignment."""
    # Given: the public TMS protocol identity only.
    # When: a researcher asks for an inspection before downloading or splitting data.
    report = bio.inspect_protocol(
        "tms-aorta",
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
    )

    # Then: the report has the declared source, semantics, and executable rule.
    assert report.dataset_version == "figshare-project-64982"
    assert report.source_uri == "https://figshare.com/projects/Tabula_Muris_Senis/64982"
    assert report.evidence_basis == ("package_defined",)
    assert report.strategy == "group-held-out"
    assert report.grouping_column == "donor_id"
    assert report.requested_group_fractions == (0.8, 0.1, 0.1)
    assert "sha-256" in report.assignment_rule.lower()
    assert report.validation_policy == "present"
    assert report.realized_assignment is None


def test_inspect_protocol_serializes_the_same_canonical_json_as_the_cli() -> None:
    """Python output is a stable machine-readable public contract."""
    # Given: one plan-time report.
    report = bio.inspect_protocol(
        "tms-aorta",
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
    )

    # When: a consumer serializes it twice.
    first = report.to_json()
    second = report.to_json()

    # Then: canonical JSON is stable and decodes to the public fields.
    assert first == second
    assert json.loads(first)["protocol_id"] == "animal-held-out-v1"


def test_inspect_protocol_includes_only_explicitly_supplied_realized_assignment() -> (
    None
):
    """Receipt details appear only after a caller supplies a realized split."""
    # Given: a locally realized canonical fixture assignment.
    assignment = make_split(metadata_dataset())

    # When: the receipt is attached to the protocol inspection.
    report = bio.inspect_protocol(
        "tms-aorta",
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
        request=bio.ProtocolInspectionRequest(assignment=assignment),
    )

    # Then: the receipt identity, actual held-out entities, and counts are visible.
    assert report.realized_assignment is not None
    assert report.realized_assignment.identity == str(assignment.assignment_identity)
    assert report.realized_assignment.test_group_ids
    assert report.realized_assignment.cross_partition_group_ids == ()


def test_inspect_protocol_summarizes_explicitly_supplied_concordance() -> None:
    """Concordance is evidence status, not an inspection-triggered execution."""
    # Given: one scoped concordance report over a fixture split.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    concordance = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=(
            bio.PublicationMetadataExpectation.not_reported(
                scope=metadata_scope(),
                partition=None,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
            ),
            *explicit_partition_evidence(metadata_scope()),
        ),
    )

    # When: the report is explicitly supplied to inspection.
    report = bio.inspect_protocol(
        "tms-aorta",
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
        request=bio.ProtocolInspectionRequest(
            assignment=assignment,
            concordance=concordance,
        ),
    )

    # Then: it has a derived immutable identity and precise status counts.
    assert report.concordance is not None
    assert report.concordance.not_reported_count == 4
    assert report.concordance.mismatch_count == 0
    assert report.concordance.identity
    rendered = report.to_text()
    assert report.realized_assignment is not None
    assert report.realized_assignment.identity in rendered
    assert report.concordance.identity in rendered


def test_inspect_protocol_text_includes_every_declared_contract_category() -> None:
    """Default human inspection is complete enough to plan a study unaided."""
    # Given: a plan-time inspection with no realized data execution.
    report = bio.inspect_protocol(
        "tms-aorta",
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
    )

    # When: the researcher reads the human default output.
    rendered = report.to_text()
    serialized = report.to_json()

    # Then: every material plan-time contract value is visible.
    for value in (
        report.dataset_name,
        report.dataset_version,
        report.source_uri,
        report.source_artifact,
        report.transform_protocol,
        report.task_id,
        report.protocol_id,
        report.evidence_basis[0],
        report.evidence[0].citations[0].title,
        report.evidence[0].citations[0].uri,
        report.strategy,
        report.grouping_column,
        report.leakage_unit,
        report.held_out_axis,
        report.evaluation_target,
        report.assignment_rule,
        report.deterministic_tie_break,
        report.seed_policy,
        report.allocation_policy,
        report.validation_policy,
        report.required_metadata[0],
        report.group_overlap_invariant,
        report.preprocessing_fit_scope[0],
        report.lifecycle,
        report.readiness,
        report.limitations[0],
    ):
        assert value in rendered
        assert value in serialized
    assert "80%/10%/10%" in rendered
    assert "realized assignment: absent" in rendered
    assert "concordance: absent" in rendered


def test_inspect_protocol_rejects_concordance_for_a_different_assignment() -> None:
    """A concordance result cannot be paired with a different split receipt."""
    # Given: two valid but differently seeded assignments over the same dataset.
    dataset = metadata_dataset()
    first = make_split(dataset)
    second = bio.SplitAssigner(
        dataset=dataset.snapshot,
        task=first.task,
        observations=dataset.split_observations,
    ).split(protocol="animal-held-out-v1", seed=18)
    concordance = bio.compare_metadata_concordance(
        dataset,
        second,
        expectations=(
            bio.PublicationMetadataExpectation.not_reported(
                scope=metadata_scope(),
                partition=None,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
            ),
            *explicit_partition_evidence(metadata_scope()),
        ),
    )

    # When: a caller pairs the seed-17 receipt with seed-18 concordance evidence.
    with pytest.raises(bio.ProtocolInspectionReceiptMismatchError) as captured:
        _ = bio.inspect_protocol(
            "tms-aorta",
            task="cell-type-annotation-v1",
            protocol="animal-held-out-v1",
            request=bio.ProtocolInspectionRequest(
                assignment=first,
                concordance=concordance,
            ),
        )

    # Then: inspection names the broken identity join rather than summarizing it.
    assert captured.value.field == "concordance_assignment_identity"


def test_inspect_protocol_rejects_every_identity_uncommitted_receipt_field() -> None:
    """Rendered receipt facts cannot change while retaining the original identity."""
    # Given: one valid assignment and four independently tampered facts.
    original = make_split(metadata_dataset())
    forged_receipts = (
        replace(original, observation_count=original.observation_count + 1),
        replace(original, group_count=original.group_count + 1),
        replace(
            original,
            requested_group_fractions=replace(
                original.requested_group_fractions,
                train=0.7,
                validation=0.2,
            ),
        ),
        replace(
            original,
            realized_group_counts=replace(
                original.realized_group_counts,
                train=original.realized_group_counts.train + 1,
                validation=original.realized_group_counts.validation - 1,
            ),
        ),
    )

    # When: each stale identity is supplied as realized inspection evidence.
    for forged in forged_receipts:
        with pytest.raises(bio.ProtocolInspectionReceiptMismatchError) as captured:
            _ = bio.inspect_protocol(
                "tms-aorta",
                task="cell-type-annotation-v1",
                protocol="animal-held-out-v1",
                request=bio.ProtocolInspectionRequest(assignment=forged),
            )

        # Then: identity validation rejects every rendered semantic mutation.
        assert captured.value.field == "assignment_identity"


def test_inspect_protocol_rejects_partition_concordance_without_assignment() -> None:
    """Realized partition comparisons require their matching split receipt."""
    # Given: a valid concordance report with materialized partitions.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    concordance = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=(
            bio.PublicationMetadataExpectation.not_reported(
                scope=metadata_scope(),
                partition=None,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
            ),
            *explicit_partition_evidence(metadata_scope()),
        ),
    )

    # When: a consumer omits the receipt that the partitions summarize.
    with pytest.raises(bio.ProtocolInspectionReceiptMismatchError) as captured:
        _ = bio.inspect_protocol(
            "tms-aorta",
            task="cell-type-annotation-v1",
            protocol="animal-held-out-v1",
            request=bio.ProtocolInspectionRequest(concordance=concordance),
        )

    # Then: the report cannot be interpreted as a plan-only result.
    assert captured.value.field == "concordance_assignment"


def test_inspect_protocol_accepts_explicit_dataset_only_concordance() -> None:
    """Plan-only comparisons stay allowed only when they carry no split identity."""
    # Given: a dataset-level report deliberately stripped of partition evidence.
    dataset = metadata_dataset()
    assignment = make_split(dataset)
    complete = bio.compare_metadata_concordance(
        dataset,
        assignment,
        expectations=(
            bio.PublicationMetadataExpectation.not_reported(
                scope=metadata_scope(),
                partition=None,
                metric=bio.MetadataMetric.OBSERVATION_COUNT,
            ),
            *explicit_partition_evidence(metadata_scope()),
        ),
    )
    plan_only = replace(
        complete,
        assignment_identity=None,
        partition_reports=(),
    )

    # When: the independent dataset-level evidence is attached without a receipt.
    report = bio.inspect_protocol(
        "tms-aorta",
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
        request=bio.ProtocolInspectionRequest(concordance=plan_only),
    )

    # Then: it is accepted as explicitly plan-only evidence.
    assert report.concordance is not None
