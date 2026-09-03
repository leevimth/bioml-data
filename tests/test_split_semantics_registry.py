"""Registry validation tests for active split semantics."""

from dataclasses import replace

import pytest

from bioml_data._domain import (
    SplitEvidenceBasis,
    SplitProtocolCompatibilityRoleError,
    SplitProtocolRole,
    SplitStrategy,
)
from bioml_data._split_capability_models import SplitEvidenceCitation
from bioml_data._split_contract_errors import InvalidSplitSemanticTypeError
from bioml_data.datasets._registry import (
    DatasetCapabilityMismatchError,
    DatasetRegistry,
)
from bioml_data.datasets.tms_aorta._registration import TMS_AORTA_REGISTRATION


def test_registry_accepts_non_canary_package_defined_split() -> None:
    # Given: a package-defined split derived from the public TMS canary contract.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                is_canary=False,
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(replace(capability, is_canary=False),),
    )

    # When: coherent package-defined semantics are registered without canary use.
    registry = DatasetRegistry(registrations=(registration,))

    # Then: the compatibility role is cleared while package provenance remains.
    split = registry.registrations[0].definition.supported_splits[0]
    assert split.role is None
    assert not registry.registrations[0].split_capabilities[0].is_canary


@pytest.mark.parametrize(
    "role",
    [SplitProtocolRole.REFERENCE, SplitProtocolRole.ROBUSTNESS],
)
def test_new_split_contract_rejects_an_explicit_legacy_role_mismatch(
    role: SplitProtocolRole,
) -> None:
    # Given: the public new-contract TMS split with a derived canary role.
    split = TMS_AORTA_REGISTRATION.definition.supported_splits[0]

    # When: a caller explicitly changes that deprecated role.
    with pytest.raises(SplitProtocolCompatibilityRoleError):
        _ = replace(split, role=role)

    with pytest.raises(SplitProtocolCompatibilityRoleError):
        _ = replace(TMS_AORTA_REGISTRATION.split_capabilities[0], role=role)

    with pytest.raises(SplitProtocolCompatibilityRoleError):
        _ = replace(TMS_AORTA_REGISTRATION.split_capabilities[0].evidence[0], role=role)

    # Then: legacy role fields cannot override active basis and canary semantics.


def test_registry_accepts_multiple_evidence_bases_for_explicit_semantics() -> None:
    # Given: one split with independently cited community and literature evidence.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    community_evidence = replace(
        capability.evidence[0],
        basis=SplitEvidenceBasis.COMMUNITY_REFERENCE,
        citations=(
            SplitEvidenceCitation(
                title="OpenProblems Label Projection v1",
                uri="https://www.openproblems.bio/benchmarks/label_projection/v1.0.0/",
            ),
        ),
    )
    literature_evidence = replace(
        capability.evidence[0],
        basis=SplitEvidenceBasis.LITERATURE_REFERENCE,
        citations=(
            SplitEvidenceCitation(
                title="Abdelaal, Michielsen et al. 2019",
                uri="https://pmc.ncbi.nlm.nih.gov/articles/PMC6734286/",
            ),
        ),
    )
    multi_basis_capability = replace(
        capability,
        evidence=(community_evidence, literature_evidence),
        basis=SplitEvidenceBasis.COMMUNITY_REFERENCE,
    )
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                basis=SplitEvidenceBasis.COMMUNITY_REFERENCE,
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
    records = registry.registrations[0].split_capabilities[0].evidence
    assert {record.basis for record in records} == {
        SplitEvidenceBasis.COMMUNITY_REFERENCE,
        SplitEvidenceBasis.LITERATURE_REFERENCE,
    }
    assert records[0].citations != records[1].citations


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

    # Then: source, semantics, and package usage stay synchronized.


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


@pytest.mark.parametrize("field", ["basis", "strategy"])
def test_registry_rejects_raw_strings_for_typed_split_semantics(field: str) -> None:
    # Given: public contracts that declare source and strategy enum fields.
    value = {"basis": "package_defined", "strategy": "group-held-out"}[field]
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]

    # When: an untyped semantic value reaches either constructor.
    with pytest.raises(InvalidSplitSemanticTypeError):
        _ = replace(
            TMS_AORTA_REGISTRATION.definition.supported_splits[0],
            **{field: value},
        )
    with pytest.raises(InvalidSplitSemanticTypeError):
        _ = replace(capability, **{field: value})

    # Then: source and strategy values remain closed constructor vocabularies.


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


def test_registry_accepts_generic_group_held_out_evaluation_target() -> None:
    # Given: a canonical target label that is not constrained to held-out-axis prose.
    capability = TMS_AORTA_REGISTRATION.split_capabilities[0]
    target = "deployment-target-v1"
    definition = replace(
        TMS_AORTA_REGISTRATION.definition,
        supported_splits=(
            replace(
                TMS_AORTA_REGISTRATION.definition.supported_splits[0],
                evaluation_target=target,
            ),
        ),
    )
    registration = replace(
        TMS_AORTA_REGISTRATION,
        definition=definition,
        split_capabilities=(replace(capability, evaluation_target=target),),
    )

    # When: a generic group-held-out target reaches registry publication.
    registry = DatasetRegistry(registrations=(registration,))

    # Then: the registry preserves it without encoding a scientific prose claim.
    assert registry.registrations[0].split_capabilities[0].evaluation_target == target
