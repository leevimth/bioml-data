"""Split capability and assignment contract tests."""

from __future__ import annotations

import pytest

from bioml_data import _split
from bioml_data import _split_capability as capabilities
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    SplitProtocolRole,
    TaskId,
    UnsupportedSplitProtocolError,
)


def _tms_snapshot() -> DatasetSnapshotIdentity:
    return DatasetSnapshotIdentity(
        name=DatasetName("tms-aorta"),
        version=DatasetVersion("figshare-project-64982"),
    )


def _observation(cell_id: str, donor_id: str | None) -> _split.SplitObservation:
    metadata = ()
    if donor_id is not None:
        metadata = (
            _split.MetadataValue(
                column=_split.MetadataColumn("donor_id"),
                value=donor_id,
            ),
        )
    return _split.SplitObservation(
        observation_id=_split.ObservationId(cell_id),
        metadata=metadata,
    )


def test_query_reports_tms_animal_canary_capability() -> None:
    # Given: the supported TMS Aorta annotation task and explicit protocol.
    query = capabilities.SplitCapabilityQuery(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        protocol="animal-held-out-v1",
    )

    # When: a consumer queries the protocol capability.
    result = capabilities.query_split_capability(query)

    # Then: machine-readable semantics identify the canary and its evidence.
    assert isinstance(result, capabilities.SupportedSplitCapability)
    assert result.capability.role.value == "canary"
    assert result.capability.evidence_type.value == "product_protocol"
    assert result.capability.held_out_axis == "animal"
    assert result.capability.leakage_unit == "mouse"
    assert result.capability.required_columns == ("cell_id", "donor_id")


def test_query_exposes_scoped_canary_and_robustness_evidence() -> None:
    # Given: the supported TMS Aorta animal-held-out protocol.
    query = capabilities.SplitCapabilityQuery(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        protocol="animal-held-out-v1",
    )

    # When: a researcher inspects its evidence-bearing capability.
    capability = capabilities.query_split_capability(query).require_supported()

    # Then: package roles are explicit and every claim has the exact same scope.
    assert tuple(evidence.role for evidence in capability.evidence) == (
        SplitProtocolRole.CANARY,
        SplitProtocolRole.ROBUSTNESS,
    )
    assert all(
        evidence.scope.dataset == capability.dataset for evidence in capability.evidence
    )
    assert all(
        evidence.scope.artifact == capability.artifact
        for evidence in capability.evidence
    )
    assert all(
        evidence.scope.task == capability.task for evidence in capability.evidence
    )
    assert all(
        evidence.scope.protocol == capability.protocol
        for evidence in capability.evidence
    )
    assert capability.artifact.source_artifact == (
        "sha256:0fbf73145f2b50f956b9946aa2fa17e5fce0e40ddfc5ba922a1d503d65ced3c3"
    )
    assert capability.artifact.transform_protocol == "tms-aorta-csr-v1"
    assert capability.evidence[1].fit_scope == "train-only feature selection"
    assert "not literature-recommended" in capability.evidence[1].leakage_caveat


def test_split_protocol_roles_distinguish_literature_and_community_references() -> None:
    # Given: the public role vocabulary used by evidence records.

    # When: reference roles are inspected.
    values = {role.value for role in SplitProtocolRole}

    # Then: literature reproduction and community compatibility are not conflated.
    assert "literature_reference" in values
    assert "community_reference" in values


def test_query_distinguishes_unsupported_from_unknown_capability() -> None:
    # Given: one assessed task and one unassessed dataset snapshot.
    unsupported_query = capabilities.SplitCapabilityQuery(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        protocol="random-cell-v1",
    )
    unknown_query = capabilities.SplitCapabilityQuery(
        dataset=DatasetSnapshotIdentity(
            name=DatasetName("future-dataset"),
            version=DatasetVersion("v1"),
        ),
        task=TaskId("cell-type-annotation-v1"),
        protocol="animal-held-out-v1",
    )

    # When: capability support is queried for each scope.
    unsupported = capabilities.query_split_capability(unsupported_query)
    unknown = capabilities.query_split_capability(unknown_query)

    # Then: assessed absence is unsupported while unassessed scope stays unknown.
    assert isinstance(unsupported, capabilities.UnsupportedSplitCapability)
    assert unsupported.supported_protocols == ("animal-held-out-v1",)
    assert isinstance(unknown, capabilities.UnknownSplitCapability)


def test_split_requires_an_explicit_protocol_value() -> None:
    # Given: an assigner with enough animal groups for all partitions.
    assigner = _split.SplitAssigner(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        observations=tuple(
            _observation(f"cell-{index}", f"mouse-{index}") for index in range(3)
        ),
    )

    # When: the caller explicitly supplies a missing protocol value.
    with pytest.raises(_split.MissingSplitProtocolError):
        _ = assigner.split(protocol=None, seed=7)

    # Then: no protocol is silently selected.


def test_split_reports_an_unsupported_protocol() -> None:
    # Given: an assessed dataset/task with one supported protocol.
    assigner = _split.SplitAssigner(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        observations=tuple(
            _observation(f"cell-{index}", f"mouse-{index}") for index in range(3)
        ),
    )

    # When: the caller selects an undeclared protocol.
    with pytest.raises(UnsupportedSplitProtocolError) as captured:
        _ = assigner.split(protocol="random-cell-v1", seed=7)

    # Then: the typed error reports only the declared alternative.
    assert captured.value.supported == ("animal-held-out-v1",)


def test_split_reports_insufficient_metadata_separately() -> None:
    # Given: a supported protocol but one observation lacks donor metadata.
    assigner = _split.SplitAssigner(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        observations=(_observation("cell-1", None),),
    )

    # When: assignment attempts to read the declared leakage unit.
    with pytest.raises(_split.InsufficientSplitMetadataError) as captured:
        _ = assigner.split(protocol="animal-held-out-v1", seed=7)

    # Then: the typed error identifies the row and absent canonical column.
    assert captured.value.observation_id == "cell-1"
    assert captured.value.missing_columns == ("donor_id",)


def test_split_is_deterministic_and_keeps_animals_together() -> None:
    # Given: fourteen animal groups with two cells per animal in opposing row order.
    observations = tuple(
        _observation(f"cell-{mouse}-{replicate}", f"mouse-{mouse}")
        for mouse in range(14)
        for replicate in range(2)
    )
    forward = _split.SplitAssigner(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        observations=observations,
    )
    reverse = _split.SplitAssigner(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        observations=tuple(reversed(observations)),
    )

    # When: the same versioned protocol and seed assign both inputs.
    first = forward.split(protocol="animal-held-out-v1", seed=19)
    second = reverse.split(protocol="animal-held-out-v1", seed=19)

    # Then: identity is order-independent and no mouse crosses partitions.
    assert first.assignment_identity == second.assignment_identity
    assert first.assignments == second.assignments
    mouse_partitions: dict[str, set[_split.SplitPartition]] = {}
    for assignment in first.assignments:
        mouse_partitions.setdefault(assignment.group, set()).add(assignment.partition)
    assert all(len(partitions) == 1 for partitions in mouse_partitions.values())


def test_split_receipt_records_requested_and_realized_group_counts() -> None:
    # Given: the 14-group scale of the TMS Aorta canary.
    assigner = _split.SplitAssigner(
        dataset=_tms_snapshot(),
        task=TaskId("cell-type-annotation-v1"),
        observations=tuple(
            _observation(f"cell-{index}", f"mouse-{index}") for index in range(14)
        ),
    )

    # When: the product-defined 80/10/10 canary protocol is assigned.
    receipt = assigner.split(protocol="animal-held-out-v1", seed=23)

    # Then: the receipt exposes protocol intent and integer realization.
    assert receipt.requested_group_fractions == _split.PartitionFractions(
        train=0.8,
        validation=0.1,
        test=0.1,
    )
    assert receipt.realized_group_counts == _split.PartitionGroupCounts(
        train=11,
        validation=2,
        test=1,
    )
    assert receipt.seed == 23
    assert receipt.group_count == 14
    assert receipt.observation_count == 14
