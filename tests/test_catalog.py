"""Dataset catalog contract tests."""

from inspect import Parameter, signature

import pytest

from bioml_data import (
    DatasetLifecycle,
    UnknownDatasetError,
    UnknownDatasetVersionError,
    UnsupportedSplitProtocolError,
    load_dataset,
)
from bioml_data._split_capability import (
    SplitCapabilityQuery,
    SplitEvidenceBasis,
    SplitStrategy,
    query_split_capability,
)


def test_load_dataset_returns_pinned_tms_definition() -> None:
    # Given: the built-in TMS Aorta catalog entry.
    dataset_name = "tms-aorta"

    # When: a consumer loads the entry without a version override.
    dataset = load_dataset(dataset_name)

    # Then: the resolved definition exposes its immutable identity and scope.
    assert dataset.snapshot.name == dataset_name
    assert dataset.snapshot.version == "figshare-project-64982"
    assert dataset.lifecycle is DatasetLifecycle.PLANNED
    assert (
        dataset.source.uri == "https://figshare.com/projects/Tabula_Muris_Senis/64982"
    )
    assert tuple(task.id for task in dataset.tasks) == ("cell-type-annotation-v1",)
    assert tuple(split.id for split in dataset.supported_splits) == (
        "animal-held-out-v1",
    )


def test_load_dataset_selects_an_explicit_version() -> None:
    # Given: the pinned TMS Aorta catalog version.
    version = "figshare-project-64982"

    # When: a consumer requests that exact version.
    dataset = load_dataset("tms-aorta", version=version)

    # Then: the selected snapshot records the requested version.
    assert dataset.snapshot.version == version


def test_load_dataset_reports_an_unknown_dataset() -> None:
    # Given: a dataset name absent from the built-in catalog.
    dataset_name = "missing-dataset"

    # When: a consumer tries to load it.
    with pytest.raises(UnknownDatasetError) as captured:
        _ = load_dataset(dataset_name)

    # Then: the error identifies the request and available dataset names.
    assert captured.value.name == dataset_name
    assert captured.value.available == ("tms-aorta",)


def test_load_dataset_reports_an_unknown_version() -> None:
    # Given: a known dataset with an unavailable version.
    version = "missing-version"

    # When: a consumer requests the unavailable version.
    with pytest.raises(UnknownDatasetVersionError) as captured:
        _ = load_dataset("tms-aorta", version=version)

    # Then: the error distinguishes a version miss from a dataset miss.
    assert captured.value.name == "tms-aorta"
    assert captured.value.requested == version
    assert captured.value.available == ("figshare-project-64982",)


def test_plan_split_requires_an_explicit_protocol() -> None:
    # Given: the public split-planning method.
    split_signature = signature(load_dataset("tms-aorta").plan_split)

    # When: a consumer inspects the protocol parameter.
    protocol = split_signature.parameters["protocol"]

    # Then: protocol is keyword-only and has no silent default.
    assert protocol.kind is Parameter.KEYWORD_ONLY
    assert "=" not in str(protocol)


def test_plan_split_reports_an_unsupported_protocol() -> None:
    # Given: TMS Aorta declares one product-canary split protocol.
    dataset = load_dataset("tms-aorta")

    # When: a consumer requests an undeclared protocol.
    with pytest.raises(UnsupportedSplitProtocolError) as captured:
        _ = dataset.plan_split(
            task="cell-type-annotation-v1",
            protocol="random-cell-v1",
        )

    # Then: the error identifies the dataset and the exact supported alternative.
    assert captured.value.dataset == dataset.snapshot
    assert captured.value.protocol == "random-cell-v1"
    assert captured.value.supported == ("animal-held-out-v1",)


def test_plan_split_resolves_the_existing_animal_canary_capability() -> None:
    # Given: the public TMS catalog definition and its supported split declaration.
    dataset = load_dataset("tms-aorta")

    # When: a consumer plans the implemented animal-held-out protocol.
    plan = dataset.plan_split(
        task="cell-type-annotation-v1",
        protocol="animal-held-out-v1",
    )

    # Then: the plan and catalog declaration resolve the implemented group holdout.
    declaration = dataset.supported_splits[0]
    assert plan.protocol == "animal-held-out-v1"
    assert declaration.basis is SplitEvidenceBasis.PACKAGE_DEFINED
    assert declaration.strategy is SplitStrategy.GROUP_HELD_OUT
    assert declaration.id == plan.protocol
    assert declaration.task == plan.task
    assert declaration.required_metadata == ("cell_id", "donor_id")


def test_catalog_declaration_matches_split_capability_evidence() -> None:
    # Given: the catalog declaration projected from the implemented capability.
    dataset = load_dataset("tms-aorta")
    declaration = dataset.supported_splits[0]

    # When: capability evidence is queried for that exact declaration.
    capability = query_split_capability(
        SplitCapabilityQuery(
            dataset=dataset.snapshot,
            task=declaration.task,
            protocol=declaration.id,
        )
    ).require_supported()

    # Then: provenance, semantics, and canary usage remain coherent.
    assert declaration.id == capability.protocol
    assert declaration.basis is capability.basis
    assert declaration.strategy is capability.strategy
    assert declaration.held_out_axis == capability.held_out_axis
    assert declaration.leakage_unit == capability.leakage_unit
    assert declaration.grouping_column == capability.grouping_column
    assert declaration.evaluation_target == capability.evaluation_target
    assert declaration.is_canary is capability.is_canary
    assert declaration.required_metadata == capability.required_columns
    assert capability.held_out_axis == "animal"
