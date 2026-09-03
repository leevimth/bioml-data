"""Dataset registry dispatch contract tests."""

from dataclasses import fields, replace

import pytest

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
