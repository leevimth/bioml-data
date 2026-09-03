"""Public consumer scenarios."""

import bioml_data as bio


def test_researcher_can_inspect_a_dataset_contract() -> None:
    # Given: a researcher knows the public dataset key.
    dataset_key = "tms-aorta"

    # When: they load its catalog definition through the package root.
    dataset = bio.load_dataset(dataset_key)

    # Then: they can inspect version, task, and split support before downloading data.
    assert dataset.snapshot.version == "figshare-project-64982"
    assert tuple(task.id for task in dataset.tasks) == ("cell-type-annotation-v1",)
    assert tuple(split.id for split in dataset.supported_splits) == (
        "animal-held-out-v1",
    )


def test_researcher_can_plan_the_public_animal_canary_split() -> None:
    # Given: the public TMS catalog definition.
    dataset = bio.load_dataset("tms-aorta")

    # When: a researcher resolves the explicit supported split.
    plan = dataset.plan_split(
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
    )

    # Then: the plan and public declaration expose the split semantics.
    declaration = dataset.supported_splits[0]
    assert plan.protocol == "animal-held-out-v1"
    assert declaration.id == plan.protocol
    assert declaration.basis is bio.SplitEvidenceBasis.PACKAGE_DEFINED
    assert declaration.strategy is bio.SplitStrategy.GROUP_HELD_OUT
    assert declaration.held_out_axis == "animal"
    assert declaration.leakage_unit == "mouse"
    assert declaration.grouping_column == "donor_id"
    assert declaration.evaluation_target == "unseen animal"
    assert declaration.is_canary
    assert declaration.required_metadata == ("cell_id", "donor_id")


def test_researcher_can_read_the_deprecated_canary_role_projection() -> None:
    # Given: the public TMS definition under the new basis-and-usage contract.
    declaration = bio.load_dataset("tms-aorta").supported_splits[0]

    # When: an older reader accesses the previous role field.
    role = declaration.role

    # Then: canary usage remains readable without becoming evidence authority.
    assert role is bio.SplitProtocolRole.CANARY


def test_researcher_can_read_the_deprecated_capability_role_projection() -> None:
    # Given: the public TMS split capability under the new basis contract.
    dataset = bio.load_dataset("tms-aorta")
    declaration = dataset.supported_splits[0]
    capability = bio.query_split_capability(
        bio.SplitCapabilityQuery(
            dataset=dataset.snapshot,
            task=declaration.task,
            protocol=declaration.id,
        )
    ).require_supported()

    # When: an older reader accesses the capability and scoped evidence roles.
    capability_role = capability.role
    evidence_role = capability.evidence[0].role

    # Then: canary compatibility is projected at protocol level, not as evidence.
    assert capability_role is bio.SplitProtocolRole.CANARY
    assert evidence_role is None


def test_researcher_can_inspect_split_semantics_and_evidence_from_public_api() -> None:
    # Given: the public TMS dataset contract and its supported split.
    dataset = bio.load_dataset("tms-aorta")
    declaration = dataset.supported_splits[0]
    query = bio.SplitCapabilityQuery(
        dataset=dataset.snapshot,
        task=declaration.task,
        protocol=declaration.id,
    )

    # When: the researcher queries evidence through the package root.
    capability = bio.query_split_capability(query).require_supported()

    # Then: package provenance, split semantics, and test usage stay separate.
    assert capability.basis is bio.SplitEvidenceBasis.PACKAGE_DEFINED
    assert capability.strategy is bio.SplitStrategy.GROUP_HELD_OUT
    assert capability.held_out_axis == "animal"
    assert capability.leakage_unit == "mouse"
    assert capability.grouping_column == "donor_id"
    assert capability.evaluation_target == "unseen animal"
    assert capability.is_canary
    assert tuple(evidence.basis for evidence in capability.evidence) == (
        bio.SplitEvidenceBasis.PACKAGE_DEFINED,
    )
