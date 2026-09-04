"""Researcher-facing protocol inspection scenarios."""

import json

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
