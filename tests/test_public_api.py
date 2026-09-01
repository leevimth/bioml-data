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

    # Then: the plan and public declaration expose the exact canary contract.
    declaration = dataset.supported_splits[0]
    assert plan.protocol == "animal-held-out-v1"
    assert declaration.id == plan.protocol
    assert declaration.role is bio.SplitProtocolRole.CANARY
    assert declaration.required_metadata == ("cell_id", "donor_id")


def test_researcher_can_inspect_split_roles_and_evidence_from_public_api() -> None:
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

    # Then: the split is visibly a package canary and robustness check, not a claim
    # of literature recommendation.
    assert tuple(evidence.role for evidence in capability.evidence) == (
        bio.SplitProtocolRole.CANARY,
        bio.SplitProtocolRole.ROBUSTNESS,
    )
    assert (
        capability.evidence[0].evidence_type is bio.SplitEvidenceType.PRODUCT_PROTOCOL
    )
    assert capability.evidence[0].citations[0].title == "TMS Aorta package contract"
