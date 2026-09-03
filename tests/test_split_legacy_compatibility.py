"""Compatibility tests for the deprecated split evidence vocabulary."""

from dataclasses import asdict, replace

import pytest

from bioml_data._domain import (
    ProtocolId,
    SplitProtocolCompatibilityRoleError,
    SplitProtocolDefinition,
    SplitProtocolRole,
    TaskId,
)
from bioml_data._split_capability_models import SplitEvidenceType
from bioml_data._split_contract_errors import (
    InvalidSplitCanaryUsageError,
    InvalidSplitProtocolRoleError,
)
from bioml_data.datasets._registry import (
    DatasetCapabilityMismatchError,
    DatasetRegistry,
)
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


def test_legacy_split_contract_constructors_remain_readable() -> None:
    # Given: a caller using the pre-BIO-28 positional constructor shape.
    definition = SplitProtocolDefinition(
        ProtocolId("legacy-v1"),
        SplitProtocolRole.REFERENCE,
        TaskId("task-v1"),
        ("study_id",),
    )

    # When: the legacy definition is constructed.
    role = definition.role

    # Then: the legacy field remains available without new semantics.
    assert role is SplitProtocolRole.REFERENCE
    assert definition.basis is None


def test_legacy_split_role_remains_a_dataclass_field() -> None:
    # Given: two legacy definitions that differ only in their role.
    reference = SplitProtocolDefinition(
        ProtocolId("legacy-v1"),
        SplitProtocolRole.REFERENCE,
        TaskId("task-v1"),
        ("study_id",),
    )
    robustness = replace(reference, role=SplitProtocolRole.ROBUSTNESS)

    # When: standard dataclass operations inspect and replace the contracts.
    serialized = asdict(reference)

    # Then: role participates in equality, replacement, and serialization.
    assert reference != robustness
    assert serialized["role"] is SplitProtocolRole.REFERENCE
    assert replace(reference).role is SplitProtocolRole.REFERENCE


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


def test_new_definition_rejects_non_bool_canary_usage() -> None:
    # Given: the public new-contract TMS split declaration.
    split = TMS_AORTA_REGISTRATION.definition.supported_splits[0]

    # When: a caller supplies a truthy string as package-test usage.
    with pytest.raises(InvalidSplitCanaryUsageError):
        _ = replace(split, is_canary="true")

    # Then: canary usage remains an exact boolean boundary.


def test_new_capability_rejects_non_bool_canary_usage() -> None:
    # Given: the public new-contract TMS split capability.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]

    # When: a caller supplies an integer as package-test usage.
    with pytest.raises(InvalidSplitCanaryUsageError):
        _ = replace(capability, is_canary=1)

    # Then: truthy values cannot alter package-test semantics.


def test_registry_rejects_a_forged_non_bool_canary_usage() -> None:
    # Given: a forged registration that bypassed its public typed constructors.
    split = replace(TMS_AORTA_REGISTRATION.definition.supported_splits[0])
    capability = replace(TMS_AORTA_REGISTRATION.split_capabilities[0])
    object.__setattr__(split, "is_canary", 1)
    object.__setattr__(capability, "is_canary", 1)
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(split,),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(capability,),
    )

    # When: the public registry receives the forged split contract.
    with pytest.raises(DatasetCapabilityMismatchError):
        _ = DatasetRegistry(registrations=(registration,))

    # Then: registry publication independently requires an exact bool.


def test_definition_rejects_a_raw_string_legacy_role() -> None:
    # Given: the public new-contract TMS split declaration.
    split = TMS_AORTA_REGISTRATION.definition.supported_splits[0]

    # When: a caller supplies an untyped legacy role.
    with pytest.raises(InvalidSplitProtocolRoleError) as captured:
        _ = replace(split, role="canary")

    # Then: the typed boundary error remains printable.
    assert str(captured.value)


def test_capability_rejects_a_raw_string_legacy_role() -> None:
    # Given: the public new-contract TMS split capability.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]

    # When: a caller supplies an untyped legacy role.
    with pytest.raises(InvalidSplitProtocolRoleError) as captured:
        _ = replace(capability, role="canary")

    # Then: the typed boundary error remains printable.
    assert str(captured.value)


def test_new_contract_uses_a_coherent_real_role_field() -> None:
    # Given: public new-contract definition and capability declarations.
    split = TMS_AORTA_REGISTRATION.definition.supported_splits[0]
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]

    # When: the package usage changes with its role updated explicitly.
    with pytest.raises(SplitProtocolCompatibilityRoleError):
        _ = replace(split, is_canary=False)
    with pytest.raises(SplitProtocolCompatibilityRoleError):
        _ = replace(capability, is_canary=False)
    definition_without_canary = replace(split, is_canary=False, role=None)
    capability_without_canary = replace(capability, is_canary=False, role=None)

    # Then: role remains a real compatibility field with coherent active semantics.
    assert split.role is SplitProtocolRole.CANARY
    assert capability.role is SplitProtocolRole.CANARY
    assert definition_without_canary.role is None
    assert capability_without_canary.role is None
