"""Dataset registry dispatch contract tests."""

from dataclasses import fields, replace

import pytest

from bioml_data._domain import (
    DatasetName,
    DatasetSnapshotIdentity,
    DatasetVersion,
    ProtocolId,
    SplitEvidenceBasis,
    SplitProtocolDefinition,
    SplitProtocolRole,
    SplitStrategy,
    TaskId,
)
from bioml_data._split_capability_models import SplitEvidenceType
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
        ("role", SplitProtocolRole.REFERENCE),
        ("required_columns", ("cell_id", "study_id")),
    ],
)
def test_registry_rejects_split_definition_contract_mismatch(
    field: str,
    value: SplitProtocolRole | tuple[str, ...],
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


def test_registry_accepts_non_canary_package_defined_split() -> None:
    # Given: a package-defined split used for execution rather than a smoke test.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    non_canary_capability = replace(capability, is_canary=False)
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                role=None,
                is_canary=False,
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(non_canary_capability,),
    )

    # When: coherent package-defined semantics are registered without canary use.
    registry = DatasetRegistry(registrations=(registration,))

    # Then: package provenance and canary designation are independent axes.
    assert not registry.registrations[0].split_capabilities[0].is_canary


def test_registry_accepts_multiple_evidence_bases_for_explicit_semantics() -> None:
    # Given: one concrete split with two independently sourced evidence records.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    community_evidence = replace(
        capability.evidence[0],
        basis=SplitEvidenceBasis.COMMUNITY_REFERENCE,
    )
    literature_evidence = replace(
        capability.evidence[0],
        basis=SplitEvidenceBasis.LITERATURE_REFERENCE,
    )
    multi_basis_capability = replace(
        capability,
        evidence=(community_evidence, literature_evidence),
        basis=SplitEvidenceBasis.COMMUNITY_REFERENCE,
        strategy=SplitStrategy.GROUP_HELD_OUT,
    )
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                basis=SplitEvidenceBasis.COMMUNITY_REFERENCE,
                strategy=SplitStrategy.GROUP_HELD_OUT,
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(multi_basis_capability,),
    )

    # When: the registry validates the evidence records against one split contract.
    registry = DatasetRegistry(registrations=(registration,))

    # Then: several evidence sources can share the same explicit split semantics.
    registered_capability = registry.registrations[0].split_capabilities[0]
    assert {record.basis for record in registered_capability.evidence} == {
        SplitEvidenceBasis.COMMUNITY_REFERENCE,
        SplitEvidenceBasis.LITERATURE_REFERENCE,
    }


@pytest.mark.parametrize(
    "field",
    ["basis", "strategy", "held_out_axis", "is_canary"],
)
def test_registry_rejects_divergent_definition_and_capability_semantics(
    field: str,
) -> None:
    # Given: one public definition that disagrees with its executable capability.
    replacement = {
        "basis": SplitEvidenceBasis.LITERATURE_REFERENCE,
        "strategy": SplitStrategy.LEAVE_ONE_STUDY_OUT,
        "held_out_axis": "study",
        "is_canary": False,
    }[field]
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                **{field: replacement},
            ),
        ),
    )
    registration = replace(TMS_AORTA_REGISTRATION, definition=definition)

    # When: the contradictory pair reaches registry publication.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: split source, semantics, and package usage stay synchronized.


def test_registry_rejects_evidence_basis_without_a_matching_record() -> None:
    # Given: a split declaration whose advertised basis has no evidence record.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                basis=SplitEvidenceBasis.LITERATURE_REFERENCE,
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(
            replace(capability, basis=SplitEvidenceBasis.LITERATURE_REFERENCE),
        ),
    )

    # When: the unmatched evidence claim reaches registry publication.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: a declared basis must be represented by one scoped evidence record.


def test_registry_rejects_invalid_leave_one_study_out_semantics() -> None:
    # Given: a leave-one-study-out strategy paired with animal grouping metadata.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                strategy=SplitStrategy.LEAVE_ONE_STUDY_OUT,
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(
            replace(capability, strategy=SplitStrategy.LEAVE_ONE_STUDY_OUT),
        ),
    )

    # When: the incoherent strategy enters the registry.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: the strategy constrains held-out axis, grouping, and leakage unit.


def test_legacy_split_contract_constructors_remain_readable() -> None:
    # Given: a caller using the pre-BIO-28 positional constructor shapes.
    definition = SplitProtocolDefinition(
        ProtocolId("legacy-v1"),
        SplitProtocolRole.REFERENCE,
        TaskId("task-v1"),
        ("study_id",),
    )

    # When: the legacy definition is constructed.
    role = definition.role

    # Then: the legacy field remains available without opting into new semantics.
    assert role is SplitProtocolRole.REFERENCE
    assert definition.basis is None


def test_registry_rejects_a_legacy_only_split_contract() -> None:
    # Given: a fully legacy registration created before the basis migration.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    legacy_evidence = replace(
        capability.evidence[0],
        role=SplitProtocolRole.REFERENCE,
        evidence_type=SplitEvidenceType.LITERATURE_REUSE,
        basis=None,
    )
    legacy_capability = replace(
        capability,
        role=SplitProtocolRole.REFERENCE,
        evidence_type=SplitEvidenceType.LITERATURE_REUSE,
        evidence=(legacy_evidence,),
        basis=None,
        strategy=None,
        evaluation_target="",
        is_canary=False,
    )
    legacy_definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                role=SplitProtocolRole.REFERENCE,
                basis=None,
                strategy=None,
                held_out_axis="animal",
                leakage_unit="mouse",
                grouping_column="donor_id",
                evaluation_target="",
                is_canary=False,
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=legacy_definition,
        split_capabilities=(legacy_capability,),
    )

    # When: the old contract reaches the upgraded registry.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: legacy constructors are readable but cannot publish active evidence.


@pytest.mark.parametrize(
    "field",
    ["basis", "strategy"],
)
def test_registry_rejects_raw_strings_for_typed_split_semantics(field: str) -> None:
    # Given: a declaration and capability using a string instead of the enum.
    value = {
        "basis": "package_defined",
        "strategy": "group-held-out",
    }[field]
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                **{field: value},
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(replace(capability, **{field: value}),),
    )

    # When: untyped split metadata reaches registry publication.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: source and strategy values remain closed typed vocabularies.


@pytest.mark.parametrize(
    "field",
    ["held_out_axis", "leakage_unit", "grouping_column", "evaluation_target"],
)
def test_registry_rejects_noncanonical_group_held_out_semantics(field: str) -> None:
    # Given: a group-held-out contract with one whitespace-padded semantic value.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    value = f" {getattr(capability, field)} "
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                **{field: value},
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(replace(capability, **{field: value}),),
    )

    # When: noncanonical semantics reach registry publication.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: concrete split semantics remain canonical machine-readable values.
