"""Public consumer scenarios."""

import bioml_data as bio
from bioml_data._domain import DatasetName, SourceUri


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
    assert capability.evidence_type is bio.SplitEvidenceType.PRODUCT_PROTOCOL
    assert (
        capability.evidence[0].evidence_type is bio.SplitEvidenceType.PRODUCT_PROTOCOL
    )


def test_public_catalog_and_capability_graphs_are_detached_from_registry_state() -> (
    None
):
    # Given: public definition and capability graphs backed by the built-in registry.
    dataset = bio.load_dataset("tms-aorta")
    split = dataset.supported_splits[0]
    capability_result = bio.query_split_capability(
        bio.SplitCapabilityQuery(
            dataset=dataset.snapshot,
            task=split.task,
            protocol=split.id,
        )
    )
    capability = capability_result.require_supported()
    artifact_scope = capability.artifact
    evidence = capability.evidence[0]
    citation = evidence.citations[0]

    # When: hostile code bypasses frozen dataclass assignment on each public layer.
    object.__setattr__(dataset.snapshot, "name", DatasetName("corrupted"))
    object.__setattr__(dataset.source, "uri", SourceUri("https://corrupted.invalid"))
    object.__setattr__(dataset, "supported_splits", ())
    object.__setattr__(split, "basis", bio.SplitEvidenceBasis.LITERATURE_REFERENCE)
    object.__setattr__(capability_result, "capability", None)
    object.__setattr__(capability.dataset, "name", DatasetName("corrupted"))
    object.__setattr__(capability, "basis", bio.SplitEvidenceBasis.LITERATURE_REFERENCE)
    object.__setattr__(capability, "is_canary", False)
    object.__setattr__(capability, "role", bio.SplitProtocolRole.REFERENCE)
    object.__setattr__(capability, "evidence", ())
    object.__setattr__(artifact_scope, "transform_protocol", "corrupted-transform")
    object.__setattr__(evidence.scope, "protocol", "corrupted-protocol")
    object.__setattr__(evidence, "citations", ())
    object.__setattr__(citation, "uri", "https://corrupted.invalid")

    # Then: new public reads still return the registry's canonical contract.
    fresh_dataset = bio.load_dataset("tms-aorta")
    fresh_split = fresh_dataset.supported_splits[0]
    fresh_capability = bio.query_split_capability(
        bio.SplitCapabilityQuery(
            dataset=fresh_dataset.snapshot,
            task=fresh_split.task,
            protocol=fresh_split.id,
        )
    ).require_supported()
    assert fresh_dataset.snapshot.name == "tms-aorta"
    assert fresh_dataset.source.uri == (
        "https://figshare.com/projects/Tabula_Muris_Senis/64982"
    )
    assert fresh_split.basis is bio.SplitEvidenceBasis.PACKAGE_DEFINED
    assert fresh_capability.evidence[0].scope.protocol == "animal-held-out-v1"
    assert fresh_capability.evidence[0].citations[0].uri.startswith("https://github")
