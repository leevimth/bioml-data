"""Validation helpers for executable split contract publication."""

import re
from typing import Final, assert_never

from bioml_data._domain import (
    SplitEvidenceBasis,
    SplitProtocolDefinition,
    SplitProtocolRole,
    SplitStrategy,
)
from bioml_data._split_capability_models import (
    SplitCapability,
    legacy_evidence_type_for_basis,
)

_SEMANTIC_TOKEN: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9-]*\Z")
_METADATA_COLUMN: Final[re.Pattern[str]] = re.compile(r"[a-z][a-z0-9_]*\Z")


def valid_split_capability_contract_mode(capability: SplitCapability) -> bool:
    """Return whether active evidence and legacy reader fields agree."""
    if type(capability.is_canary) is not bool:
        return False
    return (
        type(capability.basis) is SplitEvidenceBasis
        and capability.role
        is (SplitProtocolRole.CANARY if capability.is_canary else None)
        and capability.evidence_type is legacy_evidence_type_for_basis(capability.basis)
        and capability.basis
        in tuple(evidence.basis for evidence in capability.evidence)
        and all(
            evidence.role is None
            and type(evidence.basis) is SplitEvidenceBasis
            and evidence.evidence_type is legacy_evidence_type_for_basis(evidence.basis)
            for evidence in capability.evidence
        )
        and len({evidence.basis for evidence in capability.evidence})
        == len(capability.evidence)
    )


def valid_split_semantics(capability: SplitCapability) -> bool:
    """Return whether strategy-specific split fields are canonical."""
    if type(capability.strategy) is not SplitStrategy:
        return False

    common_semantics = (
        _valid_semantic_token(capability.held_out_axis)
        and _valid_semantic_token(capability.leakage_unit)
        and _valid_metadata_column(capability.grouping_column)
        and _valid_semantic_text(capability.evaluation_target)
    )
    match capability.strategy:
        case SplitStrategy.GROUP_HELD_OUT:
            return common_semantics
        case SplitStrategy.LEAVE_ONE_STUDY_OUT:
            return (
                common_semantics
                and capability.held_out_axis == "study"
                and capability.grouping_column == "study_id"
                and capability.leakage_unit == "study"
            )
        case _:
            assert_never(capability.strategy)


def valid_definition_compatibility_projection(
    definition: SplitProtocolDefinition,
) -> bool:
    """Return whether a definition exposes its legacy role consistently."""
    if type(definition.basis) is not SplitEvidenceBasis:
        return False
    if type(definition.is_canary) is not bool:
        return False
    expected_role = SplitProtocolRole.CANARY if definition.is_canary else None
    return definition.role is expected_role


def _valid_semantic_token(value: str) -> bool:
    return type(value) is str and _SEMANTIC_TOKEN.fullmatch(value) is not None


def _valid_metadata_column(value: str) -> bool:
    return type(value) is str and _METADATA_COLUMN.fullmatch(value) is not None


def _valid_semantic_text(value: str) -> bool:
    return type(value) is str and bool(value) and value == value.strip()
