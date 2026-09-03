"""Dataset registry dispatch contract tests."""

from copy import deepcopy
from dataclasses import fields, replace

import pytest

import bioml_data as bio
from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    TaskId,
)
from bioml_data.datasets._capability_index import (
    SplitCapabilityIndexAlreadyPublishedError,
    publish_registry_capabilities,
)
from bioml_data.datasets._models import DatasetRegistration
from bioml_data.datasets._registry import (
    DATASET_REGISTRY,
    DatasetCapabilityMismatchError,
    DatasetRegistry,
    DuplicateDatasetRegistrationError,
)
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


def test_registration_excludes_provider_specific_download_metadata() -> None:
    # Given: the generic registration model shared by every dataset.

    # When: its architectural fields are inspected.
    field_names = tuple(field.name for field in fields(DatasetRegistration))

    # Then: Figshare-shaped compatibility pins are outside the registry seam.
    assert "download_pin" not in field_names


def test_registry_rejects_duplicate_exact_snapshot_keys() -> None:
    # Given: two registrations for the same exact dataset snapshot.

    # When: the registry is constructed.
    with pytest.raises(DuplicateDatasetRegistrationError):
        _ = DatasetRegistry(
            registrations=(TMS_AORTA_REGISTRATION, TMS_AORTA_REGISTRATION)
        )

    # Then: ambiguous exact keys never enter the registry.


def test_builtin_capability_index_cannot_be_republished() -> None:
    # Given: package startup has already published the validated built-in index.

    # When: another caller attempts to replace it.
    with pytest.raises(SplitCapabilityIndexAlreadyPublishedError):
        publish_registry_capabilities(())

    # Then: live capability queries cannot be mutated after startup.


def test_registry_snapshots_inputs_and_detaches_registration_views() -> None:
    # Given: a registry built from caller-owned registrations and the built-in view.
    source_registration = deepcopy(TMS_AORTA_REGISTRATION)
    registry = DatasetRegistry(registrations=(source_registration,))
    public_registration = DATASET_REGISTRY.registrations[0]
    public_capability = public_registration.split_capabilities[0]
    original_basis = public_capability.basis
    original_canary = public_capability.is_canary

    try:
        # When: caller-owned inputs and public registration views are corrupted.
        object.__setattr__(
            source_registration.definition.snapshot,
            "name",
            DatasetName("corrupted-constructor-input"),
        )
        object.__setattr__(
            public_capability, "basis", bio.SplitEvidenceBasis.LITERATURE_REFERENCE
        )
        object.__setattr__(public_capability, "is_canary", False)

        # Then: registry resolution and fresh public queries remain canonical.
        assert registry.resolve("tms-aorta").definition.snapshot.name == "tms-aorta"
        fresh_dataset = bio.load_dataset("tms-aorta")
        fresh_capability = bio.query_split_capability(
            bio.SplitCapabilityQuery(
                dataset=fresh_dataset.snapshot,
                task=fresh_dataset.supported_splits[0].task,
                protocol=fresh_dataset.supported_splits[0].id,
            )
        ).require_supported()
        assert fresh_capability.basis is bio.SplitEvidenceBasis.PACKAGE_DEFINED
        assert fresh_capability.is_canary
    finally:
        object.__setattr__(public_capability, "basis", original_basis)
        object.__setattr__(public_capability, "is_canary", original_canary)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "dataset",
            DatasetSnapshotIdentity(
                name=DatasetName("other-dataset"),
                version=DatasetVersion("v1"),
            ),
        ),
        ("task", TaskId("other-task")),
        ("protocol", ProtocolId("other-protocol")),
    ],
)
def test_registry_rejects_incoherent_split_capabilities(
    field: str,
    value: DatasetSnapshotIdentity | TaskId | ProtocolId,
) -> None:
    # Given: one capability whose dataset, task, or protocol leaves its definition.
    capability = replace(
        TMS_AORTA_REGISTRATION.split_capabilities[0],
        **{field: value},
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(capability,),
    )

    # When: the incoherent registration enters the boundary.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: invalid capability metadata cannot become authoritative.


def test_registry_rejects_missing_split_capability() -> None:
    # Given: a definition advertising a split without its executable capability.
    registration = replace(TMS_AORTA_REGISTRATION, split_capabilities=())

    # When: the incomplete registration enters the boundary.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: advertised and executable split contracts cannot diverge.


def test_registry_rejects_duplicate_split_capability() -> None:
    # Given: the same split capability is registered twice.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(capability, capability),
    )

    # When: the ambiguous registration enters the boundary.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: capability lookup has one exact contract per split.


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("required_columns", ("cell_id", "study_id")),
    ],
)
def test_registry_rejects_split_definition_contract_mismatch(
    field: str,
    value: tuple[str, ...],
) -> None:
    # Given: a capability contradicting its advertised definition contract.
    capability = replace(
        TMS_AORTA_REGISTRATION.split_capabilities[0],
        **{field: value},
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        split_capabilities=(capability,),
    )

    # When: the contradictory registration enters the boundary.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: role and required metadata share one authoritative contract.
