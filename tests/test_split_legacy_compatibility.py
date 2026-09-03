"""Compatibility tests for the deprecated split evidence vocabulary."""

from dataclasses import replace

import pytest

from bioml_data._domain import (
    ProtocolId,
    SplitProtocolDefinition,
    SplitProtocolRole,
    TaskId,
)
from bioml_data._split_capability_models import SplitEvidenceType
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
